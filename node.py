import os
import json
from typing import Dict, Any, Optional, List
from blockchain import Blockchain
from wallet import Wallet
from miner import Miner
from p2p import P2PServer

class Node:
    """
    Represents a node in the EPNET blockchain network.
    A node combines the blockchain, wallet, miner, and P2P server components.
    """
    
    def __init__(self, wallet_path: Optional[str] = None):
        """
        Initialize a node
        
        Args:
            wallet_path: Optional path to wallet file
        """
        # Initialize blockchain
        self.blockchain = Blockchain()
        
        # Create or load wallet
        if wallet_path and os.path.exists(wallet_path):
            self.wallet = Wallet.load_from_file(wallet_path)
        else:
            self.wallet = Wallet()
            if wallet_path:
                self.wallet.save_to_file(wallet_path)
        
        # Initialize miner
        self.miner = Miner(self.blockchain, self.wallet)
        
        # Initialize P2P server
        self.p2p_server = P2PServer(self.blockchain)
    
    def start(self):
        """
        Start the node services
        """
        # Start P2P server
        self.p2p_server.start()
    
    def stop(self):
        """
        Stop the node services
        """
        # Stop miner
        self.miner.stop_mining()
        
        # Stop P2P server
        self.p2p_server.stop()
    
    def connect_to_network(self, seed_nodes: List[str]):
        """
        Connect to the network using seed nodes
        
        Args:
            seed_nodes: List of seed node addresses
        """
        self.p2p_server.discover_peers(seed_nodes)
        self.p2p_server.sync_blockchain()
    
    def get_blockchain_info(self) -> Dict[str, Any]:
        """
        Get information about the blockchain
        
        Returns:
            Dictionary with blockchain information
        """
        return {
            'chain_length': len(self.blockchain.chain),
            'current_supply': self.blockchain.current_supply,
            'max_supply': self.blockchain.max_supply,
            'pending_transactions': len(self.blockchain.pending_transactions)
        }
    
    def get_wallet_info(self) -> Dict[str, Any]:
        """
        Get information about the node's wallet
        
        Returns:
            Dictionary with wallet information
        """
        return {
            'address': self.wallet.public_key,
            'balance': self.blockchain.get_balance(self.wallet.public_key)
        }
    
    def start_mining(self, mining_reward_address=None):
        """
        Start the mining process
        
        Args:
            mining_reward_address: Optional address to receive mining rewards
        """
        def block_mined_callback(block):
            # Broadcast the new block to the network
            self.p2p_server.broadcast_block(block)
        
        self.miner.start_mining(
            callback=block_mined_callback,
            mining_reward_address=mining_reward_address
        )
    
    def stop_mining(self):
        """
        Stop the mining process
        """
        self.miner.stop_mining()
    
    def create_transaction(self, recipient: str, amount: float) -> Dict[str, Any]:
        """
        Create and broadcast a new transaction
        
        Args:
            recipient: Recipient's address
            amount: Amount to transfer
            
        Returns:
            Dictionary with transaction information
        """
        # Create and sign the transaction
        transaction = self.wallet.create_transaction(recipient, amount)
        
        # Add to blockchain
        try:
            block_index = self.blockchain.add_transaction(transaction)
            
            # Broadcast to network
            self.p2p_server.broadcast_transaction(transaction)
            
            return {
                'status': 'success',
                'message': f'Transaction will be added to Block {block_index}',
                'transaction': transaction.to_dict()
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
