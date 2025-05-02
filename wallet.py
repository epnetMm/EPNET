import nacl.signing
import nacl.encoding
import json
import os
import logging
import hashlib
import time
from typing import Dict, Tuple, Any, Optional, List, Union
from transaction import Transaction

# 지갑 관리 모듈 가져오기 (경로가 추가되면 수정 필요)
try:
    from wallet.management.wallet_manager import WalletManager, WalletManagerError
except ImportError:
    # 개발 중이거나 단순 구조에서는 기본 지갑 사용
    WalletManager = None
    WalletManagerError = Exception

class Wallet:
    """
    Represents a wallet in the EPNET blockchain.
    Each wallet contains:
    - Private key
    - Public key (used as the wallet address)
    """
    
    # 최대 관리 가능한 지갑 수
    MAX_WALLETS = 5
    
    def __init__(self, private_key: Optional[str] = None):
        """
        Initialize a wallet, either with a provided private key or by generating a new one
        
        Args:
            private_key: Optional hex-encoded private key string
        """
        if private_key:
            # Convert hex string to bytes
            key_bytes = bytes.fromhex(private_key)
            self.signing_key = nacl.signing.SigningKey(key_bytes)
        else:
            # Generate a new random key
            self.signing_key = nacl.signing.SigningKey.generate()
        
        # Get the verify key (public key)
        self.verify_key = self.signing_key.verify_key
        
        # 향상된 지갑 관리 시스템이 있는지 확인
        self.wallet_manager = WalletManager() if WalletManager else None
    
    @property
    def private_key(self) -> str:
        """
        Get the private key as a hex string
        
        Returns:
            Hex-encoded private key
        """
        return self.signing_key.encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    
    @property
    def public_key(self) -> str:
        """
        Get the public key as a hex string (this serves as the wallet address)
        
        Returns:
            Hex-encoded public key
        """
        return self.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    
    @property
    def address(self) -> str:
        """
        Get the wallet address (public key)
        
        Returns:
            Wallet address
        """
        return self.public_key
    
    def create_transaction(self, recipient: str, amount: float) -> Transaction:
        """
        Create and sign a new transaction
        
        Args:
            recipient: Recipient's public key (address)
            amount: Amount to transfer
            
        Returns:
            A signed Transaction
        """
        transaction = Transaction(self.public_key, recipient, amount)
        transaction.sign_transaction(self.signing_key)
        return transaction
    
    def save_to_file(self, filename: str, password: Optional[str] = None):
        """
        Save the wallet to a file
        
        Args:
            filename: Path to save the wallet to
            password: Optional password for encryption
            
        Returns:
            True if successful, False otherwise
        """
        from config import ensure_data_directory
        
        # 데이터 디렉토리 확인
        ensure_data_directory()
        
        # 상대 경로를 절대 경로로 변환
        if not os.path.isabs(filename):
            from config import DATA_DIR
            filename = os.path.join(DATA_DIR, filename)
        
        if password and self.wallet_manager:
            # 향상된 관리 시스템이 있으면 암호화된 저장 사용
            try:
                self.wallet_manager.create_wallet(password, description="자동 생성된 지갑")
                logging.info(f"향상된 지갑 관리자를 사용하여 저장되었습니다")
                logging.info(f"월렛 주소: {self.public_key}")
                return True
            except WalletManagerError as e:
                logging.error(f"향상된 지갑 저장 중 오류: {e}")
                # 기본 저장 방식으로 폴백
        
        # 기본 저장 방식
        data = {
            'private_key': self.private_key,
            'public_key': self.public_key
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info(f"월렛이 저장되었습니다: {filename}")
            logging.info(f"월렛 주소: {self.public_key}")
            return True
        except Exception as e:
            logging.error(f"월렛 저장 중 오류: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filename: str, password: Optional[str] = None) -> 'Wallet':
        """
        Load a wallet from a file
        
        Args:
            filename: Path to load the wallet from
            password: Optional password for decryption
            
        Returns:
            Wallet instance
        """
        from config import ensure_data_directory
        
        # 데이터 디렉토리 확인
        ensure_data_directory()
        
        # 상대 경로를 절대 경로로 변환
        if not os.path.isabs(filename):
            from config import DATA_DIR
            filename = os.path.join(DATA_DIR, filename)
        
        # 향상된 관리 시스템이 있으면 시도
        if password and WalletManager:
            try:
                wallet_manager = WalletManager()
                
                # 메인 지갑 가져오기
                main_wallet = wallet_manager.get_main_wallet()
                if main_wallet:
                    address = main_wallet['address']
                    private_key = wallet_manager.get_private_key(address, password)
                    wallet = cls(private_key=private_key)
                    logging.info(f"향상된 지갑 관리자로부터 로드되었습니다")
                    logging.info(f"월렛 주소: {wallet.public_key}")
                    return wallet
            except Exception as e:
                logging.error(f"향상된 지갑 로드 중 오류: {e}")
                # 기본 로드 방식으로 폴백
        
        # 기본 로드 방식
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                wallet = cls(private_key=data['private_key'])
                logging.info(f"월렛이 로드되었습니다: {filename}")
                logging.info(f"월렛 주소: {wallet.public_key}")
                return wallet
            else:
                # 월렛 파일이 없는 경우 새 월렛 생성
                wallet = cls()
                wallet.save_to_file(filename, password)
                logging.info(f"새 월렛이 생성되었습니다: {filename}")
                return wallet
        except Exception as e:
            # 로드 중 오류 발생시 새 월렛 생성
            logging.error(f"월렛 로드 중 오류, 새 월렛을 생성합니다: {e}")
            wallet = cls()
            wallet.save_to_file(filename, password)
            return wallet
    
    @classmethod
    def recover_wallet(cls, private_key: str, password: Optional[str] = None) -> 'Wallet':
        """
        개인키로부터 지갑 복구
        
        Args:
            private_key: 개인키 (16진수 문자열)
            password: 선택적 비밀번호 (향상된 관리 시스템에 저장할 경우)
            
        Returns:
            복구된 지갑 인스턴스
        """
        wallet = cls(private_key=private_key)
        
        # 향상된 관리 시스템이 있고 비밀번호가 제공된 경우 저장
        if password and WalletManager:
            try:
                wallet_manager = WalletManager()
                wallet_manager.import_wallet(private_key, password, description="복구된 지갑")
                logging.info(f"지갑이 복구되어 향상된 지갑 관리자에 저장되었습니다")
            except WalletManagerError as e:
                logging.error(f"복구된 지갑 저장 중 오류: {e}")
        
        logging.info(f"지갑이 복구되었습니다. 주소: {wallet.public_key}")
        return wallet
    
    def to_dict(self) -> Dict[str, str]:
        """
        Convert the wallet to a dictionary
        
        Returns:
            Dictionary representation of the wallet
        """
        return {
            'private_key': self.private_key,
            'public_key': self.public_key
        }
    
    # 향상된 지갑 관리 기능들
    
    def get_all_wallets(self) -> List[Dict[str, Any]]:
        """
        Get all managed wallets
        
        Returns:
            List of wallet information
        """
        if not self.wallet_manager:
            # 향상된 관리 시스템이 없으면 현재 지갑만 반환
            return [{
                'address': self.public_key,
                'description': '기본 지갑',
                'created_at': int(time.time())
            }]
        
        return self.wallet_manager.get_wallets()
    
    def create_new_wallet(self, password: str, description: str = "") -> Dict[str, Any]:
        """
        Create a new wallet
        
        Args:
            password: Password for encryption
            description: Optional wallet description
            
        Returns:
            New wallet information
            
        Raises:
            Exception: If wallet creation fails
        """
        if not self.wallet_manager:
            raise Exception("향상된 지갑 관리 시스템을 사용할 수 없습니다")
        
        return self.wallet_manager.create_wallet(password, description)
    
    def import_wallet_from_key(self, private_key: str, password: str, description: str = "") -> Dict[str, Any]:
        """
        Import a wallet from private key
        
        Args:
            private_key: Wallet private key
            password: Password for encryption
            description: Optional wallet description
            
        Returns:
            Imported wallet information
            
        Raises:
            Exception: If wallet import fails
        """
        if not self.wallet_manager:
            raise Exception("향상된 지갑 관리 시스템을 사용할 수 없습니다")
        
        return self.wallet_manager.import_wallet(private_key, password, description)
    
    def set_active_wallet(self, address: str, password: str) -> bool:
        """
        Set the active wallet
        
        Args:
            address: Wallet address to set as active
            password: Password for verification
            
        Returns:
            True if successful
            
        Raises:
            Exception: If setting active wallet fails
        """
        if not self.wallet_manager:
            raise Exception("향상된 지갑 관리 시스템을 사용할 수 없습니다")
        
        # 비밀번호 확인을 위해 개인키 가져오기 시도
        self.wallet_manager.get_private_key(address, password)
        
        # 메인 지갑으로 설정
        self.wallet_manager.set_main_wallet(address)
        
        # 현재 지갑 업데이트
        private_key = self.wallet_manager.get_private_key(address, password)
        self.signing_key = nacl.signing.SigningKey(bytes.fromhex(private_key))
        self.verify_key = self.signing_key.verify_key
        
        return True
    
    def backup_wallets(self, backup_dir: Optional[str] = None) -> str:
        """
        Backup all wallets
        
        Args:
            backup_dir: Optional backup directory
            
        Returns:
            Backup directory path
            
        Raises:
            Exception: If backup fails
        """
        if not self.wallet_manager:
            raise Exception("향상된 지갑 관리 시스템을 사용할 수 없습니다")
        
        return self.wallet_manager.backup_wallets(backup_dir)
    
    def remove_wallet(self, address: str, password: str) -> bool:
        """
        Remove a wallet
        
        Args:
            address: Wallet address to remove
            password: Password for verification
            
        Returns:
            True if successful
            
        Raises:
            Exception: If wallet removal fails
        """
        if not self.wallet_manager:
            raise Exception("향상된 지갑 관리 시스템을 사용할 수 없습니다")
        
        return self.wallet_manager.delete_wallet(address, password)
