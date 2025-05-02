import time
import threading
from typing import Optional, Callable
from blockchain import Blockchain
from wallet import Wallet

class Miner:
    """
    Handles the mining process for the EPNET blockchain.
    """
    
    def __init__(self, blockchain: Blockchain, wallet: Wallet):
        """
        Initialize the miner
        
        Args:
            blockchain: The blockchain to mine on
            wallet: The wallet to receive mining rewards
        """
        self.blockchain = blockchain
        self.wallet = wallet
        self.mining = False
        self.mining_thread: Optional[threading.Thread] = None
        self.callback: Optional[Callable] = None
        self.mining_reward_address: Optional[str] = None  # Custom address for mining rewards
        
    def start_mining(self, callback: Optional[Callable] = None, mining_reward_address: Optional[str] = None):
        """
        Start the mining process in a separate thread
        
        Args:
            callback: Optional callback function to call when a block is mined
            mining_reward_address: Optional address to receive mining rewards (defaults to wallet address)
        """
        if self.mining:
            return
        
        self.mining = True
        self.callback = callback
        
        # Set mining reward address if provided
        if mining_reward_address:
            self.mining_reward_address = mining_reward_address
        
        self.mining_thread = threading.Thread(target=self._mine_loop)
        self.mining_thread.daemon = True
        self.mining_thread.start()
    
    def stop_mining(self):
        """
        Stop the mining process
        """
        self.mining = False
        if self.mining_thread:
            self.mining_thread.join(timeout=1)
            self.mining_thread = None
    
    def _mine_loop(self):
        """
        The main mining loop that continuously mines new blocks
        """
        while self.mining:
            # Check if we have pending transactions
            if not self.blockchain.pending_transactions:
                time.sleep(1)
                continue
            
            # Mine a block
            print("Mining a new block...")
            start_time = time.time()
            
            # Mine the block using the specified reward address or fallback to wallet address
            reward_address = self.mining_reward_address if self.mining_reward_address else self.wallet.public_key
            mined_block = self.blockchain.mine_pending_transactions(reward_address)
            
            if not mined_block:
                print("Mining failed: Reached maximum supply")
                self.mining = False
                break
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            print(f"Block mined in {elapsed:.2f} seconds!")
            print(f"Block hash: {mined_block.hash}")
            
            # Call the callback if provided
            if self.callback:
                self.callback(mined_block)
            
            # Small delay to prevent CPU hogging
            time.sleep(0.1)
    
    def is_mining(self) -> bool:
        """
        Check if the miner is currently mining
        
        Returns:
            True if mining, False otherwise
        """
        return self.mining
