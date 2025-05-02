"""
지갑 관리 모듈

이 모듈은 EPNET 블록체인의 지갑을 관리하는 기능을 제공합니다.
최대 5개의 지갑 관리, 개인키 암호화 저장, 지갑 복구 등의 기능을 제공합니다.
"""

import os
import json
import time
import logging
import base64
from typing import Dict, List, Optional, Any, Union, Tuple

# 보안 모듈 가져오기
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from security.crypto.aes import AESCipher
from security.crypto.hash import HashFunctions
from wallet.keystore.keystore import Keystore

# 로깅 설정
logger = logging.getLogger(__name__)


class WalletManagerError(Exception):
    """지갑 관리 관련 예외"""
    pass


class WalletManager:
    """
    EPNET 지갑 관리 클래스
    
    이 클래스는 사용자 지갑의 생성, 관리, 백업, 복구 등의 기능을 제공합니다.
    최대 5개의 지갑을 관리할 수 있으며, 각 지갑의 개인키는 암호화되어 로컬에 저장됩니다.
    """
    
    MAX_WALLETS = 5  # 최대 지갑 개수
    
    def __init__(self, data_dir: str = None):
        """
        지갑 관리자 초기화
        
        Args:
            data_dir: 지갑 데이터가 저장될 디렉토리 (없으면 기본값 사용)
        """
        # 저장 디렉토리 설정
        if data_dir is None:
            # 기본 디렉토리는 ~/.epnet
            home_dir = os.path.expanduser('~')
            self.data_dir = os.path.join(home_dir, '.epnet')
        else:
            self.data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 키스토어 초기화
        self.keystore = Keystore(os.path.join(self.data_dir, 'keystore'))
        
        # 지갑 정보 파일 경로
        self.wallet_file = os.path.join(self.data_dir, 'wallet.json')
        
        # 지갑 정보 로드
        self.wallets = self._load_wallets()
        
        # 메인 지갑 주소 (기본값)
        self.main_address = None
        if self.wallets and 'main_address' in self.wallets:
            self.main_address = self.wallets['main_address']
    
    def _load_wallets(self) -> Dict[str, Any]:
        """
        지갑 정보 파일 로드
        
        Returns:
            지갑 정보 딕셔너리
        """
        if not os.path.exists(self.wallet_file):
            # 기본 지갑 정보 구조
            return {
                'wallets': [],
                'main_address': None,
                'last_updated': int(time.time())
            }
        
        try:
            with open(self.wallet_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"지갑 정보 로드 오류: {e}")
            # 오류 시 기본값 반환
            return {
                'wallets': [],
                'main_address': None,
                'last_updated': int(time.time())
            }
    
    def _save_wallets(self):
        """
        지갑 정보 파일 저장
        """
        # 저장 시간 업데이트
        self.wallets['last_updated'] = int(time.time())
        
        try:
            with open(self.wallet_file, 'w') as f:
                json.dump(self.wallets, f, indent=2)
            logger.info(f"월렛이 저장되었습니다: {self.wallet_file}")
        except Exception as e:
            logger.error(f"지갑 정보 저장 오류: {e}")
    
    def create_wallet(self, password: str, description: str = "") -> Dict[str, Any]:
        """
        새 지갑 생성
        
        Args:
            password: 지갑 비밀번호
            description: 지갑 설명 (선택 사항)
            
        Returns:
            생성된 지갑 정보
            
        Raises:
            WalletManagerError: 최대 지갑 개수 초과 시
        """
        # 최대 지갑 개수 확인
        existing_wallets = self.wallets.get('wallets', [])
        if len(existing_wallets) >= self.MAX_WALLETS:
            raise WalletManagerError(f"최대 지갑 개수({self.MAX_WALLETS}개)를 초과했습니다. 기존 지갑을 삭제하고 다시 시도하세요.")
        
        # 새 개인키 생성 (32바이트 랜덤 데이터)
        private_key = os.urandom(32).hex()
        
        # 지갑 주소 생성 (SHA-256 해시)
        address = HashFunctions.sha256(private_key)
        
        # 키스토어에 저장 (암호화)
        keystore_data = self.keystore.create_keystore(private_key, password)
        
        # 지갑 정보 생성
        wallet_info = {
            'address': address,
            'description': description,
            'created_at': int(time.time()),
            'keystore_id': keystore_data['id']
        }
        
        # 지갑 목록에 추가
        self.wallets.setdefault('wallets', []).append(wallet_info)
        
        # 첫 번째 지갑이면 메인 지갑으로 설정
        if len(self.wallets['wallets']) == 1:
            self.main_address = address
            self.wallets['main_address'] = address
        
        # 변경사항 저장
        self._save_wallets()
        
        logger.info(f"새 지갑 생성됨: {address}")
        return wallet_info
    
    def import_wallet(self, private_key: str, password: str, description: str = "") -> Dict[str, Any]:
        """
        개인키로 지갑 가져오기
        
        Args:
            private_key: 가져올 지갑의 개인키 (16진수 문자열)
            password: 지갑 비밀번호
            description: 지갑 설명 (선택 사항)
            
        Returns:
            가져온 지갑 정보
            
        Raises:
            WalletManagerError: 최대 지갑 개수 초과 또는 이미 있는 지갑인 경우
        """
        # 최대 지갑 개수 확인
        existing_wallets = self.wallets.get('wallets', [])
        if len(existing_wallets) >= self.MAX_WALLETS:
            raise WalletManagerError(f"최대 지갑 개수({self.MAX_WALLETS}개)를 초과했습니다. 기존 지갑을 삭제하고 다시 시도하세요.")
        
        # 지갑 주소 계산
        address = HashFunctions.sha256(private_key)
        
        # 이미 있는 지갑인지 확인
        for wallet in existing_wallets:
            if wallet['address'] == address:
                raise WalletManagerError(f"이미 가져온 지갑입니다: {address}")
        
        # 키스토어에 저장 (암호화)
        keystore_data = self.keystore.create_keystore(private_key, password)
        
        # 지갑 정보 생성
        wallet_info = {
            'address': address,
            'description': description,
            'created_at': int(time.time()),
            'imported': True,
            'keystore_id': keystore_data['id']
        }
        
        # 지갑 목록에 추가
        self.wallets.setdefault('wallets', []).append(wallet_info)
        
        # 첫 번째 지갑이면 메인 지갑으로 설정
        if len(self.wallets['wallets']) == 1:
            self.main_address = address
            self.wallets['main_address'] = address
        
        # 변경사항 저장
        self._save_wallets()
        
        logger.info(f"지갑 가져오기 완료: {address}")
        return wallet_info
    
    def get_private_key(self, address: str, password: str) -> str:
        """
        지갑 주소로 개인키 가져오기
        
        Args:
            address: 지갑 주소
            password: 지갑 비밀번호
            
        Returns:
            개인키 (16진수 문자열)
            
        Raises:
            WalletManagerError: 지갑을 찾을 수 없거나 비밀번호가 잘못된 경우
        """
        # 지갑 존재 확인
        wallet_info = None
        for wallet in self.wallets.get('wallets', []):
            if wallet['address'] == address:
                wallet_info = wallet
                break
        
        if wallet_info is None:
            raise WalletManagerError(f"지갑을 찾을 수 없음: {address}")
        
        # 키스토어에서 개인키 복호화
        try:
            return self.keystore.decrypt_keystore(address, password)
        except Exception as e:
            logger.error(f"개인키 복호화 오류: {e}")
            raise WalletManagerError("잘못된 비밀번호 또는 손상된 키스토어")
    
    def delete_wallet(self, address: str, password: str) -> bool:
        """
        지갑 삭제
        
        Args:
            address: 삭제할 지갑 주소
            password: 지갑 비밀번호 (확인용)
            
        Returns:
            성공 여부
            
        Raises:
            WalletManagerError: 지갑을 찾을 수 없거나 비밀번호가 잘못된 경우
        """
        # 개인키 복호화로 비밀번호 확인
        try:
            self.get_private_key(address, password)
        except WalletManagerError as e:
            raise e
        
        # 지갑 목록에서 제거
        wallet_index = None
        for i, wallet in enumerate(self.wallets.get('wallets', [])):
            if wallet['address'] == address:
                wallet_index = i
                break
        
        if wallet_index is not None:
            del self.wallets['wallets'][wallet_index]
        
        # 메인 지갑이면 다른 지갑으로 변경
        if self.main_address == address:
            if self.wallets['wallets']:
                # 있는 지갑 중 첫 번째로 변경
                self.main_address = self.wallets['wallets'][0]['address']
                self.wallets['main_address'] = self.main_address
            else:
                # 남은 지갑이 없으면 None으로 설정
                self.main_address = None
                self.wallets['main_address'] = None
        
        # 키스토어에서도 삭제
        try:
            self.keystore.delete_wallet(address, password)
        except Exception as e:
            logger.error(f"키스토어 삭제 오류: {e}")
        
        # 변경사항 저장
        self._save_wallets()
        
        logger.info(f"지갑 삭제됨: {address}")
        return True
    
    def set_main_wallet(self, address: str) -> bool:
        """
        메인 지갑 설정
        
        Args:
            address: 메인 지갑으로 설정할 주소
            
        Returns:
            성공 여부
            
        Raises:
            WalletManagerError: 지갑을 찾을 수 없는 경우
        """
        # 지갑 존재 확인
        wallet_exists = False
        for wallet in self.wallets.get('wallets', []):
            if wallet['address'] == address:
                wallet_exists = True
                break
        
        if not wallet_exists:
            raise WalletManagerError(f"지갑을 찾을 수 없음: {address}")
        
        # 메인 지갑 설정
        self.main_address = address
        self.wallets['main_address'] = address
        
        # 변경사항 저장
        self._save_wallets()
        
        logger.info(f"메인 지갑 설정: {address}")
        return True
    
    def update_wallet_description(self, address: str, description: str) -> bool:
        """
        지갑 설명 업데이트
        
        Args:
            address: 지갑 주소
            description: 새 설명
            
        Returns:
            성공 여부
            
        Raises:
            WalletManagerError: 지갑을 찾을 수 없는 경우
        """
        # 지갑 찾기
        wallet_found = False
        for wallet in self.wallets.get('wallets', []):
            if wallet['address'] == address:
                wallet['description'] = description
                wallet_found = True
                break
        
        if not wallet_found:
            raise WalletManagerError(f"지갑을 찾을 수 없음: {address}")
        
        # 키스토어 메타데이터도 업데이트
        try:
            self.keystore.update_wallet_metadata(address, description)
        except Exception as e:
            logger.error(f"키스토어 메타데이터 업데이트 오류: {e}")
        
        # 변경사항 저장
        self._save_wallets()
        
        logger.info(f"지갑 설명 업데이트: {address}")
        return True
    
    def get_wallets(self) -> List[Dict[str, Any]]:
        """
        모든 지갑 정보 반환
        
        Returns:
            지갑 정보 목록
        """
        return self.wallets.get('wallets', [])
    
    def get_main_wallet(self) -> Optional[Dict[str, Any]]:
        """
        메인 지갑 정보 반환
        
        Returns:
            메인 지갑 정보 또는 None
        """
        if not self.main_address:
            return None
        
        for wallet in self.wallets.get('wallets', []):
            if wallet['address'] == self.main_address:
                return wallet
        
        return None
    
    def change_wallet_password(self, address: str, old_password: str, new_password: str) -> bool:
        """
        지갑 비밀번호 변경
        
        Args:
            address: 지갑 주소
            old_password: 현재 비밀번호
            new_password: 새 비밀번호
            
        Returns:
            성공 여부
            
        Raises:
            WalletManagerError: 지갑을 찾을 수 없거나 비밀번호가 잘못된 경우
        """
        # 개인키 복호화로 비밀번호 확인
        try:
            private_key = self.get_private_key(address, old_password)
        except WalletManagerError as e:
            raise e
        
        # 새 비밀번호로 키스토어 업데이트
        try:
            self.keystore.update_keystore_password(address, old_password, new_password)
            logger.info(f"지갑 비밀번호 변경됨: {address}")
            return True
        except Exception as e:
            logger.error(f"비밀번호 변경 오류: {e}")
            raise WalletManagerError("비밀번호 변경 중 오류 발생")
    
    def backup_wallets(self, backup_dir: str = None) -> str:
        """
        모든 지갑 백업
        
        Args:
            backup_dir: 백업 디렉토리 (없으면 자동 생성)
            
        Returns:
            백업 디렉토리 경로
        """
        # 백업 디렉토리 설정
        if backup_dir is None:
            backup_dir = os.path.join(self.data_dir, 'backup', f"backup_{int(time.time())}")
        
        # 백업 디렉토리 생성
        os.makedirs(backup_dir, exist_ok=True)
        
        # 지갑 정보 파일 복사
        import shutil
        if os.path.exists(self.wallet_file):
            shutil.copy2(self.wallet_file, os.path.join(backup_dir, 'wallet.json'))
        
        # 키스토어 백업
        keystore_backup_dir = os.path.join(backup_dir, 'keystore')
        self.keystore.backup_wallets(keystore_backup_dir)
        
        logger.info(f"지갑 백업 완료: {backup_dir}")
        return backup_dir
    
    def export_wallet(self, address: str, password: str, export_format: str = 'json') -> str:
        """
        지갑 내보내기
        
        Args:
            address: 내보낼 지갑 주소
            password: 지갑 비밀번호
            export_format: 내보내기 형식 ('json', 'keystore' 등)
            
        Returns:
            내보낸 지갑 데이터 (형식에 따라 다름)
            
        Raises:
            WalletManagerError: 지갑을 찾을 수 없거나 비밀번호가 잘못된 경우
        """
        # 개인키 가져오기
        try:
            private_key = self.get_private_key(address, password)
        except WalletManagerError as e:
            raise e
        
        # 지갑 정보 찾기
        wallet_info = None
        for wallet in self.wallets.get('wallets', []):
            if wallet['address'] == address:
                wallet_info = wallet
                break
        
        if wallet_info is None:
            raise WalletManagerError(f"지갑을 찾을 수 없음: {address}")
        
        # 내보내기 형식에 따라 처리
        if export_format == 'json':
            # JSON 형식
            export_data = {
                'address': address,
                'private_key': private_key,
                'description': wallet_info.get('description', ''),
                'created_at': wallet_info.get('created_at', int(time.time())),
                'exported_at': int(time.time())
            }
            return json.dumps(export_data, indent=2)
        
        elif export_format == 'keystore':
            # 키스토어 파일 경로 반환
            keystore_path = os.path.join(self.keystore.directory, f"epnet-{address}.json")
            if os.path.exists(keystore_path):
                return keystore_path
            else:
                raise WalletManagerError(f"키스토어 파일을 찾을 수 없음: {address}")
        
        elif export_format == 'private_key':
            # 개인키만 반환
            return private_key
        
        else:
            raise WalletManagerError(f"지원되지 않는 내보내기 형식: {export_format}")