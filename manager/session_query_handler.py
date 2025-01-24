#session_query_handler.py
from flask import Flask, request, jsonify
from database import UserDatabase
import os
from dotenv import load_dotenv
from loguru import logger
import json
import toml
import ipaddress


load_dotenv(".env", override=True)

app = Flask(__name__)
db = UserDatabase()  # Initialize your database connection
AGENTS_FILE = "agents.txt"

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
@app.route("/validate_session", methods=["POST"])
def validate_session():
    """
    Validate the session_token for the given user_id.
    """
    # Get the payload from the request
    data = request.get_json()
    logger.info(f"Got request from : {json.dumps(data, indent=4)}")

    user_id = data.get("user_id")
    session_token = data.get("session_token")

    if not user_id or not session_token:
        return jsonify({"valid": False, "message": "user_id and session_token are required"}), 400

    # Check if the session is valid
    is_valid = db.verify_session(session_token)

    if is_valid:
        logger.success(f"Valid session found")
        return jsonify({"valid": True, "message": "Session is valid."}), 200
    else:
        logger.error(f"No valid session found !!")
        return jsonify({"valid": False, "message": "Session is invalid."}), 200

@app.route("/register_agent", methods=["POST"])
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

    agents.append(agent)
    write_agents(agents)
    logger.success(f"Agent {agent} registerd successfully")
    return jsonify({"valid": True, "message": "Agent registerd successfully"}), 200

@app.route("/unregister_agent", methods=["POST"])
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
    logger.success(f"Agent {agent} unregisterd successfully")
    return jsonify({"valid": True, "message": "Agent unregisterd successfully"}), 200


if __name__ == "__main__":
    config_path = os.path.join('.streamlit', 'config.toml')
    if os.path.exists(config_path):
        config = toml.load(config_path)
        port = config.get('server', {}).get('session_port', 8501)
    else:
        port = 8501
    app.run(host="0.0.0.0", port=port)

