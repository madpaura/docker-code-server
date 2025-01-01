# app.py
import streamlit as st
import hashlib
from datetime import datetime, timedelta
import secrets
import validators
from userdb import UserDatabase
import os
from typing import Dict

# Initialize database connection
db = UserDatabase()

def generate_session_token():
    return secrets.token_urlsafe(32)

def get_client_ip():
    try:
        return st.experimental_get_query_params().get('client_ip', ['unknown'])[0]
    except:
        return 'unknown'

def init_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.session_state.username = None
        st.session_state.user_id = None
        st.session_state.session_token = None

def handle_login(username: str, password: str) -> bool:
    user = db.verify_login(username, password)
    if user and user['is_approved']:
        session_token = generate_session_token()
        expires_at = datetime.now() + timedelta(hours=24)
        if db.create_session(user['id'], session_token, expires_at):
            st.session_state.logged_in = True
            st.session_state.is_admin = user['is_admin']
            st.session_state.username = user['username']
            st.session_state.user_id = user['id']
            st.session_state.session_token = session_token
            
            db.log_audit(
                user['id'],
                'login',
                {'method': 'password'},
                get_client_ip()
            )
            return True
    return False

def display_audit_logs():
    st.subheader("Audit Logs")
    users = db.get_all_users()
    user_filter = st.selectbox(
        "Filter by User",
        options=[user['username'] for user in users],
        key="audit_user_filter"
    )
    
    logs = db.get_audit_logs(
        username=user_filter if user_filter != "All Users" else None,
        limit=100
    )
    
    if logs:
        for log in logs:
            st.text(
                f"[{log['timestamp']}] {log['username']}: {log['action_type']} - "
                f"IP: {log['ip_address']}"
            )
    else:
        st.info("No audit logs found")

def main():
    st.set_page_config(page_title="User Authentication System", layout="wide")
    init_session_state()
    
    if not st.session_state.logged_in:
        page = st.sidebar.radio("Navigation", ["Login", "Register"])
    else:
        if st.session_state.is_admin:
            page = st.sidebar.radio("Navigation", 
                                  ["Admin Dashboard", "Manage Users", "Audit Logs", "Logout"])
        else:
            user = db.get_user_by_username(st.session_state.username)
            if user and user['redirect_url']:
                st.success("Redirecting to your assigned application...")
                st.markdown(
                    f'<meta http-equiv="refresh" content="2;url={user["redirect_url"]}">', 
                    unsafe_allow_html=True
                )
                st.markdown(f'If not redirected, click [here]({user["redirect_url"]})')
            page = st.sidebar.radio("Navigation", ["User Dashboard", "Logout"])
    
    if page == "Login":
        st.title("Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if handle_login(username, password):
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials or account not approved")
    
    elif page == "Register":
        st.title("Register")
        with st.form("register_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Register")
            
            if submit:
                if password != confirm_password:
                    st.error("Passwords do not match!")
                elif not username or not email or not password:
                    st.error("Please fill in all fields!")
                else:
                    user_data = {
                        'username': username,
                        'password': hashlib.sha256(password.encode()).hexdigest(),
                        'email': email,
                        'metadata': {'registration_source': 'web'}
                    }
                    if db.create_user(user_data):
                        st.success("Registration successful! Please wait for admin approval.")
                    else:
                        st.error("Username or email already exists!")
    
    elif page == "Admin Dashboard" and st.session_state.is_admin:
        st.title("Admin Dashboard")
        st.write(f"Welcome, {st.session_state.username}!")
        
        st.subheader("Pending Approvals")
        pending_users = db.get_pending_users()
        
        if pending_users:
            for user in pending_users:
                with st.form(f"approve_form_{user['id']}"):
                    st.write(f"User: {user['username']} ({user['email']})")
                    st.write(f"Registration date: {user['created_at']}")
                    redirect_url = st.text_input(
                        "Redirect URL",
                        key=f"url_{user['id']}",
                        placeholder="https://example.com"
                    )
                    approve = st.form_submit_button("Approve")
                    
                    if approve:
                        if not validators.url(redirect_url):
                            st.error("Please provide a valid URL")
                        else:
                            db.update_user(
                                user['id'],
                                {
                                    'is_approved': True,
                                    'redirect_url': redirect_url,
                                    'metadata': {'approved_by': st.session_state.username}
                                }
                            )
                            db.log_audit(
                                st.session_state.user_id,
                                'approve_user',
                                {'approved_user': user['username']},
                                get_client_ip()
                            )
                            st.success(f"Approved user {user['username']}")
                            st.rerun()
        else:
            st.info("No pending approvals")
    
    elif page == "Manage Users" and st.session_state.is_admin:
        st.title("Manage Users")
        users = db.get_all_users()
        
        if users:
            for user in users:
                with st.expander(f"User: {user['username']}"):
                    with st.form(f"manage_user_{user['id']}"):
                        st.write(f"Email: {user['email']}")
                        st.write(f"Status: {'Approved' if user['is_approved'] else 'Pending'}")
                        current_url = user['redirect_url'] or ""
                        new_url = st.text_input(
                            "Redirect URL", 
                            value=current_url,
                            key=f"manage_url_{user['id']}"
                        )
                        update = st.form_submit_button("Update Redirect URL")
                        
                        if update:
                            if not validators.url(new_url):
                                st.error("Please provide a valid URL")
                            else:
                                db.update_user(
                                    user['id'],
                                    {'redirect_url': new_url}
                                )
                                db.log_audit(
                                    st.session_state.user_id,
                                    'update_redirect_url',
                                    {'user': user['username'], 'new_url': new_url},
                                    get_client_ip()
                                )
                                st.success(f"Updated redirect URL for {user['username']}")
                                st.rerun()
    
    elif page == "Audit Logs" and st.session_state.is_admin:
        display_audit_logs()
    
    elif page == "User Dashboard" and st.session_state.logged_in:
        st.title("User Dashboard")
        st.write(f"Welcome, {st.session_state.username}!")
        user = db.get_user_by_username(st.session_state.username)
        if user['redirect_url']:
            st.write("You will be redirected to your assigned application.")
            st.write(f"Assigned URL: {user['redirect_url']}")
        else:
            st.warning("No redirect URL has been assigned to your account yet.")
    
    elif page == "Logout":
        if st.session_state.user_id:
            db.log_audit(
                st.session_state.user_id,
                'logout',
                {},
                get_client_ip()
            )
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.session_state.username = None
        st.session_state.user_id = None
        st.session_state.session_token = None
        st.success("Logged out successfully!")
        st.rerun()

if __name__ == "__main__":
    main()