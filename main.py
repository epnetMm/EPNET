from app import app
from config import setup_logging, WALLET_FILE, DATA_DIR, SEED_NODES_FILE

# 로깅 설정
setup_logging()

def initialize_blockchain():
    """
    EPNET 블록체인 초기화 및 시작
    이 함수는 run.py에서 호출됩니다.
    """
    # run.py에서 초기화 작업을 수행합니다
    from run import initialize_blockchain as init_blockchain
    return init_blockchain()

# 워크플로우가 gunicorn을 사용해 main.py:app을 실행하도록 설정되어 있습니다.
# 초기화는 app.py에서 자동으로 호출됩니다.
