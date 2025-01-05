import socket
import json

def query_server_resources(server_host, server_port=5000):
    """
    Query a single server for its resource information.
    """
    try:
        # Create a socket and connect to the server
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_host, server_port))
        
        # Send request to the server
        client_socket.send("get_resources".encode('utf-8'))
        
        # Receive response from the server
        response = client_socket.recv(1024).decode('utf-8')
        client_socket.close()
        
        # Parse the JSON response
        return json.loads(response)
    except Exception as e:
        print(f"Error querying server {server_host}:{server_port}: {e}")
        return None

def query_available_servers(server_list, port):
    """
    Query multiple servers for their resource information.
    """
    servers_resources = []
    for server in server_list:
        resources = query_server_resources(server, server_port=port)
        if resources:
            resources["server_id"] = server
            servers_resources.append(resources)
    return servers_resources


# if __name__ == "__main__":
#     servers = ["0.0.0.0", "0.0.0.0", "0.0.0.0"]
#     print(query_available_servers(servers))