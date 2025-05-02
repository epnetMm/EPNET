import os
import json
import logging
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from werkzeug.middleware.proxy_fix import ProxyFix
import threading
import time

from blockchain import Blockchain
from transaction import Transaction
from block import Block
from wallet import Wallet
from node import Node
from utils import format_timestamp, validate_address
from config import setup_logging, WALLET_FILE, ensure_data_directory

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "epnet_development_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Ensure data directory exists
ensure_data_directory()

# Initialize the blockchain node
node = Node(WALLET_FILE)

# Start the node services
node.start()

# Routes for web interface
@app.route('/')
def index():
    """Render the home page with blockchain information"""
    blockchain_info = node.get_blockchain_info()
    wallet_info = node.get_wallet_info()
    
    # Get the latest blocks (last 5)
    latest_blocks = []
    for block in reversed(node.blockchain.chain[-5:]):
        block_info = {
            'index': block.index,
            'hash': block.hash,
            'timestamp': format_timestamp(block.timestamp),
            'transaction_count': len(block.transactions)
        }
        latest_blocks.append(block_info)
    
    # Get the latest pending transactions (last 5)
    pending_txs = []
    for tx in node.blockchain.pending_transactions[-5:]:
        tx_info = {
            'sender': tx.sender[:10] + '...' if len(tx.sender) > 10 else tx.sender,
            'recipient': tx.recipient[:10] + '...' if len(tx.recipient) > 10 else tx.recipient,
            'amount': tx.amount,
            'timestamp': format_timestamp(tx.timestamp)
        }
        pending_txs.append(tx_info)
    
    return render_template('index.html', 
                          blockchain_info=blockchain_info,
                          wallet_info=wallet_info,
                          latest_blocks=latest_blocks,
                          pending_transactions=pending_txs,
                          is_mining=node.miner.is_mining())

@app.route('/blockchain')
def blockchain_explorer():
    """Render the blockchain explorer page"""
    # Get all blocks with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    chain = node.blockchain.chain
    total_pages = (len(chain) + per_page - 1) // per_page
    
    blocks = []
    for block in chain[start_idx:end_idx]:
        block_info = {
            'index': block.index,
            'hash': block.hash,
            'previous_hash': block.previous_hash,
            'timestamp': format_timestamp(block.timestamp),
            'transaction_count': len(block.transactions),
            'nonce': block.nonce
        }
        blocks.append(block_info)
    
    return render_template('blockchain.html', 
                          blocks=blocks,
                          page=page,
                          total_pages=total_pages)

@app.route('/transactions')
def transactions():
    """Render the transactions page"""
    # Get transactions for the current wallet
    wallet_address = node.wallet.public_key
    wallet_transactions = node.blockchain.get_transactions_by_address(wallet_address)
    
    processed_txs = []
    for tx in wallet_transactions:
        # Determine if this is an incoming or outgoing transaction
        tx_type = 'incoming' if tx['recipient'] == wallet_address else 'outgoing'
        if tx['sender'] == '0' and tx['recipient'] == wallet_address:
            tx_type = 'mining_reward'
        
        processed_tx = {
            'type': tx_type,
            'sender': tx['sender'][:10] + '...' if len(tx['sender']) > 10 else tx['sender'],
            'recipient': tx['recipient'][:10] + '...' if len(tx['recipient']) > 10 else tx['recipient'],
            'amount': tx['amount'],
            'timestamp': format_timestamp(tx['timestamp'])
        }
        processed_txs.append(processed_tx)
    
    # Sort by timestamp (newest first)
    processed_txs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return render_template('transactions.html', 
                          transactions=processed_txs,
                          wallet_address=wallet_address,
                          wallet_balance=node.blockchain.get_balance(wallet_address))

@app.route('/wallet')
def wallet():
    """Render the wallet page"""
    wallet_info = node.get_wallet_info()
    return render_template('wallet.html', wallet_info=wallet_info)

@app.route('/create_transaction', methods=['POST'])
def create_transaction():
    """Create a new transaction"""
    try:
        recipient = request.form.get('recipient')
        amount = float(request.form.get('amount'))
        
        # Validate recipient address
        if not validate_address(recipient):
            flash('Invalid recipient address format', 'danger')
            return redirect(url_for('wallet'))
        
        # Validate amount
        if amount <= 0:
            flash('Amount must be greater than zero', 'danger')
            return redirect(url_for('wallet'))
        
        # Check if sender has enough balance
        sender_balance = node.blockchain.get_balance(node.wallet.public_key)
        if sender_balance < amount:
            flash(f'Insufficient balance. Your balance: {sender_balance} EP', 'danger')
            return redirect(url_for('wallet'))
        
        # Create and broadcast transaction
        result = node.create_transaction(recipient, amount)
        
        if result['status'] == 'success':
            flash('Transaction created successfully! It will be processed soon.', 'success')
        else:
            flash(f'Transaction failed: {result["message"]}', 'danger')
        
        return redirect(url_for('transactions'))
    except ValueError:
        flash('Invalid amount format', 'danger')
        return redirect(url_for('wallet'))
    except Exception as e:
        flash(f'Error creating transaction: {str(e)}', 'danger')
        return redirect(url_for('wallet'))

@app.route('/mine')
def mine():
    """Render the mining page"""
    return render_template('mine.html', 
                          is_mining=node.miner.is_mining(),
                          mining_reward=node.blockchain.mining_reward,
                          current_supply=node.blockchain.current_supply,
                          max_supply=node.blockchain.max_supply)

@app.route('/start_mining', methods=['POST'])
def start_mining():
    """Start the mining process"""
    if not node.miner.is_mining():
        node.start_mining()
        flash('Mining started!', 'success')
    else:
        flash('Mining is already running', 'info')
    
    return redirect(url_for('mine'))

@app.route('/stop_mining', methods=['POST'])
def stop_mining():
    """Stop the mining process"""
    if node.miner.is_mining():
        node.stop_mining()
        flash('Mining stopped', 'success')
    else:
        flash('Mining is not running', 'info')
    
    return redirect(url_for('mine'))

@app.route('/nodes')
def nodes():
    """Render the network nodes page"""
    peers = node.p2p_server.get_peers()
    return render_template('nodes.html', peers=peers)

@app.route('/add_node', methods=['POST'])
def add_node():
    """Add a new node to the network"""
    try:
        node_address = request.form.get('node_address')
        if node_address:
            node.p2p_server.add_peer(node_address)
            flash(f'Node {node_address} added successfully!', 'success')
        else:
            flash('Node address cannot be empty', 'danger')
    except Exception as e:
        flash(f'Error adding node: {str(e)}', 'danger')
    
    return redirect(url_for('nodes'))

@app.route('/sync_blockchain', methods=['POST'])
def sync_blockchain():
    """Synchronize the blockchain with the network"""
    try:
        result = node.p2p_server.sync_blockchain()
        if result:
            flash('Blockchain synchronized with the network!', 'success')
        else:
            flash('Already up to date with the network', 'info')
    except Exception as e:
        flash(f'Error synchronizing blockchain: {str(e)}', 'danger')
    
    return redirect(url_for('nodes'))

# API endpoints for P2P communication
@app.route('/chain', methods=['GET'])
def get_chain():
    """API endpoint to get the full blockchain"""
    chain_data = [block.to_dict() for block in node.blockchain.chain]
    response = {
        'chain': chain_data,
        'length': len(chain_data)
    }
    return jsonify(response)

@app.route('/transaction/new', methods=['POST'])
def receive_transaction():
    """API endpoint to receive a new transaction from the network"""
    values = request.get_json()
    
    if not values:
        return jsonify({'message': 'No transaction data provided'}), 400
    
    # Create a Transaction object from the received data
    transaction = Transaction.from_dict(values)
    
    # Verify the transaction
    if not transaction.verify_signature():
        return jsonify({'message': 'Invalid transaction signature'}), 400
    
    # Add to pending transactions
    try:
        block_index = node.blockchain.add_transaction(transaction)
        response = {'message': f'Transaction will be added to Block {block_index}'}
        return jsonify(response), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 400

@app.route('/block/new', methods=['POST'])
def receive_block():
    """API endpoint to receive a new block from the network"""
    values = request.get_json()
    
    if not values:
        return jsonify({'message': 'No block data provided'}), 400
    
    # Create a Block object from the received data
    transactions = []
    for tx_data in values.get('transactions', []):
        transaction = Transaction.from_dict(tx_data)
        transactions.append(transaction)
    
    block = Block(
        index=values['index'],
        transactions=transactions,
        timestamp=values['timestamp'],
        previous_hash=values['previous_hash'],
        nonce=values['nonce']
    )
    block.hash = values['hash']
    
    # Verify the block
    if block.hash != block.calculate_hash():
        return jsonify({'message': 'Invalid block hash'}), 400
    
    # Check if the block is the next in sequence
    if block.index != len(node.blockchain.chain):
        # If not, we might need to sync the whole chain
        return jsonify({'message': 'Block index mismatch, full sync required'}), 409
    
    # Check if block connects to our chain
    if block.previous_hash != node.blockchain.last_block.hash:
        return jsonify({'message': 'Block does not connect to our chain'}), 409
    
    # Add the block to our chain
    node.blockchain.chain.append(block)
    
    # Clear any transactions that are now in the blockchain
    tx_hashes_in_block = {tx.calculate_hash() for tx in block.transactions}
    node.blockchain.pending_transactions = [
        tx for tx in node.blockchain.pending_transactions 
        if tx.calculate_hash() not in tx_hashes_in_block
    ]
    
    return jsonify({'message': 'Block added to the chain'}), 201

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    """API endpoint to register a list of new nodes"""
    values = request.get_json()
    
    nodes = values.get('nodes')
    if not nodes:
        return jsonify({'message': 'Please supply a valid list of nodes'}), 400
    
    for node_address in nodes:
        node.p2p_server.add_peer(node_address)
    
    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(node.p2p_server.get_peers())
    }
    return jsonify(response), 201

@app.route('/nodes', methods=['GET'])
def get_nodes():
    """API endpoint to get the list of nodes"""
    response = {
        'nodes': list(node.p2p_server.get_peers()),
        'count': len(node.p2p_server.get_peers())
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
