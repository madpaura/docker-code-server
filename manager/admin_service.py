from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import hashlib
import secrets
from database import UserDatabase
from dotenv import load_dotenv
import os
from loguru import logger
import json
import toml
import ipaddress

# Configure logger
logger.add("manager_backend.log", rotation="500 MB", retention="10 days", level="INFO")

# Load environment variables
load_dotenv(".env", override=True)

app = Flask(__name__)
CORS(app)

# Initialize database connection
db = UserDatabase()
db.initialize_database()

# Agent configuration
AGENTS_FILE = "agents.txt"

def generate_session_token():
    return secrets.token_urlsafe(32)

def is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def read_agents():
    if not os.path.exists(AGENTS_FILE):
        return []
    with open(AGENTS_FILE, 'r') as file:
        agents = file.read().splitlines()
        return agents

def write_agents(agents):
    with open(AGENTS_FILE, 'w') as file:
        for agent in agents:
            file.write(f"{agent}\n")

# Authentication endpoints
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = db.verify_login(username, password)
    print(user)

    if user and user["is_approved"]:
        session_token = generate_session_token()
        expires_at = datetime.now() + timedelta(hours=24)
        
        if db.create_session(user["id"], session_token, expires_at):
            return jsonify({
                'success': True,
                'user': {
                    'id': user["id"],
                    'username': user["username"],
                    'is_admin': user["is_admin"],
                    'session_token': session_token
                }
            })
    
    return jsonify({'success': False, 'error': 'Invalid credentials or account not approved'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.get_json()
    user_id = data.get('user_id')
    
    if user_id:
        db.log_audit(user_id, "logout", {}, request.remote_addr)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Invalid request'}), 400

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    
    if password != confirm_password:
        return jsonify({'success': False, 'error': 'Passwords do not match'}), 400
    
    if not username or not email or not password:
        return jsonify({'success': False, 'error': 'Please fill in all fields'}), 400
    
    user_data = {
        "username": username,
        "password": hashlib.sha256(password.encode()).hexdigest(),
        "email": email,
        "metadata": {"registration_source": "web"},
    }
    
    if db.create_user(user_data):
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Username or email already exists'}), 400

# User management endpoints
@app.route('/api/users', methods=['GET'])
def get_users():
    logger.info("Fetching all users")
    users = db.get_all_users()
    if users:
        logger.success(f"Found {len(users)} users")
        return jsonify({'success': True, 'users': users})
    logger.warning("No users found in database")
    return jsonify({'success': False, 'error': 'No users found'}), 404

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user_info(user_id):
    logger.info("Fetching all users")
    user = db.get_user_by_id(user_id)
    if user:
        logger.success(f"Found {len(user)} user")
        return jsonify({'success': True, 'redirect_url': user['redirect_url']})

    logger.warning("No users found in database")
    return jsonify({'success': False, 'error': 'No users found'}), 404

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if db.delete_user_by_id(user_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'User not found'}), 404

@app.route('/api/users/pending', methods=['GET'])
def get_pending_users():
    users = db.get_pending_users()
    if users:
        return jsonify({'success': True, 'users': users})
    return jsonify({'success': False, 'error': 'No pending users'}), 200

@app.route('/api/users/<int:user_id>/approve', methods=['POST'])
def approve_user(user_id):
    data = request.get_json()
    server_id = data.get('server_id')
    
    if db.update_user(user_id, {
        'is_approved': True,
        'redirect_url': f"http://{server_id}:{os.getenv('AGENT_PORT', 8510)}"
    }):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'User not found'}), 404

# Audit logs endpoint
@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    username = request.args.get('username')
    limit = request.args.get('limit', default=100, type=int)
    
    logger.info(f"Fetching audit logs for username: {username}, limit: {limit}")
    logs = db.get_audit_logs(username=username, limit=limit)
    if logs:
        logger.success(f"Found {len(logs)} audit logs")
        return jsonify({'success': True, 'logs': logs})
    logger.info("No audit logs found")
    return jsonify({'success': False, 'error': 'No logs found'}), 404

from query_agents import query_available_agents

# Server resources endpoint
@app.route('/api/server-resources', methods=['GET'])
def get_server_resources():
    agents_list = read_agents()
    query_port = int(os.getenv('AGENT_PORT', 8510)) + 1
    servers = query_available_agents(agents_list, query_port)
    
    if servers:
        return jsonify({'success': True, 'servers': servers})
    return jsonify({'success': False, 'error': 'No servers available'}), 404

# Session validation endpoints
@app.route("/api/validate_session", methods=["POST"])
def validate_session():
    data = request.get_json()
    logger.info(f"Got request from : {json.dumps(data, indent=4)}")

    user_id = data.get("user_id")
    session_token = data.get("session_token")

    if not user_id or not session_token:
        return jsonify({"valid": False, "message": "user_id and session_token are required"}), 400

    is_valid = db.verify_session(session_token)

    if is_valid:
        logger.success(f"Valid session found")
        return jsonify({"valid": True, "message": "Session is valid."}), 200
    else:
        logger.error(f"No valid session found !!")
        return jsonify({"valid": False, "message": "Session is invalid."}), 200

# Agent management endpoints
@app.route("/api/register_agent", methods=["POST"])
def register_agent():
    data = request.get_json()
    agent = data.get("agent")
    if not agent:
        return jsonify({"valid": False, "message": "ip address required"}), 400
    
    if not is_valid_ip(agent):
        return jsonify({"valid": False, "message": "agent id must be valid IP address"}), 400
    
    agents = read_agents()
    if agent in agents:
        return jsonify({"valid": False, "message": "Agent already registered"}), 400

    logger.info(f"Registering new agent: {agent}")
    agents.append(agent)
    write_agents(agents)
    logger.success(f"Agent {agent} registered successfully")
    return jsonify({"valid": True, "message": "Agent registered successfully"}), 200

@app.route("/api/unregister_agent", methods=["POST"])
def unregister_agent():
    data = request.get_json()
    agent = data.get("agent")
    if not agent:
        return jsonify({"valid": False, "message": "ip address required"}), 400
    
    if not is_valid_ip(agent):
        return jsonify({"valid": False, "message": "agent id must be valid IP address"}), 400
    
    agents = read_agents()
    if agent not in agents:
        return jsonify({"valid": False, "message": "Agent not found"}), 400

    agents.remove(agent)
    write_agents(agents)
    logger.success(f"Agent {agent} unregistered successfully")
    return jsonify({"valid": True, "message": "Agent unregistered successfully"}), 200

if __name__ == '__main__':
    config_path = os.path.join('.streamlit', 'config.toml')
    if os.path.exists(config_path):
        config = toml.load(config_path)
        port = config.get('server', {}).get('backend_port', 8500)
    else:
        port = 8500
    
    app.run(host='0.0.0.0', port=port)