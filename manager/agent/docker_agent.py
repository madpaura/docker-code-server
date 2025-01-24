import os, sys, platform, socket, shutil, hashlib, uuid, docker
import docker.errors
import docker.models
import docker.models.containers
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import dateutil.parser
import webbrowser
import subprocess
import platform
import requests
import atexit

from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from dotenv import load_dotenv
from streamlit_option_menu import option_menu

# project
from resource_manager import PortManager

class DockerContainerManager:
    def __init__(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
        except docker.errors.DockerException as e:
            logger.error(f"Error connecting to Docker daemon: {e}")
            sys.exit(1)

    def create_container(
        self,
        image_name: str,
        container_name: str = None,
        ports: Dict[str, str] = None,
        volumes: Dict[str, Dict[str, str]] = None,
        environment: Dict[str, str] = None,
        command: str = None,
        detach: bool = True,
        cpu_count: float = None,
        cpu_percent: int = None,
        memory_limit: str = None,
        memory_swap: str = None,
        memory_reservation: str = None,
        host_name: str = "cx-qvp"
    ):
        try:
            # Pull the image if it doesn't exist
            try:
                self.client.images.get(image_name)
            except docker.errors.ImageNotFound:
                logger.warning(f"Pulling image {image_name}...")
                try:
                    image = self.client.images.pull(image_name)
                except docker.errors.APIError as e:
                    logger.error("Failed pulling image")
                    return None, f"Failed pulling image {image_name} Exception : {e}"

            # Create and start the container
            container = self.client.containers.run(
                image=image_name,
                name=container_name,
                ports=ports,
                volumes=volumes,
                environment=environment,
                command=command,
                detach=detach,
                cpu_count=cpu_count,
                cpu_percent=cpu_percent,
                mem_limit=memory_limit,
                memswap_limit=memory_swap,
                hostname=host_name,
                privileged=True
            )
            logger.success(f"Container created successfully: {container.name}")
            return container, "Sucess"

        except docker.errors.APIError as e:
            logger.error(f"Error creating container: {e}")
            return None, f"Error creating container: {e}"

    def list_container(self, name: str) -> Optional[docker.models.containers.Container]:
        try:
            container = self.client.containers.get(name)
            return container
        except docker.errors.NotFound:
            logger.error(f"Container {name} not found")
        except docker.errors.APIError as e:
            logger.error(f"Error stopping container: {e}")

    def stop_container(self, container_id_or_name: str):
        try:
            container = self.client.containers.get(container_id_or_name)
            container.stop()
            logger.success(f"Container {container_id_or_name} stopped successfully")
        except docker.errors.NotFound:
            logger.error(f"Container {container_id_or_name} not found")
        except docker.errors.APIError as e:
            logger.error(f"Error stopping container: {e}")

    def remove_container(self, container_id_or_name: str, force: bool = False):
        try:
            container = self.client.containers.get(container_id_or_name)
            container.remove(force=force)
            logger.success(f"Container {container_id_or_name} removed successfully")
        except docker.errors.NotFound:
            logger.error(f"Container {container_id_or_name} not found")
        except docker.errors.APIError as e:
            logger.error(f"Error removing container: {e}")


@st.dialog("Error")
def error_msg(msg, url=None):
    st.error(msg, icon="🚨")
    if url:
        st.write(f"Please visit to install necessary toolchain: {url}")
        if st.button("Go"):
            webbrowser.open(url)


def get_container_stats(container):
    """Get container statistics with fallback for different Docker versions"""
    stats = container.stats(stream=False)
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})
    memory_stats = stats.get("memory_stats", {})

    try:
        cpu_total = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        precpu_total = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        system_cpu_usage = cpu_stats.get("system_cpu_usage", 0)
        previous_system_cpu_usage = precpu_stats.get("system_cpu_usage", 0)

        online_cpus = cpu_stats.get("online_cpus", 1) or 1
        cpu_delta = cpu_total - precpu_total
        system_delta = system_cpu_usage - previous_system_cpu_usage

        cpu_usage = (
            (cpu_delta / system_delta) * 100.0 * online_cpus
            if system_delta > 0 and cpu_delta > 0
            else 0.0
        )

        memory_usage = memory_stats.get("usage", 0)
        memory_limit = memory_stats.get("limit", 1) or 1
        memory_percentage = (memory_usage / memory_limit) * 100.0

        return {
            "cpu_usage": round(cpu_usage, 2),
            "memory_usage": round(memory_percentage, 2),
            "memory_used": round(memory_usage / (1024 * 1024), 2),
            "memory_limit": round(memory_limit / (1024 * 1024), 2),
        }
    except Exception as e:
        error_msg(f"Error calculating stats: {str(e)}")
        return {"cpu_usage": 0, "memory_usage": 0, "memory_used": 0, "memory_limit": 0}


def parse_docker_timestamp(timestamp_str):
    """Parse Docker timestamp string to datetime object"""
    try:
        return dateutil.parser.parse(timestamp_str).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return "N/A"


def create_gauge(value, title, color="royalblue"):
    """Create a gauge chart using Plotly"""
    return go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 50], "color": "lightgreen"},
                    {"range": [50, 80], "color": "orange"},
                    {"range": [80, 100], "color": "orangered"},
                ],
            },
        )
    ).update_layout(height=300)


def display_container_stats(container):
    st.header("Usage Statistics")
    try:
        stats = get_container_stats(container)
        col1, col2 = st.columns(2)

        with col1:
            st.plotly_chart(
                create_gauge(stats["cpu_usage"], "CPU Usage (%)"),
                use_container_width=True,
            )

        with col2:
            st.plotly_chart(
                create_gauge(stats["memory_usage"], "Memory Usage (%)"),
                use_container_width=True,
            )

        st.metric("Memory Used (MB)", f"{stats['memory_used']:.2f}")
        st.metric("Memory Limit (MB)", f"{stats['memory_limit']:.2f}")
    except Exception as e:
        error_msg(f"Failed to get container statistics: {str(e)}")


def display_container_actions(container, user):
    col1, col2, col3 = st.columns(3)

    with col1:
        if container.status != "running":
            if st.button("▶️ Start"):
                try:
                    container.start()
                    st.success("Container started successfully")
                    st.rerun()
                except Exception as e:
                    error_msg(f"Failed to start container: {str(e)}")
        else:
            if st.button("⏹️ Stop"):
                try:
                    container.stop()
                    st.success("Container stopped successfully")
                    st.rerun()
                except Exception as e:
                    error_msg(f"Failed to stop container: {str(e)}")

    with col2:
        if st.button("🔄 Restart"):
            try:
                container.restart()
                st.success("Container restarted successfully")
                st.rerun()
            except Exception as e:
                error_msg(f"Failed to restart container: {str(e)}")

    with col3:
        if st.button("🗑️ Remove"):
            try:
                container.remove(force=True)
                port_manager = PortManager()
                new_ports = port_manager.deallocate_ports(user)
                st.success("Container removed successfully")
                st.rerun()
            except Exception as e:
                error_msg(f"Failed to remove container: {str(e)}")

def blue_header(text):
    st.markdown(f"<h3 style='color: blue;'> {text}</h3>", unsafe_allow_html=True)

def display_service_actions(container, user, page):
        
    port_manager = PortManager()
    port_range = port_manager.get_allocated_ports(user)

    ports = {}
    ports["code_port_host"] = port_range["start_port"]
    ports["ssh_port_host"] = port_range["start_port"] + 1
    ports["spice_port_host"] = port_range["start_port"] + 2
    ports["fm_ui_port_host"] = port_range["start_port"] + 3
    ports["fm_port_host"] = port_range["start_port"] + 4

    container_ip = container.attrs["NetworkSettings"].get("IPAddress") or next(
        (
            net.get("IPAddress", "N/A")
            for net in container.attrs["NetworkSettings"]["Networks"].values()
        ),
        "N/A",
    )

    container_ip, publicip = get_machine_ip()
    if page == None:
        st.write('No Conainers found...')

    elif page == 'VS Code':
        url = f"http://{container_ip}:{ports['code_port_host']}"
        blue_header(url)
        webbrowser.open(url)

    elif page == 'SSH':
        cmd = f"ssh -p {ports['ssh_port_host']} root@{container_ip}"
        st.write("Run below command in putty or click below to download script")
        col0, col1 = st.columns(2)
        with col0:
            blue_header(cmd)
        with col1:
            if platform.system() == "Windows":
                st.download_button(label="📥 SSH", data=cmd, file_name="ssh.cmd", mime="application/bat")
            else:
                st.download_button(label="📥 SSH", data=cmd, file_name="ssh.sh", mime="application/bash")

    elif page == 'RDP':
        cmd = f"remote-viewer spice://{container_ip}:{ports['spice_port_host']}"
        st.write("Run below command in SPICE viewer or click below to download script")
        col0, col1 = st.columns(2)
        with col0:
            blue_header(cmd)
        with col1:
            if platform.system() == "Windows":
                st.download_button(label="📥 RDP", data=cmd, file_name="rdp.cmd", mime="application/bat")
            else:
                st.download_button(label="📥 RDP", data=cmd, file_name="rdp.sh", mime="application/bash")
    
    elif page == 'FM-UI':
        url = f"http://{container_ip}:{ports['fm_ui_port_host']}"
        blue_header(url)
        webbrowser.open(url)

    with st.sidebar.expander("📡 Connection Info"):
        st.write(f"Container IP: {container_ip}")
        st.write("Default Ports:")
        for service, port in ports.items():
            service = service.replace("_port_host", "").upper()
            st.write(f"- {service} - {port}")

    with st.sidebar.expander("📥 Download Tools"):
        add_download_tools("putty-64bit-0.82-installer.msi", "📥 Putty ", "download/putty-64bit-0.82-installer.msi", "application/msi")
        add_download_tools("virt-viewer-x64-11.0-1.0.msi", "📥 Spice Viewer ", "download/virt-viewer-x64-11.0-1.0.msi", "application/msi")
        add_download_tools("TRACE32.zip", "📥 TRACE32 ", "download/TRACE32.zip", "application/zip")

def add_download_tools(tool, label, path, mime):
    try:
        with open(path, "rb") as file:
            st.download_button(label=label, 
                            data=file, file_name=tool,
                                mime=mime)
    except Exception as e:                
        logger.warning(f"Failed setting up download {tool}")

    
def generate_user_hash(username: str) -> str:
    import hashlib

    # Create SHA-256 hash of username
    hash_obj = hashlib.sha256(username.encode())

    # Get first 16 characters of hexadecimal hash
    return hash_obj.hexdigest()[:16]


def render_page(user):
    manager = DockerContainerManager()

    try:
        client = docker.from_env()
    except Exception as e:
        error_msg(f"Failed to connect to Docker: {str(e)}")
        return

    with st.sidebar:        
        page = option_menu(
            menu_title=f'{user}',
            options=['Home', 'VS Code', 'SSH', 'RDP', "FM-UI"],
            icons=['house', 'braces-asterisk', 'terminal','pc-display-horizontal', 'hdd-network'],
            menu_icon='cast',
            default_index=0,
            styles={
                "container": {"padding": "0!important","background-color":'white'},
                "icon": {"color": "black", "font-size": "23px"},
                "nav-link-selected": {"background-color": "#02a2e8"},
                }
            )

    name = get_contianer_name(user)
    container = manager.list_container(name)

    if not container:
        st.info("No containers found")
        if st.button("▶️ Create"):
            create_start_container(manager, user)
        return

    if page == 'Home':
        st.header("Available Instances")
        container_data = [
            {
                "Container ID": container.short_id,
                "Name": container.name,
                "Image": container.image.tags[0] if container.image.tags else "None",
                "Status": container.status,
                "Created": parse_docker_timestamp(container.attrs["Created"]),
            }
        ]

        logger.info(container_data)

        df = pd.DataFrame(container_data)
        st.dataframe(df)

        st.header("Manage Instance")
        display_container_actions(container, user)

        if container.status == "running":
            display_container_stats(container)

    display_service_actions(container, user, page)

def get_contianer_name(user):
    name = f"code-server-{user}-{generate_user_hash(user)}"
    return name

def get_machine_ip():
    """
    Get both local and public IP addresses of the machine.
    Returns a tuple of (local_ip, public_ip)
    """
    # Get local IP
    try:
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually connect but helps get local IP
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception as e:
        local_ip = "Could not determine local IP: " + str(e)

    # Get public IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        public_ip = s.getsockname()[0]
        s.close()
    except Exception as e:
        public_ip = "Could not determine public IP: " + str(e)

    # return "127.0.0.1", "127.0.0.1"
    return local_ip, public_ip

def is_valid_dir(dir):
    if not os.path.exists(dir):
        return False, "Destination directory does not exist."
    if not os.path.isdir(dir):
        return False, "Destination path is not a directory."
    if not os.listdir(dir):
        return False, "Destination directory is empty."
    return True, "Destination directory is valid."

def is_valid_sign(dir):
    signature_file = f"{dir}" + "/signature.txt"
    if not os.path.exists(signature_file):
        return False, "Signature file does not exist."
    with open(signature_file, 'r') as file:
        content = file.read()
        if "Timestamp:" not in content or "Unique Hash:" not in content:
            return False, "Signature file is missing required content."
    return True, "Signature file is valid."

def copy_dir_with_progress(src, dst, progress_bar):
    items = os.listdir(src)
    total_items = len(items)
    copied_items = 0

    logger.info(total_items)
    for item in items:
        progress = int ((copied_items/total_items) * 100)
        progress_bar.progress(progress, text=f"Copying {item} ...")
        src_path = os.path.join(src, item)
        dst_path = os.path.join(dst, item)

        if os.path.isfile(src_path):
            logger.info(f"File copy {src_path}")
            shutil.copy2(src_path, dst_path)
        elif os.path.isdir(src_path):
            logger.info(f"Dir copy {src_path}")
            shutil.copytree(src_path, dst_path)
        copied_items += 1
        logger.error(progress)

def setup_workdir(user, dir_template, dir_deploy):
    valid_dir, dir_error = is_valid_dir(dir_deploy)
    valid_sign, sign_error = is_valid_sign(dir_deploy)

    if valid_dir and valid_sign:
        logger.success("Valid workdir exists")
        return True

    logger.warning(f"{dir_error}, {sign_error}")
    progress_bar = st.progress(0)

    try:
        # shutil.copytree(dir_template, f"{dir_deploy}", progress_bar)
        copy_dir_with_progress(dir_template, f"{dir_deploy}", progress_bar)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Generate a unique hash (using UUID)
        unique_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

        progress_bar.progress(90, text="Setting up signature...")
        # Create a signature file in the destination directory
        signature_file_path = os.path.join(dir_deploy, 'signature.txt')
        with open(signature_file_path, 'w') as signature_file:
            signature_file.write(f"Timestamp: {timestamp}\n")
            signature_file.write(f"Unique Hash: {unique_hash}\n")

    except Exception as e:
        logger.error(f"Failed setting up workdir for user {user} : Exception {e}")
        return False

    progress_bar.progress(100, text="Almost there !! Setting up your container..")
    return True

def create_overlay(base_image_path, overlay_image_path):
    try:
        command = f"qemu-img create -f qcow2 -b {base_image_path} -F qcow2 {overlay_image_path}"
        subprocess.check_call(command, shell=True)
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create overlay image: {e}")
        return False

def create_start_container(manager, user):
    # Load environment variables from .env file
    load_dotenv("../.env", override=True)
    env = {}
    env["PUID"] = os.geteuid()
    env["PGID"] = os.getegid()
    env["TZ"] = "Etc/UTC"
    env["DEFAULT_WORKSPACE"] = os.getenv("DEFAULT_WORKSPACE", "/config/workspace")
    env["SUDO_PASSWORD"] = os.getenv("SUDO_PASSWORD", "abc")

    docker_image_name = os.getenv("DOCKER_IMAGE", "cxl.io/dev/code-server")
    docker_image_tag = os.getenv("DOCKER_TAG", "latest")

    dir_template = os.getenv("WORKDIR_TEMPLATE", "/opt/cxl/")
    dir_deploy = os.getenv("WORKDIR_DEPLOY", "/home/vms/") + f"{user}-{generate_user_hash(user)}" 

    if setup_workdir(user, dir_template, dir_deploy) == False:
        error_msg(f"Failed setting up workdir for {user}, please contact admin")
        return

    # create overlay for guest os provided
    guest_os_list = [item.strip() for item in os.getenv("GUEST_OS_LIST").split(",")]
    for guest_os in guest_os_list:
        dst_path = f"{dir_deploy}/guestos/{os.path.basename(os.path.dirname(guest_os))}"
        os.makedirs(dst_path, exist_ok=True)
        file_name = os.path.basename(guest_os)
        name, ext = os.path.splitext(file_name)
        new_file_name = f"{dst_path}/{name}_overlay{ext}"
        logger.info(f"Creating Overlay : {guest_os}, {new_file_name}")
        if create_overlay(guest_os, new_file_name) == False:
            error_msg(f"Failed creating overlay for {user}, please contact admin")
            return

    # TODO revamp this section
    container_name = get_contianer_name(user)
    guest_os_path_host = os.path.join(dir_deploy, "guestos")
    config_path_host = os.path.join(dir_deploy, "code/config")
    qvp_bin_path_host = os.path.join(dir_deploy, "qvp")
    tools_path_host = os.path.join(dir_deploy, "tools")
    arm_path_host = os.path.join(dir_deploy, "tools/ARMCompiler6.16")

    port_manager = PortManager()
    new_ports = port_manager.allocate_ports(user)
    start_port = int(new_ports["start_port"])

    code_port_host = start_port
    ssh_port_host = start_port + 1
    spice_port_host = start_port + 2
    fm_ui_port_host = start_port + 3
    fm_port_host = start_port + 4

    volumes = {}

    volumes["/dev/kvm"] = {
        "bind": "/dev/kvm",
        "mode": "rw",
    }

    volumes["/opt/os/guestos_base"] = {
        "bind": "/opt/os/guestos_base",
        "mode": "ro",
    }

    volumes[guest_os_path_host] = {
        "bind": os.getenv("GUEST_OS_MOUNT"),
        "mode": "rw",
    }
    volumes[config_path_host] = {
        "bind": os.getenv("CODE_CONFIG_MOUNT"),
        "mode": "rw",
    }

    volumes[qvp_bin_path_host] = {
        "bind": os.getenv("QVP_BINARY_MOUNT"),
        "mode": "rw",
    }

    volumes[tools_path_host] = {
        "bind": os.getenv("TOOLS_MOUNT"),
        "mode": "ro",
    }

    volumes[arm_path_host] = {
        "bind": "/usr/local/ARMCompiler6.16",
        "mode": "ro",
    }

    volumes["/dev/kvm"] = {
        "bind": "/dev/kvm",
        "mode": "rw",
    }

    ports = {}
    ports[os.getenv("CODE_PORT", 8443)] = code_port_host
    ports[os.getenv("GUEST_OS_SSH_PORT", 22)] = ssh_port_host
    ports[os.getenv("GUEST_OS_SPICE_PORT", 3001)] = spice_port_host
    ports[os.getenv("OPENCXL_FM_PORT", 8000)] = fm_port_host
    ports[os.getenv("OPENCXL_FM_UI_PORT", 3000)] = fm_ui_port_host

    try:
        container, error = manager.create_container(
            image_name=f"{docker_image_name}:{docker_image_tag}",
            container_name=container_name,
            ports=ports,
            volumes=volumes,
            environment=env,
            cpu_count=int(os.getenv("DOCKER_CPU", 2)),
            cpu_percent=int(os.getenv("DOCKER_CPU_PERCENT", 100)),
            memory_limit=os.getenv("DOCKER_MEM_LMT", "2g"),
            memory_swap=os.getenv("DOCKER_MEM_SWAP", "3g"),
            host_name = os.getenv("DOCKER_HOSTNAME", "cxl-qvp")
        )
        if container == None:
            error_msg(f"Failed to start container: {str(error)}")
            return

        st.rerun()
    except Exception as e:
        error_msg(f"Failed to start container: {str(e)}")

def is_valid_session(remote_server_url, user_id, session_token):
    payload = {
        "user_id" : user_id,
        "session_token" : session_token
    }
    try:
        response = requests.post(
            f"{remote_server_url}/validate_session",
            json=payload,
            timeout=10
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"valid": False, "message": f"Request failed: {str(e)}"}


def main():
    # load envs
    load_dotenv("../.env", override=True)
    manager_ip = os.getenv("MGMT_SERVER_IP")
    manager_port = int(os.getenv("MGMT_SERVER_PORT")) + 1
    url = f"http://{manager_ip}:{manager_port}"

    st.set_page_config(page_title="QVP : CXL Remote Development", layout="wide")
    st.title("QVP : CXL Remote Development")

    query_params = st.query_params
    user_id = query_params.get("user")
    session_token = query_params.get("session_token")

    logger.info(f"Client manager new request : user = {user_id}, session = {session_token}")

    # session params are part of redirect url
    session = is_valid_session(url, user_id, session_token)
    if session.get("valid") == True:
        logger.success(f"Session is valid, rendering page...")
        render_page(user_id)
    else:
        st.error(f"Invalid session. {session.get('message', 'Please log in again.')}")
        logger.error(f"Invalid session. {session.get('message', 'Please log in again.')}")
        st.markdown(f'click [here] to login ({url})')

if __name__ == "__main__":
    main()
    # st.write("hello")
    
