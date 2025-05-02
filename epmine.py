#!/usr/bin/env python3
"""
EPNET Blockchain Mining Tool

This script provides a command-line interface for mining EPNET cryptocurrency.
Usage: python epmine.py <wallet_address>
"""

import os
import sys
import time
import logging
import threading
import signal
from typing import Optional, Callable

from config import setup_logging, WALLET_FILE
from node import Node
from wallet import Wallet

# 로깅 설정
setup_logging()

# 글로벌 변수
mining_thread = None
stop_event = threading.Event()

def signal_handler(sig, frame):
    """
    시그널 핸들러 (Ctrl+C 처리)
    """
    print("\n채굴 종료 신호를 받았습니다. 정리 중...")
    if mining_thread and mining_thread.is_alive():
        stop_event.set()
        mining_thread.join(timeout=2)
    sys.exit(0)

def get_confirmation():
    """Get user confirmation to start mining."""
    print("\nEPNET 블록체인 마이닝을 시작하려고 합니다.")
    print("이 프로세스는 컴퓨터 자원을 사용하며 실제 EP 코인을 채굴합니다.")
    
    while True:
        answer = input("계속하시겠습니까? (y/n): ").lower()
        if answer == 'y':
            return True
        elif answer == 'n':
            return False
        else:
            print("'y' 또는 'n'으로 대답해 주세요.")

def start_mining(wallet_address: str, callback: Optional[Callable] = None):
    """Start the mining process and send rewards to the provided wallet address."""
    global mining_thread
    
    # 노드 초기화
    try:
        # 기존 월렛 사용 또는 새 월렛 생성
        wallet = Wallet.load_from_file(WALLET_FILE)
        
        # 노드 생성 및 시작
        node = Node(WALLET_FILE)
        node.start()
        
        logging.info(f"마이닝 시작: 보상 주소 = {wallet_address}")
        print(f"마이닝 시작 중... 보상은 {wallet_address}로 전송됩니다.")
        
        # 마이닝 콜백 함수
        def mining_callback(block):
            block_info = {
                "index": block.index,
                "hash": block.hash[:10] + "...",
                "transactions": len(block.transactions),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(block.timestamp))
            }
            
            print(f"\n새 블록 채굴 완료!")
            print(f"블록 번호: {block_info['index']}")
            print(f"블록 해시: {block_info['hash']}")
            print(f"포함된 거래: {block_info['transactions']} 개")
            print(f"타임스탬프: {block_info['timestamp']}")
            
            # 사용자 정의 콜백이 있으면 실행
            if callback:
                callback(block)
            
            # 종료 신호가 있는지 확인
            if stop_event.is_set():
                return False
            
            return True
        
        # 백그라운드 스레드에서 마이닝 시작
        def mining_worker():
            try:
                node.start_mining(wallet_address)
                while not stop_event.is_set():
                    time.sleep(1)
            except Exception as e:
                logging.error(f"마이닝 오류: {e}")
            finally:
                node.stop_mining()
                node.stop()
        
        # 이전 마이닝 스레드가 있으면 정리
        if mining_thread and mining_thread.is_alive():
            stop_event.set()
            mining_thread.join(timeout=2)
            stop_event.clear()
        
        # 마이닝 스레드 시작
        mining_thread = threading.Thread(target=mining_worker)
        mining_thread.daemon = True
        mining_thread.start()
        
        # Ctrl+C 핸들러 등록
        signal.signal(signal.SIGINT, signal_handler)
        
        return True
    
    except Exception as e:
        logging.error(f"마이닝 시작 오류: {e}")
        print(f"마이닝을 시작할 수 없습니다: {e}")
        return False

def main():
    """Main function to handle command line arguments and start mining."""
    if len(sys.argv) < 2:
        print("사용법: python epmine.py <wallet_address>")
        return 1
    
    wallet_address = sys.argv[1]
    
    # 사용자 확인 요청
    if not get_confirmation():
        print("마이닝이 취소되었습니다.")
        return 0
    
    # 마이닝 시작
    start_mining(wallet_address)
    
    # 메인 스레드는 계속 실행 상태 유지
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n마이닝이 중지되었습니다.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())