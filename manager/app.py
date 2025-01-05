# app.py
import streamlit as st
import hashlib
from datetime import datetime, timedelta
import secrets
from database import UserDatabase
import os
from typing import Dict
from dotenv import load_dotenv
import json
from resouce_query_handler import query_available_servers
import pandas as pd


load_dotenv(".env", override=True)

AGENT_SERVERS_LIST = os.getenv("AGENT_SERVERS_LIST")
server_list = [server.strip() for server in AGENT_SERVERS_LIST.split(",")]
server_query_port = int(os.getenv("AGENT_RESOURCE_QUERY_PORT", 8502))
server_client_port = int(os.getenv("AGENT_QUERY_PORT", 8500))

# Initialize database connection
db = UserDatabase()
db.initialize_database()


def generate_session_token():
    return secrets.token_urlsafe(32)


def get_client_ip():
    try:
        return st.experimental_get_query_params().get("client_ip", ["unknown"])[0]
    except:
        return "unknown"


def init_session_state():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.session_state.username = None
        st.session_state.user_id = None
        st.session_state.session_token = None


def handle_login(username: str, password: str) -> bool:
    user = db.verify_login(username, password)
    if user and user["is_approved"]:
        session_token = generate_session_token()
        expires_at = datetime.now() + timedelta(hours=24)
        if db.create_session(user["id"], session_token, expires_at):
            st.session_state.logged_in = True
            st.session_state.is_admin = user["is_admin"]
            st.session_state.username = user["username"]
            st.session_state.user_id = user["id"]
            st.session_state.session_token = session_token

            db.log_audit(user["id"], "login", {"method": "password"}, get_client_ip())
            return True
    return False


def display_audit_logs():
    st.subheader("Audit Logs")

    # Get all users for the filter
    users = db.get_all_users()
    user_options = ["All Users"] + [user["username"] for user in users]

    col1, col2 = st.columns(2)

    with col1:
        user_filter = st.selectbox(
            "Filter by User", options=user_options, key="audit_user_filter"
        )

    with col2:
        n_rows = st.select_slider(
            "Number of rows",
            options=[10, 25, 50, 100, 500],
            value=100,
            key="n_rows_slider",
        )

    try:
        logs = db.get_audit_logs(
            username=user_filter if user_filter != "All Users" else None, limit=n_rows
        )

        if logs:
            # Process the logs to ensure proper format
            processed_logs = []
            for log in logs:
                # Convert action_details from string to dict if needed
                action_details = log.get("action_details", "{}")
                if isinstance(action_details, str):
                    try:
                        action_details = json.loads(action_details)
                    except:
                        action_details = {}

                # Create a processed log entry
                processed_log = {
                    "Timestamp": pd.to_datetime(log["timestamp"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "Username": log["username"],
                    "Action": log["action_type"],
                    "IP Address": log["ip_address"],
                    "Details": str(action_details),
                }
                processed_logs.append(processed_log)

            # Create DataFrame
            df = pd.DataFrame(processed_logs)

            # Add search functionality
            search_term = st.text_input("Search in logs:", "")
            if search_term:
                mask = (
                    df.astype(str)
                    .apply(lambda x: x.str.contains(search_term, case=False))
                    .any(axis=1)
                )
                df = df[mask]

            # Display data info
            st.write(f"Showing {len(df)} records")

            # Display the DataFrame with sorting enabled
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Timestamp": st.column_config.TextColumn(
                        "Timestamp",
                        width="medium",
                    ),
                    "Username": st.column_config.TextColumn(
                        "Username",
                        width="small",
                    ),
                    "Action": st.column_config.TextColumn(
                        "Action",
                        width="small",
                    ),
                    "IP Address": st.column_config.TextColumn(
                        "IP Address",
                        width="small",
                    ),
                    "Details": st.column_config.TextColumn(
                        "Details",
                        width="large",
                    ),
                },
            )

            # Add export functionality
            if st.button("Export to CSV"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="audit_logs.csv",
                    mime="text/csv",
                )

        else:
            st.info("No audit logs found")
    except Exception as e:
        st.error(f"Error retrieving audit logs: {str(e)}")
        st.info(
            "If this is a new installation, make sure the audit_log table is properly created."
        )


def display_pending_approvals():
    st.subheader("Pending Approvals")
    pending_users = db.get_pending_users()

    if pending_users:
        df = pd.DataFrame(pending_users)

        # Rename columns for better display
        df = df.rename(
            columns={
                "username": "Username",
                "email": "Email",
                "created_at": "Registration Date",
            }
        )

        df["Registration Date"] = pd.to_datetime(df["Registration Date"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        st.write(f"Found {len(df)} pending approval(s)")

        # Add search functionality
        search_term = st.text_input("Search pending users:", key="pending_search")
        if search_term:
            mask = (
                df.astype(str)
                .apply(lambda x: x.str.contains(search_term, case=False))
                .any(axis=1)
            )
            df = df[mask]

        # Display the DataFrame
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Username": st.column_config.TextColumn(
                    "Username",
                    width="medium",
                ),
                "Email": st.column_config.TextColumn(
                    "Email",
                    width="medium",
                ),
                "Registration Date": st.column_config.TextColumn(
                    "Registration Date",
                    width="medium",
                ),
            },
        )

        # Create approval form
        st.subheader("Approve Users")
        selected_user = st.selectbox(
            "Select user to approve",
            options=df["Username"].tolist(),
            key="user_to_approve",
        )

        if selected_user:
            user_id = [
                u["id"] for u in pending_users if u["username"] == selected_user
            ][0]

            with st.form(key=f"approve_form_{user_id}"):

                servers = query_available_servers(server_list, server_query_port)
                server_options = (
                    [server["server_id"] for server in servers]
                    if servers
                    else ["No servers available"]
                )

                # Select server from the list
                selected_server = st.selectbox(
                    "Select a server for the user",
                    options=server_options,
                    key=f"server_select_{user_id}",
                )

                col1, col2 = st.columns([1, 4])
                with col1:
                    approve = st.form_submit_button("Approve")

                if approve:
                    if selected_server == "No servers available":
                        st.error("No servers available for assignment.")
                    else:
                        # Update the user's redirect URL with the selected server
                        db.update_user(
                            user_id,
                            {
                                "is_approved": True,
                                "redirect_url": f"http://{selected_server}:{server_client_port}",
                                "metadata": {"approved_by": st.session_state.username},
                            },
                        )
                        db.log_audit(
                            st.session_state.user_id,
                            "approve_user",
                            {"approved_user": selected_user},
                            get_client_ip(),
                        )
                        st.success(
                            f"Approved user {selected_user} and assigned to server {selected_server}"
                        )
                        st.rerun()
    else:
        st.info("No pending approvals")


def display_manage_users():
    st.title("Manage Users")
    users = db.get_all_users()

    if users:
        df = pd.DataFrame(users)

        # Rename columns for better readability
        df = df.rename(
            columns={
                "id": "ID",
                "username": "Username",
                "email": "Email",
                "is_approved": "Approved",
                "redirect_url": "Redirect URL",
                "created_at": "Created At",
            }
        )

        # Format the 'Approved' column to show 'Yes' or 'No'
        df["Approved"] = df["Approved"].apply(lambda x: "Yes" if x else "No")

        # Format the 'Created At' column to a readable date-time format
        df["Created At"] = pd.to_datetime(df["Created At"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Display the DataFrame
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.TextColumn("ID", width="small"),
                "Username": st.column_config.TextColumn("Username", width="medium"),
                "Email": st.column_config.TextColumn("Email", width="medium"),
                "Approved": st.column_config.TextColumn("Approved", width="small"),
                "Redirect URL": st.column_config.TextColumn(
                    "Redirect URL", width="large"
                ),
                "Created At": st.column_config.TextColumn("Created At", width="medium"),
            },
        )

        # Add a delete user section
        st.subheader("Delete User")
        selected_user = st.selectbox(
            "Select a user to delete",
            options=df["Username"].tolist(),
            key="delete_user_selectbox",
        )

        if selected_user:
            user_id = df[df["Username"] == selected_user]["ID"].values[0]

            # Confirmation step before deletion
            confirm_delete = st.checkbox(
                f"Are you sure you want to delete user '{selected_user}'?",
                key=f"confirm_delete_{user_id}",
            )

            if confirm_delete:
                if st.button("Delete User", key=f"delete_button_{user_id}"):
                    db.log_audit(
                        st.session_state.user_id,
                        "delete_user",
                        {"deleted_user": selected_user},
                        get_client_ip(),
                    )
                    db.delete_user_by_username(selected_user)
                    st.success(f"User '{selected_user}' has been deleted.")
                    st.rerun()  # Refresh the page to update the user list
    else:
        st.info("No users found in the database.")


import time


def display_server_resources():
    """
    Display available servers and their resources in a Streamlit table.
    """
    st.subheader("Available Servers and Resources")

    progress_bar = st.progress(0)
    status_text = st.empty()  # Placeholder for status text

    # Simulate progress while querying servers
    for percent_complete in range(100):
        time.sleep(0.02)  # Simulate a delay (replace with actual query logic)
        progress_bar.progress(percent_complete + 1)
        status_text.text(f"Querying server resources... {percent_complete + 1}%")

    servers = query_available_servers(server_list, server_query_port)
    if servers:
        df = pd.DataFrame(servers)

        # Rename columns for better readability
        df = df.rename(
            columns={
                "cpu_count": "CPU Cores",
                "total_memory": "Total Memory (GB)",
                "host_cpu_used": "Host CPU Used (%)",
                "host_memory_used": "Host Memory Used (GB)",
                "docker_instances": "Docker Instances",
                "allocated_cpu": "Allocated CPU (Cores)",
                "allocated_memory": "Allocated Memory (GB)",
                "remaining_cpu": "Remaining CPU (Cores)",
                "remaining_memory": "Remaining Memory (GB)",
            }
        )

        # Display the DataFrame
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "CPU Cores": st.column_config.NumberColumn("CPU Cores"),
                "Total Memory (GB)": st.column_config.NumberColumn(
                    "Total Memory (GB)", format="%.2f GB"
                ),
                "Host CPU Used (%)": st.column_config.NumberColumn(
                    "Host CPU Used (%)", format="%.2f %%"
                ),
                "Host Memory Used (GB)": st.column_config.NumberColumn(
                    "Host Memory Used (GB)", format="%.2f GB"
                ),
                "Docker Instances": st.column_config.NumberColumn("Docker Instances"),
                "Allocated CPU (Cores)": st.column_config.NumberColumn(
                    "Allocated CPU (Cores)", format="%.2f cores"
                ),
                "Allocated Memory (GB)": st.column_config.NumberColumn(
                    "Allocated Memory (GB)", format="%.2f GB"
                ),
                "Remaining CPU (Cores)": st.column_config.NumberColumn(
                    "Remaining CPU (Cores)", format="%.2f cores"
                ),
                "Remaining Memory (GB)": st.column_config.NumberColumn(
                    "Remaining Memory (GB)", format="%.2f GB"
                ),
            },
        )
    else:
        st.info("No servers available.")

    # Clear the progress bar and status text
    progress_bar.empty()
    status_text.empty()


def main():
    st.set_page_config(page_title="User Authentication System", layout="wide")
    init_session_state()

    st.markdown(
        """
            <style>
                .sidebar .sidebar-content {
                    padding: 20px;
                }
                .sidebar .sidebar-content .stRadio > div {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                .sidebar .sidebar-content .stRadio label {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    font-size: 16px;
                    padding: 10px;
                    border-radius: 5px;
                    transition: background-color 0.3s;
                }
                .sidebar .sidebar-content .stRadio label:hover {
                    background-color: #f0f0f0;
                }
                .logo {
                    text-align: center;
                    margin-bottom: 20px;
                }
                .logo img {
                    max-width: 100%;
                    height: auto;
                }
            </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        """
        <div class="logo">
            <img src="/home/vishwa/workspace/cxl-deploy/docker-code-server/manager/logo.png" alt="Logo">
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.divider()

    if not st.session_state.logged_in:
        page = st.sidebar.radio(
            "Menu",
            ["Login", "Register"],
            format_func=lambda x: f"🔑 {x}" if x == "Login" else f"📝 {x}",
        )
    else:
        if st.session_state.is_admin:
            page = st.sidebar.radio(
                "Menu",
                ["Admin Dashboard", "Manage Users", "Servers", "Audit Logs", "Logout"],
                format_func=lambda x: {
                    "Admin Dashboard": "📊 Admin Dashboard",
                    "Manage Users": "👥 Manage Users",
                    "Servers": "🖥️ Servers",
                    "Audit Logs": "📋 Audit Logs",
                    "Logout": "🚪 Logout",
                }[x],
            )
        else:
            user = db.get_user_by_username(st.session_state.username)
            if user and user["redirect_url"]:
                st.success("Redirecting to your assigned application...")
                url = (
                    user["redirect_url"]
                    + f"?user={st.session_state.username}&session_token={st.session_state.session_token}"
                )
                st.markdown(
                    f'<meta http-equiv="refresh" content="2;url={url}">',
                    unsafe_allow_html=True,
                )
                st.markdown(f"If not redirected, click [here]({url})")
            page = st.sidebar.radio("Menu", ["User Dashboard", "Logout"])

    if page == "Login":
        st.title("Login")
        display_login()

    elif page == "Register":
        st.title("Register")
        display_user_registration()

    elif page == "Admin Dashboard" and st.session_state.is_admin:
        st.title("Admin Dashboard")
        st.write(f"Welcome, {st.session_state.username}!")
        display_pending_approvals()

    elif page == "Servers":
        display_server_resources()

    elif page == "Manage Users" and st.session_state.is_admin:
        display_manage_users()

    elif page == "Audit Logs" and st.session_state.is_admin:
        display_audit_logs()

    elif page == "User Dashboard" and st.session_state.logged_in:
        st.title("User Dashboard")
        st.write(f"Welcome, {st.session_state.username}!")
        user = db.get_user_by_username(st.session_state.username)
        if user["redirect_url"]:
            st.write("You will be redirected to your assigned application.")
            url = (
                user["redirect_url"]
                + f"?user={st.session_state.username}&session_token={st.session_state.session_token}"
            )
            st.write(f"Assigned URL: {url}")
        else:
            st.warning("No redirect URL has been assigned to your account yet.")

    elif page == "Logout":
        if st.session_state.user_id:
            db.log_audit(st.session_state.user_id, "logout", {}, get_client_ip())
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.session_state.username = None
        st.session_state.user_id = None
        st.session_state.session_token = None
        st.success("Logged out successfully!")
        st.rerun()


def display_login():
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


def display_user_registration():
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
                    "username": username,
                    "password": hashlib.sha256(password.encode()).hexdigest(),
                    "email": email,
                    "metadata": {"registration_source": "web"},
                }
                if db.create_user(user_data):
                    st.success(
                        "Registration successful! Please wait for admin approval."
                    )
                else:
                    st.error("Username or email already exists!")


if __name__ == "__main__":
    main()
