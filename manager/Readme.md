# User Authentication System

This is a Streamlit-based web application for user authentication, management, and server resource monitoring. 
It includes features like user registration, login, admin dashboard, audit logs, and server resource tracking.

## Features
- **User Registration & Login**: Users can register and log in with credentials.
- **Admin Dashboard**: Admins can manage users, approve registrations, and view audit logs.
- **Audit Logs**: Track user actions and system events.
- **Server Resources**: Monitor available servers and their resource usage.

## How to Run

1. **Install Dependencies**:
   Ensure you have Python installed, then install the required packages:
   ```bash
   pip install streamlit pandas python-dotenv
   ```

2. **Set Up Environment Variables**:
   Create a `.env` file in the root directory with the following variables:
   ```plaintext
   AGENT_SERVERS_LIST=server1,server2
   AGENT_RESOURCE_QUERY_PORT=8502
   AGENT_CLIENT_PORT=8500
   ```

3. **Run the Application**:
   Start the Streamlit app by running:
   ```bash
   streamlit run app.py
   ```

4. **Access the App**:
   Open your browser and navigate to `http://localhost:8501`.

---
For more details, refer to the code in `app.py`.

# Session Validation Server

A simple Flask-based API to validate user sessions using a `session_token` and `user_id`.

## Features
- **Session Validation**: Validates user sessions by checking the provided `session_token` and `user_id`.

## How to Run

1. **Install Dependencies**:
   Ensure you have Python installed, then install the required packages:
   ```bash
   pip install flask loguru python-dotenv
   ```

2. **Set Up Environment Variables**:
   Create a `.env` file in the root directory with the following variable:
   ```plaintext
   MGMT_CONSOLE_PORT=8501
   ```

3. **Run the Application**:
   Start the Flask app by running:
   ```bash
   python session_query_handler.py
   ```

4. **Access the API**:
   The API will be available at `http://0.0.0.0:8501/validate_session`. Send a POST request with a JSON payload containing `user_id` and `session_token`.

---
For more details, refer to the code in `session_query_handler.py`.