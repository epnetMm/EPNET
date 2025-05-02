import hashlib
import json
import time
import logging
from typing import List, Dict, Any, Optional
from block import Block
from transaction import Transaction
import utils

class Blockchain:
    """
    The main blockchain class for the EPNET blockchain.
    This class is responsible for managing the blockchain, including:
    - Adding new blocks
    - Validating the chain
    - Managing transactions
    - Handling consensus
    """

    def __init__(self, load_from_disk=True):
        """
        블록체인 초기화
        
        Args:
            load_from_disk: 디스크에서 블록체인 데이터를 로드할지 여부
        """
        from config import MINING_REWARD, MAX_SUPPLY, BLOCKCHAIN_FILE, ensure_data_directory
        import os
        
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.nodes = set()
        self.mining_reward = MINING_REWARD  # 초기 채굴 보상 (설정에서 가져옴)
        self.max_supply = MAX_SUPPLY  # EP 최대 발행량 (설정에서 가져옴)
        self.current_supply = 0
        self.mining_reward_address = None  # 마이닝 보상을 받을 주소
        self.last_difficulty_adjustment = 0  # 마지막 난이도 조정 블록 번호
        
        # 디스크에서 블록체인 데이터 로드 시도
        if load_from_disk and os.path.exists(BLOCKCHAIN_FILE):
            try:
                self.load_from_disk()
            except Exception as e:
                logging.error(f"블록체인 로드 중 오류: {e}")
                # 로드 실패시 제네시스 블록 생성
                self.create_genesis_block()
        else:
            # 새 블록체인 생성
            self.create_genesis_block()
            
        # 블록체인 유효성 검사
        if not self.is_chain_valid():
            logging.warning("블록체인 데이터가 유효하지 않습니다. 제네시스 블록으로 재설정합니다.")
            self.chain = []
            self.create_genesis_block()
    
    def create_genesis_block(self):
        """
        Create the genesis block - the first block in the blockchain
        """
        genesis_block = Block(0, [], time.time(), "0")
        genesis_block.hash = genesis_block.calculate_hash()
        self.chain.append(genesis_block)
    
    @property
    def last_block(self) -> Block:
        """
        Returns the latest block in the blockchain
        """
        return self.chain[-1]
    
    def add_transaction(self, transaction: Transaction) -> int:
        """
        Adds a new transaction to the list of pending transactions
        
        Args:
            transaction: The transaction to add
            
        Returns:
            The index of the block that will hold this transaction
        """
        # Verify transaction
        if not transaction.verify_signature():
            raise Exception("Invalid transaction signature")
        
        # Check if sender has enough balance
        if transaction.sender != "0":  # Mining reward transactions have sender as "0"
            sender_balance = self.get_balance(transaction.sender)
            if sender_balance < transaction.amount:
                raise Exception("Insufficient balance")
        
        self.pending_transactions.append(transaction)
        return self.last_block.index + 1
    
    def mine_pending_transactions(self, mining_reward_address: str) -> Optional[Block]:
        """
        Mine pending transactions and add a new block to the chain
        
        Args:
            mining_reward_address: The address where the mining reward will be sent
            
        Returns:
            The newly created block or None if max supply reached
        """
        # Check if we've reached max supply
        if self.current_supply >= self.max_supply:
            return None
        
        # Calculate reward based on remaining coins
        remaining = self.max_supply - self.current_supply
        reward = min(self.mining_reward, remaining)
        
        # Add mining reward transaction
        reward_transaction = Transaction("0", mining_reward_address, reward)
        self.pending_transactions.append(reward_transaction)
        
        # Create new block
        block = Block(
            index=len(self.chain),
            transactions=self.pending_transactions,
            timestamp=time.time(),
            previous_hash=self.last_block.hash
        )
        
        block.mine_block()
        
        # Add block to chain
        self.chain.append(block)
        
        # Update current supply
        self.current_supply += reward
        
        # Reset pending transactions
        self.pending_transactions = []
        
        # 블록체인 상태를 디스크에 저장
        self.save_to_disk()
        
        # 블록 채굴 로그 기록
        logging.info(f"새 블록이 채굴되었습니다 - 인덱스: {block.index}, 해시: {block.hash[:10]}...")
        logging.info(f"현재 블록체인 길이: {len(self.chain)}, 현재 유통량: {self.current_supply} EP")
        
        return block
    
    def is_chain_valid(self) -> bool:
        """
        Check if the blockchain is valid
        
        Returns:
            True if valid, False otherwise
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            # Check if hash is correctly calculated
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check if this block points to the correct previous block
            if current_block.previous_hash != previous_block.hash:
                return False
            
            # Verify proof of work
            if not current_block.hash.startswith('0' * Block.difficulty):
                return False
        
        return True
    
    def get_balance(self, address: str) -> float:
        """
        Calculate the balance of a given address
        
        Args:
            address: The address to check
            
        Returns:
            The balance of the address
        """
        balance = 0
        
        # Check all transactions in the blockchain
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.sender == address:
                    balance -= transaction.amount
                if transaction.recipient == address:
                    balance += transaction.amount
        
        return balance
    
    def get_transactions_by_address(self, address: str) -> List[Dict[str, Any]]:
        """
        Get all transactions for a specific address
        
        Args:
            address: The address to get transactions for
            
        Returns:
            List of transactions
        """
        transactions = []
        
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.sender == address or transaction.recipient == address:
                    transactions.append(transaction.to_dict())
        
        return transactions
    
    def replace_chain(self, new_chain: List[Block]) -> bool:
        """
        Replace the chain with a new longer valid chain
        
        Args:
            new_chain: The new chain to replace with
            
        Returns:
            True if chain was replaced, False otherwise
        """
        # Convert new_chain JSON to Block objects if necessary
        if isinstance(new_chain[0], dict):
            converted_chain = []
            for block_dict in new_chain:
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
                converted_chain.append(block)
            new_chain = converted_chain
        
        # Check if the new chain is longer and valid
        if len(new_chain) <= len(self.chain):
            return False
        
        # Validate the new chain
        for i in range(1, len(new_chain)):
            current_block = new_chain[i]
            previous_block = new_chain[i-1]
            
            # Check if hash is valid
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check if this block points to the correct previous block
            if current_block.previous_hash != previous_block.hash:
                return False
            
            # Verify proof of work
            if not current_block.hash.startswith('0' * Block.difficulty):
                return False
        
        # Replace our chain with the new valid chain
        self.chain = new_chain
        
        # Recalculate current supply
        self.current_supply = 0
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.sender == "0":  # Mining reward
                    self.current_supply += transaction.amount
        
        return True
    
    def register_node(self, address: str):
        """
        Add a new node to the list of nodes
        
        Args:
            address: Address of node (e.g. 'http://192.168.0.1:5000')
        """
        parsed_url = utils.parse_url(address)
        self.nodes.add(parsed_url.netloc)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the blockchain to a dictionary
        
        Returns:
            Dictionary representation of the blockchain
        """
        return {
            'chain': [block.to_dict() for block in self.chain],
            'pending_transactions': [tx.to_dict() for tx in self.pending_transactions],
            'current_supply': self.current_supply,
            'max_supply': self.max_supply
        }
    
    def save_to_disk(self):
        """
        블록체인 상태를 디스크에 저장합니다.
        이를 통해 노드 재시작 후에도 블록체인 상태가 유지됩니다.
        """
        from config import BLOCKCHAIN_FILE, ensure_data_directory, save_config
        import logging
        
        try:
            ensure_data_directory()
            blockchain_data = self.to_dict()
            save_config(BLOCKCHAIN_FILE, blockchain_data)
            logging.info(f"블록체인이 성공적으로 저장되었습니다: {len(self.chain)} 블록")
            return True
        except Exception as e:
            logging.error(f"블록체인 저장 중 오류: {e}")
            return False
    
    def load_from_disk(self):
        """
        디스크에서 블록체인 상태를 로드합니다.
        """
        from config import BLOCKCHAIN_FILE, load_config
        import logging
        
        try:
            blockchain_data = load_config(BLOCKCHAIN_FILE)
            if not blockchain_data:
                logging.warning("블록체인 데이터를 찾을 수 없습니다. 새 블록체인을 생성합니다.")
                return False
            
            # Clear genesis block created in init
            self.chain = []
            
            for block_dict in blockchain_data['chain']:
                transactions = []
                for tx_dict in block_dict['transactions']:
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
                self.chain.append(block)
            
            for tx_dict in blockchain_data['pending_transactions']:
                transaction = Transaction.from_dict(tx_dict)
                self.pending_transactions.append(transaction)
            
            self.current_supply = blockchain_data['current_supply']
            
            logging.info(f"블록체인이 성공적으로 로드되었습니다: {len(self.chain)} 블록")
            return True
        except Exception as e:
            logging.error(f"블록체인 로드 중 오류: {e}")
            return False
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Blockchain':
        """
        Create a blockchain from a dictionary
        
        Args:
            data: Dictionary representation of a blockchain
            
        Returns:
            A Blockchain instance
        """
        blockchain = Blockchain(load_from_disk=False)
        
        # Clear genesis block created in init
        blockchain.chain = []
        
        for block_dict in data['chain']:
            transactions = []
            for tx_dict in block_dict['transactions']:
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
            blockchain.chain.append(block)
        
        for tx_dict in data['pending_transactions']:
            transaction = Transaction.from_dict(tx_dict)
            blockchain.pending_transactions.append(transaction)
        
        blockchain.current_supply = data['current_supply']
        
        return blockchain
