import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from transaction import Transaction

class Block:
    """
    Represents a block in the EPNET blockchain.
    Each block contains:
    - Index (block number)
    - List of transactions
    - Timestamp
    - Hash of the previous block
    - Nonce (used for proof of work)
    - Current block hash
    """
    difficulty = 4  # Number of leading zeros required in hash for proof of work
    
    def __init__(self, index: int, transactions: List[Transaction], timestamp: float, 
                 previous_hash: str, nonce: int = 0):
        """
        Initialize a new block
        
        Args:
            index: Block number
            transactions: List of transactions in this block
            timestamp: Time when the block was created
            previous_hash: Hash of the previous block
            nonce: Value used for proof of work
        """
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """
        Calculate the hash of the block
        
        Returns:
            SHA-256 hash of the block
        """
        # Convert transactions to a JSON string
        transaction_strings = [json.dumps(tx.to_dict(), sort_keys=True) for tx in self.transactions]
        block_string = f"{self.index}{self.previous_hash}{self.timestamp}{transaction_strings}{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self):
        """
        Mine the block by finding a hash with the required number of leading zeros
        """
        while self.hash[:Block.difficulty] != '0' * Block.difficulty:
            self.nonce += 1
            self.hash = self.calculate_hash()
    
    def has_valid_transactions(self) -> bool:
        """
        Check if all transactions in the block are valid
        
        Returns:
            True if all transactions are valid, False otherwise
        """
        for transaction in self.transactions:
            if not transaction.verify_signature():
                return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the block to a dictionary
        
        Returns:
            Dictionary representation of the block
        """
        return {
            'index': self.index,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'hash': self.hash
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Block':
        """
        Create a block from a dictionary
        
        Args:
            data: Dictionary representation of a block
            
        Returns:
            A Block instance
        """
        transactions = []
        for tx_data in data['transactions']:
            transaction = Transaction.from_dict(tx_data)
            transactions.append(transaction)
        
        block = Block(
            index=data['index'],
            transactions=transactions,
            timestamp=data['timestamp'],
            previous_hash=data['previous_hash'],
            nonce=data['nonce']
        )
        block.hash = data['hash']
        return block
