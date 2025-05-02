import hashlib
import json
import time
import re
import urllib.parse
from typing import Any

def get_timestamp() -> float:
    """
    Get the current timestamp
    
    Returns:
        Current time as a float
    """
    return time.time()

def hash_string(string: str) -> str:
    """
    Create a SHA-256 hash of a string
    
    Args:
        string: String to hash
        
    Returns:
        SHA-256 hash of the string
    """
    return hashlib.sha256(string.encode()).hexdigest()

def parse_url(url: str) -> urllib.parse.ParseResult:
    """
    Parse a URL
    
    Args:
        url: URL to parse
        
    Returns:
        Parsed URL object
    """
    # Add http:// if no protocol is specified
    if not re.match(r'^https?://', url):
        url = f'http://{url}'
    
    return urllib.parse.urlparse(url)

def format_timestamp(timestamp: float) -> str:
    """
    Format a timestamp as a human-readable string
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Formatted timestamp string
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

def validate_address(address: str) -> bool:
    """
    Validate that an address is in the correct format
    
    Args:
        address: Address to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Addresses are hex strings of public keys
    if address == "0":  # Special case for mining rewards
        return True
    
    if not re.match(r'^[0-9a-fA-F]{64}$', address):
        return False
    
    return True

def calculate_hash_difficulty(hash_string: str) -> int:
    """
    Calculate the proof-of-work difficulty (number of leading zeros) of a hash
    
    Args:
        hash_string: Hash to check
        
    Returns:
        Number of leading zeros
    """
    difficulty = 0
    for char in hash_string:
        if char != '0':
            break
        difficulty += 1
    
    return difficulty
