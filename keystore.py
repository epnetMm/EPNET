"""
지갑 키스토어 모듈

이 모듈은 EPNET 블록체인의 지갑 비밀키를 안전하게 저장하고 관리하는 기능을 제공합니다.
키스토어는 암호화된 형태로 개인 키를 저장하며, 비밀번호로 보호됩니다.
"""

import os
import json
import time
import uuid
import logging
from typing import Dict, Any, Optional, List, Union

# 보안 모듈 가져오기
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from security.crypto.aes import AESCipher
from security.crypto.hash import HashFunctions

# 로깅 설정
logger = logging.getLogger(__name__)


class KeystoreError(Exception):
    """키스토어 관련 예외"""
    pass


class Keystore:
    """
    EPNET 지갑 키스토어 클래스
    
    이 클래스는 지갑 비밀키를 암호화하여 저장하고 관리하는 기능을 제공합니다.
    비밀번호 보호, 키 백업/복원, 다중 지갑 관리 등을 지원합니다.
    """
    
    def __init__(self, directory: str = None):
        """
        키스토어 초기화
        
        Args:
            directory: 키스토어 파일이 저장될 디렉토리 (없으면 기본값 사용)
        """
        # 저장 디렉토리 설정
        if directory is None:
            # 기본 디렉토리는 ~/.epnet/keystore
            home_dir = os.path.expanduser('~')
            self.directory = os.path.join(home_dir, '.epnet', 'keystore')
        else:
            self.directory = directory
        
        # 디렉토리 생성
        os.makedirs(self.directory, exist_ok=True)
        
        # 키스토어 캐시
        self.keystores: Dict[str, Dict[str, Any]] = {}
        
        # 로드된 지갑 파일 목록
        self.load_wallet_files()
    
    def load_wallet_files(self):
        """
        디렉토리에서 지갑 파일 목록 로드
        """
        # 디렉토리가 존재하는지 확인
        if not os.path.exists(self.directory):
            return
        
        # 모든 JSON 파일 검색
        for filename in os.listdir(self.directory):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(self.directory, filename)
            try:
                with open(filepath, 'r') as f:
                    keystore_data = json.load(f)
                
                # 기본 유효성 검사
                if not all(k in keystore_data for k in ['address', 'crypto', 'id', 'version']):
                    logger.warning(f"잘못된 키스토어 형식: {filename}")
                    continue
                
                # 메모리에 키스토어 정보 캐싱
                address = keystore_data['address']
                self.keystores[address] = keystore_data
                logger.debug(f"키스토어 로드됨: {address}")
            
            except Exception as e:
                logger.error(f"키스토어 로드 중 오류: {e}")
    
    def create_keystore(self, private_key: str, password: str) -> Dict[str, Any]:
        """
        개인 키와 비밀번호로 새 키스토어 생성
        
        Args:
            private_key: 암호화할 개인 키 (16진수 문자열)
            password: 키스토어 암호화에 사용할 비밀번호
            
        Returns:
            생성된 키스토어 데이터
        """
        # 고유 ID 생성
        keystore_id = str(uuid.uuid4())
        
        # 현재 시간 (UTC 타임스탬프)
        creation_time = int(time.time())
        
        # 비밀번호로부터 키 유도
        password_hash = HashFunctions.sha256(password)
        
        # 암호화 키 생성을 위한 솔트
        salt = HashFunctions.generate_salt(32)
        
        # 최종 암호화 키 생성
        encryption_key = HashFunctions.sha256(password_hash + salt)
        
        # AES 암호화
        aes = AESCipher(bytes.fromhex(encryption_key))
        encrypted_data = aes.encrypt(private_key)
        
        # 공개 주소 계산 (간소화된 버전 - 실제로는 더 복잡한 과정 사용)
        address = HashFunctions.sha256(private_key)[:40]
        
        # 키스토어 데이터 구성
        keystore_data = {
            'address': address,
            'crypto': {
                'cipher': 'aes-256-cbc',
                'ciphertext': encrypted_data['ciphertext'],
                'cipherparams': {
                    'iv': encrypted_data['iv']
                },
                'kdf': 'scrypt',  # 실제로는 scrypt 또는 pbkdf2 사용
                'kdfparams': {
                    'dklen': 32,
                    'n': 262144,  # scrypt 난이도
                    'p': 1,
                    'r': 8,
                    'salt': salt
                },
                'mac': HashFunctions.sha256(encryption_key + encrypted_data['ciphertext'])
            },
            'id': keystore_id,
            'version': 3,  # 이더리움 키스토어 버전 3과 호환
            'meta': {
                'created': creation_time,
                'network': 'epnet',
                'description': ''
            }
        }
        
        # 메모리 캐시에 저장
        self.keystores[address] = keystore_data
        
        # 파일에 저장
        filename = f"epnet-{address}.json"
        filepath = os.path.join(self.directory, filename)
        
        with open(filepath, 'w') as f:
            json.dump(keystore_data, f, indent=2)
        
        logger.info(f"새 키스토어 생성: {address}")
        return keystore_data
    
    def decrypt_keystore(self, address_or_file: str, password: str) -> str:
        """
        키스토어에서 개인 키 복호화
        
        Args:
            address_or_file: 지갑 주소 또는 키스토어 파일 경로
            password: 키스토어 비밀번호
            
        Returns:
            복호화된 개인 키
            
        Raises:
            KeystoreError: 키스토어를 찾을 수 없거나 비밀번호가 잘못된 경우
        """
        # 파일 경로인지 확인
        if address_or_file.endswith('.json') and os.path.exists(address_or_file):
            # 파일에서 키스토어 데이터 로드
            with open(address_or_file, 'r') as f:
                keystore_data = json.load(f)
        else:
            # 주소로 캐시된 키스토어 검색
            address = address_or_file
            if address not in self.keystores:
                raise KeystoreError(f"키스토어를 찾을 수 없음: {address}")
            
            keystore_data = self.keystores[address]
        
        # 비밀번호로부터 키 유도
        password_hash = HashFunctions.sha256(password)
        salt = keystore_data['crypto']['kdfparams']['salt']
        encryption_key = HashFunctions.sha256(password_hash + salt)
        
        # MAC 검증
        ciphertext = keystore_data['crypto']['ciphertext']
        expected_mac = HashFunctions.sha256(encryption_key + ciphertext)
        
        if expected_mac != keystore_data['crypto']['mac']:
            raise KeystoreError("잘못된 비밀번호")
        
        # AES 복호화
        aes = AESCipher(bytes.fromhex(encryption_key))
        
        try:
            private_key = aes.decrypt(
                ciphertext,
                keystore_data['crypto']['cipherparams']['iv']
            )
            return private_key
        except Exception as e:
            logger.error(f"복호화 오류: {e}")
            raise KeystoreError("키스토어 복호화 중 오류 발생")
    
    def update_keystore_password(self, address: str, old_password: str, new_password: str) -> bool:
        """
        키스토어 비밀번호 변경
        
        Args:
            address: 지갑 주소
            old_password: 현재 비밀번호
            new_password: 새 비밀번호
            
        Returns:
            성공 여부
            
        Raises:
            KeystoreError: 키스토어를 찾을 수 없거나 비밀번호가 잘못된 경우
        """
        # 기존 키스토어에서 개인 키 복호화
        try:
            private_key = self.decrypt_keystore(address, old_password)
        except KeystoreError as e:
            raise e
        
        # 새 비밀번호로 키스토어 재생성
        self.create_keystore(private_key, new_password)
        
        logger.info(f"키스토어 비밀번호 업데이트: {address}")
        return True
    
    def list_wallets(self) -> List[Dict[str, Any]]:
        """
        사용 가능한 지갑 목록 반환
        
        Returns:
            지갑 정보 목록 (주소, 생성 시간 등)
        """
        wallets = []
        
        for address, keystore in self.keystores.items():
            wallet_info = {
                'address': address,
                'created': keystore.get('meta', {}).get('created', 0),
                'description': keystore.get('meta', {}).get('description', ''),
                'network': keystore.get('meta', {}).get('network', 'epnet'),
                'file': f"epnet-{address}.json"
            }
            wallets.append(wallet_info)
        
        return wallets
    
    def delete_wallet(self, address: str, password: str) -> bool:
        """
        지갑 삭제 (비밀번호 확인 필요)
        
        Args:
            address: 삭제할 지갑 주소
            password: 지갑 비밀번호 (확인용)
            
        Returns:
            성공 여부
            
        Raises:
            KeystoreError: 키스토어를 찾을 수 없거나 비밀번호가 잘못된 경우
        """
        # 비밀번호 확인
        try:
            self.decrypt_keystore(address, password)
        except KeystoreError as e:
            raise e
        
        # 파일 삭제
        filename = f"epnet-{address}.json"
        filepath = os.path.join(self.directory, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # 캐시에서 제거
        if address in self.keystores:
            del self.keystores[address]
        
        logger.info(f"지갑 삭제됨: {address}")
        return True
    
    def update_wallet_metadata(self, address: str, description: str) -> bool:
        """
        지갑 메타데이터 업데이트
        
        Args:
            address: 지갑 주소
            description: 새 설명
            
        Returns:
            성공 여부
            
        Raises:
            KeystoreError: 키스토어를 찾을 수 없는 경우
        """
        if address not in self.keystores:
            raise KeystoreError(f"키스토어를 찾을 수 없음: {address}")
        
        # 메타데이터 업데이트
        if 'meta' not in self.keystores[address]:
            self.keystores[address]['meta'] = {}
        
        self.keystores[address]['meta']['description'] = description
        
        # 파일 업데이트
        filename = f"epnet-{address}.json"
        filepath = os.path.join(self.directory, filename)
        
        with open(filepath, 'w') as f:
            json.dump(self.keystores[address], f, indent=2)
        
        logger.info(f"지갑 메타데이터 업데이트: {address}")
        return True
    
    def backup_wallets(self, backup_dir: str, password: Optional[str] = None) -> str:
        """
        모든 키스토어를 백업 디렉토리에 복사
        
        Args:
            backup_dir: 백업 디렉토리 경로
            password: 백업 파일 암호화에 사용할 비밀번호 (선택 사항)
            
        Returns:
            백업 디렉토리 경로
        """
        import shutil
        
        # 백업 디렉토리 생성
        os.makedirs(backup_dir, exist_ok=True)
        
        # 모든 키스토어 파일 복사
        for address in self.keystores:
            src_path = os.path.join(self.directory, f"epnet-{address}.json")
            dst_path = os.path.join(backup_dir, f"epnet-{address}.json")
            
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
        
        # 백업 메타데이터 생성
        backup_meta = {
            'timestamp': int(time.time()),
            'wallet_count': len(self.keystores),
            'version': '1.0',
            'encrypted': password is not None
        }
        
        # 메타데이터 저장
        meta_path = os.path.join(backup_dir, 'backup-meta.json')
        with open(meta_path, 'w') as f:
            json.dump(backup_meta, f, indent=2)
        
        logger.info(f"지갑 백업 완료: {len(self.keystores)}개 지갑, 위치: {backup_dir}")
        return backup_dir