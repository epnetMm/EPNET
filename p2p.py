import socket
import threading
import json
import time
import logging
import os
import requests
from typing import Dict, List, Any, Set, Optional, Callable
from blockchain import Blockchain
from transaction import Transaction
from block import Block
from config import PEERS_FILE, ensure_data_directory, save_config, load_config

class P2PServer:
    """
    Handles the peer-to-peer networking for the EPNET blockchain.
    This is responsible for:
    - Discovering other nodes
    - Synchronizing the blockchain
    - Broadcasting new blocks and transactions
    - Handling consensus
    """
    
    def __init__(self, blockchain: Blockchain, host: str = '0.0.0.0', port: int = 8000):
        """
        Initialize the P2P server
        
        Args:
            blockchain: The blockchain instance
            host: Host to bind the server to
            port: Port to bind the server to
        """
        self.blockchain = blockchain
        self.host = host
        self.port = port
        self.peers: Set[str] = set()
        self.running = False
        self.server_thread: Optional[threading.Thread] = None
        
        # Callbacks for events
        self.on_block_added: Optional[Callable] = None
        self.on_transaction_added: Optional[Callable] = None
        
        # 저장된 피어 목록 불러오기
        self.load_peers()
    
    def start(self):
        """
        Start the P2P server in a separate thread
        """
        if self.running:
            return
        
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def stop(self):
        """
        Stop the P2P server
        """
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=1)
            self.server_thread = None
    
    def _run_server(self):
        """
        Run the HTTP server that listens for P2P messages
        """
        # This is handled by Flask in app.py
        pass
    
    def broadcast_transaction(self, transaction: Transaction):
        """
        Broadcast a transaction to all connected peers
        
        Args:
            transaction: The transaction to broadcast
        """
        transaction_data = transaction.to_dict()
        
        for peer in self.peers:
            try:
                url = f"http://{peer}/transaction/new"
                requests.post(url, json=transaction_data, timeout=5)
            except requests.RequestException as e:
                print(f"Failed to broadcast transaction to {peer}: {e}")
    
    def broadcast_block(self, block: Block):
        """
        Broadcast a new block to all connected peers
        
        Args:
            block: The block to broadcast
        """
        block_data = block.to_dict()
        
        for peer in self.peers:
            try:
                url = f"http://{peer}/block/new"
                requests.post(url, json=block_data, timeout=5)
            except requests.RequestException as e:
                print(f"Failed to broadcast block to {peer}: {e}")
    
    def add_peer(self, address: str):
        """
        Add a new peer to the list of known peers
        
        Args:
            address: The address of the peer to add (host:port)
        """
        if address not in self.peers:
            self.peers.add(address)
            self.blockchain.register_node(address)
            logging.info(f"새 피어가 추가되었습니다: {address}")
            self.save_peers()  # 피어 목록 저장
    
    def remove_peer(self, address: str):
        """
        Remove a peer from the list of known peers
        
        Args:
            address: The address of the peer to remove (host:port)
        """
        if address in self.peers:
            self.peers.remove(address)
            logging.info(f"피어가 제거되었습니다: {address}")
            self.save_peers()  # 피어 목록 저장
    
    def sync_blockchain(self):
        """
        Synchronize the blockchain with all known peers.
        This implements the consensus algorithm.
        """
        max_length = len(self.blockchain.chain)
        new_chain = None
        
        # Find the longest valid chain among all peers
        for peer in self.peers:
            try:
                url = f"http://{peer}/chain"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    chain_data = response.json()
                    chain_length = chain_data.get('length', 0)
                    chain = chain_data.get('chain', [])
                    
                    # Check if the chain is longer and valid
                    if chain_length > max_length:
                        # Create a temporary blockchain to validate the chain
                        temp_blockchain = Blockchain()
                        temp_blockchain.chain = []
                        
                        # Convert the chain data to Block objects
                        for block_dict in chain:
                            transactions = []
                            for tx_dict in block_dict.get('transactions', []):
                                transaction = Transaction.from_dict(tx_dict)
                                transactions.append(transaction)
                            
                            block = Block(
                                index=block_dict['index'],
                                transactions=transactions,
                                timestamp=block_dict['timestamp'],
                                previous_hash=block_dict['previous_hash'],
                                nonce=block_dict.get('nonce', 0)
                            )
                            block.hash = block_dict['hash']
                            temp_blockchain.chain.append(block)
                        
                        # Check if the chain is valid
                        if temp_blockchain.is_chain_valid():
                            max_length = chain_length
                            new_chain = temp_blockchain.chain
            except requests.RequestException as e:
                print(f"Failed to sync with peer {peer}: {e}")
        
        # Replace our chain if we found a longer valid chain
        if new_chain:
            self.blockchain.chain = new_chain
            return True
        
        return False
    
    def discover_peers(self, seed_nodes: List[str]):
        """
        Discover new peers using seed nodes
        
        Args:
            seed_nodes: List of seed node addresses to connect to
        """
        for node in seed_nodes:
            if node not in self.peers:
                try:
                    # Add the seed node
                    self.add_peer(node)
                    
                    # Get the seed node's peers
                    url = f"http://{node}/nodes"
                    response = requests.get(url, timeout=5)
                    
                    if response.status_code == 200:
                        nodes = response.json().get('nodes', [])
                        for peer in nodes:
                            if peer not in self.peers:
                                self.add_peer(peer)
                except requests.RequestException as e:
                    print(f"Failed to discover peers from {node}: {e}")
    
    def get_peers(self) -> List[str]:
        """
        Get the list of known peers
        
        Returns:
            List of peer addresses
        """
        return list(self.peers)
        
    def save_peers(self):
        """
        피어 목록을 디스크에 저장합니다.
        """
        try:
            ensure_data_directory()
            peer_data = {
                'peers': list(self.peers),
                'updated_at': time.time()
            }
            save_config(PEERS_FILE, peer_data)
            logging.info(f"피어 목록이 저장되었습니다: {len(self.peers)}개 노드")
            return True
        except Exception as e:
            logging.error(f"피어 목록 저장 중 오류: {e}")
            return False
    
    def load_peers(self):
        """
        디스크에서 피어 목록을 로드합니다.
        """
        try:
            peer_data = load_config(PEERS_FILE)
            if peer_data and 'peers' in peer_data:
                for peer in peer_data['peers']:
                    self.peers.add(peer)
                    self.blockchain.register_node(peer)
                logging.info(f"피어 목록이 로드되었습니다: {len(self.peers)}개 노드")
            return True
        except Exception as e:
            logging.error(f"피어 목록 로드 중 오류: {e}")
            return False
