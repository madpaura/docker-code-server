import psutil
import docker
from docker.errors import DockerException
from loguru import logger
import toml
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import schedule
import time
import socket
import requests
import os, sys
from loguru import logger
from dotenv import load_dotenv
import atexit

load_dotenv(".env", override=True)

app = Flask(__name__)

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

def register_agent(url, agent):
    """Register the agent with the given URL and agent ID."""
    try:
        response = requests.post(f"{url}/register_agent", json={"agent": f"{agent}"})
        logger.info(response.json())
    except Exception as e:
        logger.error(e)

def unregister_agent(url, agent):
    """Unregister the agent with the given URL and agent ID."""
    try:
        response = requests.post(f"{url}/unregister_agent", json={"agent": f"{agent}"})
        logger.info(response.json())
    except Exception as e:
        logger.error(e)

def job():
    """Register the agent every 5 minutes."""
    load_dotenv("../.env", override=True)
    manager_ip = os.getenv("MGMT_SERVER_IP")
    manager_port = int(os.getenv("MGMT_SERVER_PORT")) + 1
    url = f"http://{manager_ip}:{manager_port}"
    localip, publicip = get_machine_ip()
    register_agent(url, localip)


def on_exit():
    load_dotenv("../.env", override=True)
    manager_ip = os.getenv("MGMT_SERVER_IP")
    manager_port = int(os.getenv("MGMT_SERVER_PORT")) + 1
    url = f"http://{manager_ip}:{manager_port}"    
    localip, publicip = get_machine_ip()
    unregister_agent(url, localip)

atexit.register(on_exit)

def get_agent_resources():
    """
    Fetch server resource information (CPU, memory, Docker instances, etc.).
    """
    client = docker.from_env()
    containers = client.containers.list()

    # Get host CPU and memory usage
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent()
    memory_info = psutil.virtual_memory()
    total_memory = memory_info.total / (1024**3)

    docker_instances = 0
    allocated_cpu = 0
    allocated_memory = 0 

    # Calculate Docker resource usage
    try:
        docker_instances = 0
        for container in containers:

            if "code-server" in container.name:
                stats = container.stats(stream=False)
                docker_instances += 1

                # Get allocated CPU (in cores)
                cpu_quota = stats["cpu_stats"].get("cpu_quota", 0)
                cpu_period = stats["cpu_stats"].get("cpu_period", 100000)
                
                container_info = client.api.inspect_container(container.id)
                host_config = container_info.get("HostConfig", {})

                allocated_cpu += host_config.get("CpuCount") 
                allocated_memory += host_config.get("Memory") / (1024 **3)

                logger.info(f"{allocated_cpu}, {allocated_memory}")

    except DockerException as e:
        logger.error(f"Error fetching Docker container stats: {e}")
        docker_instances = 0
        allocated_cpu = 0
        allocated_memory = 0
        
    # Calculate remaining resources
    remaining_cpu = cpu_count - allocated_cpu
    remaining_memory = total_memory - allocated_memory

    return {
        "cpu_count": cpu_count,  # Number of physical CPU cores
        "total_memory": round(total_memory, 2),  # Total installed memory in GB
        "host_cpu_used": cpu_percent,  # CPU usage percentage
        "host_memory_used": round(memory_info.used / (1024**3),2),  # Used memory in GB
        "docker_instances": docker_instances,  # Number of Docker instances
        "allocated_cpu": allocated_cpu,  # Total allocated CPU for containers
        "allocated_memory": round(allocated_memory, 2),  # Total allocated memory for containers in GB
        "remaining_cpu": remaining_cpu,  # Remaining CPU cores
        "remaining_memory": round(remaining_memory, 2),  # Remaining memory in GB
    }


@app.route('/get_resources', methods=['GET'])
def get_resources():
    """
    Handle GET request to fetch agents resources.
    """
    resources = get_agent_resources()
    print(resources)
    return jsonify(resources)

if __name__ == "__main__":
    config_path = os.path.join('.streamlit', 'config.toml')
    if os.path.exists(config_path):
        config = toml.load(config_path)
        port = config.get('server', {}).get('stats_port', 8511)
    else:
        port = 8511

    job()
    # schedule.every(5).seconds.do(job)  # Run the job every 5 minutes

    app.run(host="0.0.0.0", port=port)
    
