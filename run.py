#!/usr/bin/env python3
"""
EPNET 블록체인 시작 스크립트

이 스크립트는 EPNET 블록체인 노드를 시작하고 웹 인터페이스를 실행합니다.
실제 블록체인으로서 외부 의존성 없이 독립적으로 실행됩니다.
"""

import os
import sys
import time
import signal
import logging
import threading
import flask
import flask.logging
from typing import Optional

from config import setup_logging, WALLET_FILE, ensure_data_directory
from node import Node
from wallet import Wallet
from app import app

# 글로벌 변수
node = None
stop_event = threading.Event()

def signal_handler(sig, frame):
    """
    시그널 핸들러 (Ctrl+C 처리)
    """
    print("\n종료 신호를 받았습니다. 정리 중...")
    if node:
        node.stop()
    sys.exit(0)

def initialize_blockchain():
    """
    EPNET 블록체인 초기화 및 시작
    이 함수는 제네시스 블록을 생성하고 P2P 네트워크를 구성합니다.
    """
    global node
    
    # 디렉토리 확인
    ensure_data_directory()
    
    # 로깅 초기화
    setup_logging()
    
    try:
        # 시작 확인 요청
        first_run = not os.path.exists(WALLET_FILE)
        if first_run:
            print("\nEPNET 블록체인을 처음 실행합니다.")
            print("이 과정에서 블록체인 노드가 생성되고 네트워크에 연결됩니다.")
            
            while True:
                answer = input("계속하시겠습니까? (y/n): ").lower()
                if answer == 'y':
                    break
                elif answer == 'n':
                    print("블록체인 시작이 취소되었습니다.")
                    return False
                else:
                    print("'y' 또는 'n'으로 대답해 주세요.")
            
            # 월렛 생성
            wallet = Wallet()
            wallet.save_to_file(WALLET_FILE)
            logging.info(f"새 월렛이 생성되었습니다: {wallet.public_key}")
            print(f"새 월렛이 생성되었습니다. 주소: {wallet.public_key}")
        else:
            # 기존 월렛 로드
            wallet = Wallet.load_from_file(WALLET_FILE)
            logging.info(f"기존 월렛을 로드했습니다: {wallet.public_key}")
        
        # 노드 생성 및 시작
        node = Node(WALLET_FILE)
        node.start()
        
        # 노드 정보 출력
        print("\nEPNET 블록체인 노드가 시작되었습니다.")
        print(f"월렛 주소: {wallet.public_key}")
        
        # 블록체인 정보 출력
        blockchain_info = node.get_blockchain_info()
        print(f"현재 블록 수: {len(blockchain_info['chain'])}")
        print(f"현재 EP 유통량: {blockchain_info['current_supply']}")
        
        return True
    
    except Exception as e:
        logging.error(f"블록체인 초기화 오류: {e}")
        print(f"블록체인을 초기화할 수 없습니다: {e}")
        return False

def run_blockchain_node():
    """
    블록체인 노드를 실행하고 웹 인터페이스를 시작합니다.
    이 함수는 외부 서비스(gunicorn 등)에 의존하지 않고 독립적으로 실행됩니다.
    """
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    
    # 블록체인 초기화
    if not initialize_blockchain():
        return 1
    
    # 플라스크 앱 실행
    try:
        # 로깅 설정
        log = logging.getLogger('werkzeug')
        log.disabled = True
        app.logger.disabled = True
        
        # 앱 실행 (기본 포트: 5000)
        port = int(os.environ.get("PORT", 5000))
        print(f"\n웹 인터페이스가 시작되었습니다: http://localhost:{port}")
        print("Ctrl+C를 눌러 종료할 수 있습니다.")
        
        # 플라스크 앱 실행
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        
        return 0
    
    except Exception as e:
        logging.error(f"웹 인터페이스 시작 오류: {e}")
        print(f"웹 인터페이스를 시작할 수 없습니다: {e}")
        
        # 노드 정리
        if node:
            node.stop()
        
        return 1

if __name__ == "__main__":
    sys.exit(run_blockchain_node())