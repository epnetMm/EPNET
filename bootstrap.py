"""
EPNET 블록체인 부트스트랩 모듈

이 모듈은 EPNET 블록체인의 부팅 및 초기화를 담당합니다.
제네시스 블록 생성, 네트워크 연결 등 블록체인 시작에 필요한 작업을 수행합니다.
"""

import os
import sys
import json
import time
import logging
import socket
import threading
import argparse
from typing import Dict, Any, Optional, List, Tuple

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 경로 추가
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# 필요한 모듈 임포트
from config import ensure_data_directory, DATA_DIR
from wallet import Wallet
from transaction import Transaction
from block import Block
from blockchain import Blockchain
from node import Node
try:
    from network.discovery.bootstrap import BootstrapNodeManager
    from network.protocol.peer_protocol import PeerProtocol
    from network.synchronization.chain_sync import ChainSynchronizer
    from core.storage.persistence import BlockchainStorage
    ADVANCED_MODULES = True
except ImportError:
    logger.warning("고급 네트워크 모듈을 찾을 수 없습니다. 기본 기능으로 계속합니다.")
    ADVANCED_MODULES = False


class BootstrapError(Exception):
    """부트스트랩 관련 예외"""
    pass


class EPNETBootstrap:
    """
    EPNET 블록체인 부트스트래퍼
    
    이 클래스는 블록체인 노드의 초기화, 제네시스 블록 생성, 네트워크 연결 등을
    관리합니다.
    """
    
    # 기본 설정
    DEFAULT_PORT = 5000
    MAX_SUPPLY = 210000000000  # 최대 발행량 (2100억 EP)
    GENESIS_REWARD = 50000000  # 제네시스 보상 (5천만 EP)
    
    def __init__(self, 
                 data_dir: Optional[str] = None, 
                 port: int = DEFAULT_PORT,
                 is_bootstrap_node: bool = False):
        """
        부트스트래퍼 초기화
        
        Args:
            data_dir: 데이터 디렉토리 (없으면 기본값 사용)
            port: 서버 포트
            is_bootstrap_node: 부트스트랩 노드 여부
        """
        self.data_dir = data_dir or DATA_DIR
        self.port = port
        self.is_bootstrap_node = is_bootstrap_node
        
        # 데이터 디렉토리 확인
        ensure_data_directory()
        
        # 컴포넌트
        self.wallet = None
        self.blockchain = None
        self.node = None
        
        # 고급 네트워크 컴포넌트
        self.storage = None
        self.bootstrap_manager = None
        self.peer_protocol = None
        self.chain_sync = None
        
        # 초기화 상태
        self.is_initialized = False
        self.genesis_created = False
    
    def initialize(self, create_genesis: bool = False, 
                  connect_peers: bool = True) -> bool:
        """
        블록체인 초기화
        
        Args:
            create_genesis: 제네시스 블록 생성 여부
            connect_peers: 피어 연결 여부
            
        Returns:
            성공 여부
        """
        try:
            # 이미 초기화되었는지 확인
            if self.is_initialized:
                return True
            
            logger.info("EPNET 블록체인 초기화 중...")
            
            # 지갑 초기화
            self._init_wallet()
            
            # 스토리지 초기화 (고급 모듈이 있는 경우)
            if ADVANCED_MODULES:
                self.storage = BlockchainStorage(self.data_dir)
            
            # 블록체인 초기화
            self._init_blockchain()
            
            # 제네시스 블록 생성 (필요한 경우)
            genesis_exists = self.blockchain.get_height() > 0
            if not genesis_exists and create_genesis:
                self._create_genesis_block()
            
            # 네트워크 연결 (필요한 경우)
            if connect_peers:
                self._init_network()
            
            # 초기화 완료
            self.is_initialized = True
            logger.info("EPNET 블록체인이 성공적으로 초기화되었습니다.")
            
            return True
        
        except Exception as e:
            logger.error(f"블록체인 초기화 중 오류: {e}")
            return False
    
    def _init_wallet(self):
        """
        지갑 초기화
        """
        wallet_file = os.path.join(self.data_dir, 'wallet.json')
        self.wallet = Wallet.load_from_file(wallet_file)
        logger.info(f"지갑이 로드되었습니다. 주소: {self.wallet.public_key}")
    
    def _init_blockchain(self):
        """
        블록체인 초기화
        """
        # 스토리지를 사용하는 고급 모드
        if ADVANCED_MODULES and self.storage:
            blocks, state = self.storage.load_blocks()
            
            # 블록체인 생성
            self.blockchain = Blockchain()
            
            # 저장된 블록이 있는 경우
            if blocks:
                for block_data in blocks:
                    block = Block.from_dict(block_data)
                    self.blockchain.add_block(block, validate=False)
                
                logger.info(f"저장된 블록체인이 로드되었습니다. 높이: {self.blockchain.get_height()}")
            else:
                logger.info("저장된 블록이 없습니다. 새 블록체인을 초기화합니다.")
        
        # 기본 모드
        else:
            self.blockchain = Blockchain()
            logger.info("새 블록체인이 초기화되었습니다.")
    
    def _init_network(self):
        """
        네트워크 초기화
        """
        try:
            # 노드 ID 생성
            node_id = self.wallet.public_key
            
            # 고급 네트워크 모듈 사용
            if ADVANCED_MODULES:
                # 부트스트랩 노드 관리자 초기화
                self.bootstrap_manager = BootstrapNodeManager(
                    data_dir=self.data_dir,
                    is_bootstrap=self.is_bootstrap_node,
                    port=self.port
                )
                
                # 피어 프로토콜 초기화
                self.peer_protocol = PeerProtocol(
                    node_id=node_id,
                    port=self.port,
                    blockchain=self.blockchain
                )
                
                # 체인 동기화 관리자 초기화
                self.chain_sync = ChainSynchronizer(
                    blockchain=self.blockchain,
                    peer_protocol=self.peer_protocol
                )
                
                # 각 컴포넌트 시작
                self.bootstrap_manager.start()
                self.peer_protocol.start()
                self.chain_sync.start()
                
                # 부트스트랩 노드에 연결
                bootstrap_nodes = self.bootstrap_manager.get_bootstrap_nodes()
                for node_addr in bootstrap_nodes:
                    self.peer_protocol.add_peer(node_addr)
                
                logger.info(f"고급 네트워크 시스템이 초기화되었습니다. {len(bootstrap_nodes)}개의 부트스트랩 노드에 연결.")
            
            # 기본 네트워크 모듈 사용
            else:
                # 기본 노드 초기화
                self.node = Node(
                    blockchain=self.blockchain,
                    node_id=node_id,
                    port=self.port
                )
                
                # 기본 부트스트랩 노드에 연결
                self.node.register_node("223.38.181.27:5000")  # 기본 부트스트랩 노드
                
                logger.info("기본 네트워크 시스템이 초기화되었습니다.")
        
        except Exception as e:
            logger.error(f"네트워크 초기화 중 오류: {e}")
            raise
    
    def _create_genesis_block(self):
        """
        제네시스 블록 생성
        """
        if self.blockchain.get_height() > 0:
            logger.warning("제네시스 블록이 이미 존재합니다.")
            return
        
        logger.info("제네시스 블록 생성 중...")
        
        # 제네시스 트랜잭션 생성 (코인베이스)
        coinbase_tx = Transaction(
            sender="0",  # 코인베이스 트랜잭션의 발신자는 "0"
            recipient=self.wallet.public_key,  # 보상은 현재 지갑으로
            amount=self.GENESIS_REWARD
        )
        
        # 서명 없이 직접 ID 설정 (제네시스 블록의 특수 처리)
        coinbase_tx.transaction_id = "genesis_transaction"
        
        # 제네시스 블록 생성
        genesis_block = Block(
            index=0,
            transactions=[coinbase_tx],
            timestamp=time.time(),
            previous_hash="0"  # 제네시스 블록은 이전 해시가 "0"
        )
        
        # 블록 채굴
        genesis_block.mine_block()
        
        # 블록체인에 추가
        self.blockchain.add_block(genesis_block)
        
        # 블록 저장 (고급 모듈)
        if ADVANCED_MODULES and self.storage:
            self.storage.save_block(genesis_block.to_dict())
        
        self.genesis_created = True
        logger.info(f"제네시스 블록이 생성되었습니다. 해시: {genesis_block.hash}")
    
    def start(self):
        """
        블록체인 노드 시작
        """
        # 초기화 확인
        if not self.is_initialized:
            self.initialize(create_genesis=True, connect_peers=True)
        
        # 노드 시작
        if ADVANCED_MODULES:
            # 이미 초기화 과정에서 시작되었으므로 추가 조치 불필요
            logger.info(f"EPNET 블록체인 노드가 활성화되었습니다. 포트: {self.port}")
            
            # 네트워크 연결 상태 출력
            if self.peer_protocol:
                active_peers = len(self.peer_protocol.active_peers)
                total_peers = len(self.peer_protocol.peers)
                logger.info(f"활성 피어: {active_peers}/{total_peers}")
        else:
            # 기본 노드 시작
            if self.node:
                logger.info(f"EPNET 블록체인 노드가 활성화되었습니다. 포트: {self.port}")
    
    def stop(self):
        """
        블록체인 노드 중지
        """
        # 고급 모듈
        if ADVANCED_MODULES:
            # 각 컴포넌트 중지
            if self.chain_sync:
                self.chain_sync.stop()
            
            if self.peer_protocol:
                self.peer_protocol.stop()
            
            if self.bootstrap_manager:
                self.bootstrap_manager.stop()
            
            if self.storage:
                self.storage.close()
        
        # 기본 모듈
        elif self.node:
            # 정리 작업 (알 수 없음)
            pass
        
        logger.info("EPNET 블록체인 노드가 중지되었습니다.")
    
    def get_status(self) -> Dict[str, Any]:
        """
        현재 상태 정보 반환
        
        Returns:
            상태 정보
        """
        status = {
            'initialized': self.is_initialized,
            'genesis_created': self.genesis_created,
            'blockchain_height': self.blockchain.get_height() if self.blockchain else 0,
            'wallet_address': self.wallet.public_key if self.wallet else None,
            'node_port': self.port
        }
        
        # 고급 모듈 상태 추가
        if ADVANCED_MODULES:
            if self.peer_protocol:
                status['active_peers'] = len(self.peer_protocol.active_peers)
                status['total_peers'] = len(self.peer_protocol.peers)
            
            if self.chain_sync:
                status['syncing'] = self.chain_sync.is_syncing
            
            if self.bootstrap_manager:
                status['bootstrap_mode'] = self.is_bootstrap_node
        
        return status


def confirm_or_create_genesis():
    """
    제네시스 블록 생성 여부 확인

    Returns:
        사용자 선택 결과
    """
    print("\n=== EPNET 블록체인 초기화 ===")
    print("블록체인을 시작하기 전에 제네시스 블록 생성 여부를 결정해야 합니다.")
    print("제네시스 블록은 블록체인의 첫 번째 블록으로, 최초의 코인을 생성합니다.")
    print("기존 네트워크에 참여하려면 제네시스 블록 생성 없이 계속하세요.")
    
    while True:
        choice = input("\n제네시스 블록을 생성하시겠습니까? (y/n): ").strip().lower()
        
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        else:
            print("올바른 선택이 아닙니다. 'y' 또는 'n'을 입력하세요.")


def main():
    """
    메인 함수
    """
    parser = argparse.ArgumentParser(description='EPNET 블록체인 네트워크 시작')
    parser.add_argument('--port', type=int, default=5000, help='서버 포트 (기본값: 5000)')
    parser.add_argument('--bootstrap', action='store_true', help='부트스트랩 노드로 실행')
    parser.add_argument('--genesis', action='store_true', help='제네시스 블록 생성')
    parser.add_argument('--no-confirm', action='store_true', help='사용자 확인 없이 진행')
    args = parser.parse_args()
    
    try:
        # 블록체인 부트스트랩 생성
        bootstrap = EPNETBootstrap(
            port=args.port,
            is_bootstrap_node=args.bootstrap
        )
        
        # 제네시스 블록 생성 여부 결정
        create_genesis = args.genesis
        
        # 사용자 확인이 필요한 경우
        if not args.no_confirm and not create_genesis:
            create_genesis = confirm_or_create_genesis()
        
        # 블록체인 초기화
        bootstrap.initialize(create_genesis=create_genesis)
        
        # 노드 시작
        bootstrap.start()
        
        # 상태 출력
        status = bootstrap.get_status()
        print("\n=== EPNET 블록체인 상태 ===")
        print(f"블록체인 높이: {status['blockchain_height']}")
        print(f"지갑 주소: {status['wallet_address']}")
        print(f"노드 포트: {status['node_port']}")
        
        if ADVANCED_MODULES:
            print(f"활성 피어: {status.get('active_peers', 0)}/{status.get('total_peers', 0)}")
            print(f"부트스트랩 모드: {status.get('bootstrap_mode', False)}")
        
        print("\nEPNET 블록체인이 실행 중입니다. 종료하려면 Ctrl+C를 누르세요.")
        
        # 메인 스레드 유지
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n사용자에 의해 종료되었습니다.")
        if 'bootstrap' in locals():
            bootstrap.stop()
    
    except Exception as e:
        print(f"\n오류 발생: {e}")
        if 'bootstrap' in locals():
            bootstrap.stop()
        
        sys.exit(1)


if __name__ == "__main__":
    main()