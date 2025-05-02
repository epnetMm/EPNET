"""
EPNET 블록체인 설정 관리

이 모듈은 EPNET 블록체인의 중요 설정과 매개변수를 관리합니다.
"""

import os
import json
import logging
from typing import Dict, List, Any

# 블록체인 기본 설정
MINING_REWARD = 50  # 초기 채굴 보상
MAX_SUPPLY = 210_000_000_000  # EP 최대 발행량
DIFFICULTY = 4  # 작업증명 난이도 (앞에 오는 0의 개수)
DIFFICULTY_ADJUSTMENT_INTERVAL = 2016  # 난이도 조정 간격 (블록 수)
TARGET_TIME_PER_BLOCK = 600  # 목표 블록 생성 시간 (초)
HALVING_INTERVAL = 210000  # 보상 반감기 간격 (블록 수)

# 네트워크 설정
DEFAULT_PORT = 5000  # 기본 P2P 네트워크 포트
DEFAULT_HOST = '0.0.0.0'  # 기본 호스트 주소
SEED_NODES = [  # 기본 시드 노드 목록
    "https://EpNeT-MOBILE.replit.app",
    # 아래에 공개 노드 추가 가능
]

# 파일 경로 설정
DATA_DIR = os.path.join(os.path.expanduser('~'), '.epnet')  # 데이터 디렉토리
BLOCKCHAIN_FILE = os.path.join(DATA_DIR, 'blockchain.json')  # 블록체인 저장 파일
WALLET_FILE = os.path.join(DATA_DIR, 'wallet.json')  # 지갑 저장 파일
PEERS_FILE = os.path.join(DATA_DIR, 'peers.json')  # 피어 목록 저장 파일
SEED_NODES_FILE = os.path.join(DATA_DIR, 'seed_nodes.json')  # 시드 노드 저장 파일

# 로깅 설정
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = os.path.join(DATA_DIR, 'epnet.log')  # 로그 파일 경로

def ensure_data_directory():
    """
    데이터 디렉토리가 존재하는지 확인하고, 없으면 생성합니다.
    이 함수는 블록체인 상태를 로컬에 저장하기 위해 필요합니다.
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_config(config_name: str, data: Any):
    """
    설정 데이터를 파일에 저장합니다.
    
    Args:
        config_name: 설정 이름 (파일 경로)
        data: 저장할 데이터
    """
    ensure_data_directory()
    with open(config_name, 'w') as f:
        json.dump(data, f, indent=2)

def load_config(config_name: str, default=None) -> Any:
    """
    설정 데이터를 파일에서 로드합니다.
    
    Args:
        config_name: 설정 이름 (파일 경로)
        default: 파일이 없을 경우 반환할 기본값
        
    Returns:
        로드된 설정 데이터 또는 기본값
    """
    ensure_data_directory()
    if os.path.exists(config_name):
        try:
            with open(config_name, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"설정 파일 로드 중 오류: {e}")
    
    return default

def setup_logging():
    """
    로깅 설정을 초기화합니다.
    """
    ensure_data_directory()
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )