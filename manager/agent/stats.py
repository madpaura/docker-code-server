import socket
import json
import threading
import psutil
import docker
from docker.errors import DockerException
import argparse


def get_server_resources():
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

                print(allocated_cpu, allocated_memory)

    except DockerException as e:
        print(f"Error fetching Docker container stats: {e}")
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


def handle_client_connection(client_socket):
    """
    Handle a client connection: receive request and send resource information.
    """
    try:
        # Receive request from client
        request = client_socket.recv(1024).decode("utf-8")
        if request == "get_resources":
            # Fetch server resources
            resources = get_server_resources()
            # Send resources as JSON response
            client_socket.send(json.dumps(resources).encode("utf-8"))
    except Exception as e:
        print(f"Error handling client connection: {e}")
    finally:
        client_socket.close()


def start_resource_publisher(host="0.0.0.0", port=5000):
    """
    Start the resource publisher server to listen for requests.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Resource publisher server started on {host}:{port}")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr}")
        # Handle client connection in a new thread
        client_thread = threading.Thread(
            target=handle_client_connection, args=(client_socket,)
        )
        client_thread.start()


# Run the server in a separate thread
def run_server(port):
    """
    Start the resource publisher server in a background thread.
    """
    server_thread = threading.Thread(target=start_resource_publisher, args=("0.0.0.0", port), daemon=True)
    server_thread.start()
    server_thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the resource publisher server.")
    parser.add_argument("--port", type=int, default=5000, help="The port to run the server on.")
    args = parser.parse_args()

    run_server(args.port)