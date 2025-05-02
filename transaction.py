import json
import time
import hashlib
from typing import Dict, Any, Optional
import nacl.signing
import nacl.encoding
import base64

class Transaction:
    """
    Represents a transaction on the EPNET blockchain.
    Each transaction contains:
    - Sender's public key
    - Recipient's public key
    - Amount being transferred
    - Timestamp
    - Transaction signature
    """
    def __init__(self, sender: str, recipient: str, amount: float, 
                 timestamp: Optional[float] = None, signature: Optional[str] = None):
        """
        Initialize a new transaction
        
        Args:
            sender: Sender's public key (address)
            recipient: Recipient's public key (address)
            amount: Amount to transfer
            timestamp: Time when transaction was created (optional)
            signature: Transaction signature (optional)
        """
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.signature = signature
    
    def calculate_hash(self) -> str:
        """
        Calculate the hash of the transaction
        
        Returns:
            SHA-256 hash of the transaction
        """
        transaction_string = f"{self.sender}{self.recipient}{self.amount}{self.timestamp}"
        return hashlib.sha256(transaction_string.encode()).hexdigest()
    
    def sign_transaction(self, signing_key: nacl.signing.SigningKey):
        """
        Sign the transaction with the sender's private key
        
        Args:
            signing_key: The sender's private key
        """
        if self.sender == "0":  # Mining reward transaction doesn't need signature
            return
        
        transaction_hash = self.calculate_hash().encode()
        signed = signing_key.sign(transaction_hash)
        self.signature = base64.b64encode(signed.signature).decode('utf-8')
    
    def verify_signature(self) -> bool:
        """
        Verify the transaction signature
        
        Returns:
            True if signature is valid, False otherwise
        """
        # Mining reward transaction doesn't have a signature
        if self.sender == "0":
            return True
        
        # Check if we have a signature
        if not self.signature:
            return False
        
        try:
            # Decode the sender's public key
            verify_key = nacl.signing.VerifyKey(
                self.sender.encode(), 
                encoder=nacl.encoding.HexEncoder
            )
            
            # Verify the signature
            transaction_hash = self.calculate_hash().encode()
            signature_bytes = base64.b64decode(self.signature)
            verify_key.verify(transaction_hash, signature_bytes)
            return True
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the transaction to a dictionary
        
        Returns:
            Dictionary representation of the transaction
        """
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'timestamp': self.timestamp,
            'signature': self.signature
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Transaction':
        """
        Create a transaction from a dictionary
        
        Args:
            data: Dictionary representation of a transaction
            
        Returns:
            A Transaction instance
        """
        return Transaction(
            sender=data['sender'],
            recipient=data['recipient'],
            amount=data['amount'],
            timestamp=data['timestamp'],
            signature=data['signature']
        )
