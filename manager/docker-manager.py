import docker.errors
import docker.models
import docker.models.containers
import streamlit as st
import docker
import pandas as pd
import time
import plotly.graph_objects as go
from datetime import datetime
import dateutil.parser
import webbrowser
import subprocess
import platform
from typing import List, Dict, Optional
import sys
from loguru import logger
from dotenv import load_dotenv
import os
from resource_manager import PortManager
import socket


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


def display_service_actions(container, user):
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Actions")

    port_manager = PortManager()
    ports = port_manager.get_allocated_ports(user)

    container_ip = container.attrs["NetworkSettings"].get("IPAddress") or next(
        (
            net.get("IPAddress", "N/A")
            for net in container.attrs["NetworkSettings"]["Networks"].values()
        ),
        "N/A",
    )

    # Todo : container or machine ip ?
    container_ip = get_machine_ip()
    if st.sidebar.button(f"📝 FW Development"):
        url = f"http://{container_ip}:{ports["code_port_host"]}"
        webbrowser.open(url)

    if st.sidebar.button(f"🖥️ SSH Guest OS"):
        if platform.system() == "Windows":
            subprocess.Popen(
                ["putty", "-ssh", f"root@{container_ip} -p {ports["ssh_port_host"]}"]
            )
        else:
            terminal_cmd = (
                [
                    "gnome-terminal",
                    "--",
                    "ssh",
                    f"root@{container_ip} -p {ports["ssh_port_host"]}",
                ]
                if platform.system() == "Linux"
                else None
            )
            if terminal_cmd:
                logger.info(terminal_cmd)
                subprocess.Popen(terminal_cmd)

    if st.sidebar.button(f"🖥️ RDP Guest OS"):
        try:
            # virt-viewer --direct spice://192.168.1.100:5901
            subprocess.Popen(["virt-viewer", "--direct", f"spice://{container_ip}:{ports["spice_port_host"]}"])
        except Exception as e:
            error_msg(
                f"Failed to launch {service}: {str(e)}",
                (
                    "https://www.spice-space.org/download.html"
                    if service == "RDP"
                    else None
                ),
            )

    with st.sidebar.expander("📡 Connection Info"):
        st.write(f"Container IP: {container_ip}")
        st.write("Default Ports:")
        for service, port in ports.items():
            st.write(f"- {service}: {port}")


def generate_user_hash(username: str) -> str:
    import hashlib

    # Create SHA-256 hash of username
    hash_obj = hashlib.sha256(username.encode())

    # Get first 16 characters of hexadecimal hash
    return hash_obj.hexdigest()[:16]


def render_page(user):
    manager = DockerContainerManager()

    st.set_page_config(page_title="QVP : CXL Remote Development", layout="wide")
    st.title("QVP : CXL Remote Development")

    try:
        client = docker.from_env()
    except Exception as e:
        error_msg(f"Failed to connect to Docker: {str(e)}")
        return

    st.sidebar.markdown("---")
    col1, col2 = st.sidebar.columns([0.7, 0.3])
    with col1:
        st.title("My Instances")
    with col2:
        if st.button("Refresh", icon=":material/refresh:"):
            st.rerun()

    st.header("Available Instances")
    name = get_contianer_name(user)

    container = manager.list_container(name)
    if not container:
        st.info("No containers found")
        if st.button("▶️ Create"):
            create_start_container(manager, user)
        return

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
    selected_container_id = st.selectbox(
        "Select Instance",
        options=[c["Container ID"] for c in container_data],
        format_func=lambda x: f"{x} ({next(c['Name'] for c in container_data if c['Container ID'] == x)})",
    )

    if selected_container_id:
        container = client.containers.get(selected_container_id)
        display_service_actions(container, user)
        display_container_actions(container, user)

        if container.status == "running":
            display_container_stats(container)


def get_contianer_name(user):
    name = f"code-server-{user}-{generate_user_hash(user)}"
    return name


def get_machine_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address

import shutil
import hashlib
import uuid

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

def setup_workdir(user):
    dir_template = os.getenv("WORKDIR_TEMPLATE", "/opt/cxl/")
    dir_deploy = os.getenv("WORKDIR_DEPLOY", "/home/vms/") + f"{user}"

    valid_dir, dir_error = is_valid_dir(dir_deploy)
    valid_sign, sign_error = is_valid_sign(dir_deploy)

    if valid_dir and valid_sign:
        logger.success("Valid workdir exists")
        return True

    logger.warning(f"{dir_error}, {sign_error}")

    try:
        shutil.copytree(dir_template, f"{dir_deploy}/config" )
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Generate a unique hash (using UUID)
        unique_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

        # Create a signature file in the destination directory
        signature_file_path = os.path.join(dir_deploy, 'signature.txt')
        with open(signature_file_path, 'w') as signature_file:
            signature_file.write(f"Timestamp: {timestamp}\n")
            signature_file.write(f"Unique Hash: {unique_hash}\n")

    except Exception as e:
        logger.error(f"Failed setting up workdir for user {user} : Exception {e}")
        return False
    
    return True


def create_start_container(manager, user):
    # Load environment variables from .env file
    load_dotenv(".env", override=True)

    env = {}
    env["PUID"] = 1000
    env["PGID"] = 1000
    env["TZ"] = "Etc/UTC"
    env["DEFAULT_WORKSPACE"] = os.getenv("DEFAULT_WORKSPACE", "/config/workspace")

    docker_image_name = os.getenv("DOCKER_IMAGE", "cxl.io/dev/code-server")
    docker_image_tag = os.getenv("DOCKER_TAG", "latest")

    # user specific needs to configure on-the fly
    hosted_ip = get_machine_ip()
    pwd = os.getenv("PWD")

    if setup_workdir(user) == False:
        error_msg(f"Failed setting up workdir for {user}, please contact admin")
        return

    vm_path = "/home/vms/" + user
    container_name = get_contianer_name(user)
    guest_os_path_host = vm_path + "/os"
    config_path_host = vm_path + "/config"
    qvp_bin_path_host = vm_path + "/qvp"

    port_manager = PortManager()
    new_ports = port_manager.allocate_ports(user)

    code_port_host = new_ports["code_port_host"]
    ssh_port_host = new_ports["ssh_port_host"]
    spice_port_host = new_ports["spice_port_host"]

    volumes = {}
    volumes[guest_os_path_host] = {
        "bind": os.getenv("GUEST_OS_MOUNT", "/opt/os"),
        "mode": "rw",
    }
    volumes[config_path_host] = {
        "bind": os.getenv("CODE_CONFIG_MOUNT", "/config"),
        "mode": "rw",
    }

    volumes[qvp_bin_path_host] = {
        "bind": os.getenv("QVP_BINARY_MOUNT", "/config/qvp"),
        "mode": "rw",
    }

    ports = {}
    ports[os.getenv("CODE_PORT", 8443)] = code_port_host
    ports[os.getenv("GUEST_OS_SSH_PORT", 22)] = ssh_port_host
    ports[os.getenv("GUEST_OS_SPICE_PORT", 8100)] = spice_port_host

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
        )
        if container == None:
            error_msg(f"Failed to start container: {str(error)}")
            return

        st.rerun()
    except Exception as e:
        error_msg(f"Failed to start container: {str(e)}")


def main():
    # render_page("kavana.mv")
    render_page("vishwa.mg")


if __name__ == "__main__":
    main()
    
