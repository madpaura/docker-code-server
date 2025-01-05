from flask import Flask, request, jsonify
from database import UserDatabase
import os
from dotenv import load_dotenv
from loguru import logger
import json

load_dotenv("/home/vishwa/workspace/cxl-deploy/.env", override=True)

app = Flask(__name__)
db = UserDatabase()  # Initialize your database connection

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

if __name__ == "__main__":
    port = os.getenv("MGMT_CONSOLE_PORT", 8501)
    app.run(host="0.0.0.0", port=port)

