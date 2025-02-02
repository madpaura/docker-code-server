from flask import request, jsonify, send_from_directory
import docker
import docker.errors
import docker.models
import docker.models.containers
import dateutil.parser
import subprocess
import shutil
import uuid
import os
import threading
import hashlib
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

from resource_manager import PortManager

# Configure logger
logger.add("agent_service.log", rotation="500 MB", retention="10 days", level="INFO")

# Load environment variables
load_dotenv(".env", override=True)


class DockerContainerManager:
    def __init__(self):
        """Initialize Docker client and lock"""
        try:
            self.client = docker.from_env()
            self.lock = threading.Lock()
        except docker.errors.DockerException as e:
            logger.error(f"Error connecting to Docker daemon: {e}")
            raise

    def create_container(
        self,
        image_name,
        container_name=None,
        ports=None,
        volumes=None,
        environment=None,
        command=None,
        detach=True,
        cpu_count=None,
        cpu_percent=None,
        memory_limit=None,
        memory_swap=None,
        memory_reservation=None,
        host_name="cx-qvp",
    ):
        self.lock.acquire()
        try:
            try:
                self.client.images.get(image_name)
            except docker.errors.ImageNotFound:
                logger.warning(f"Pulling image {image_name}...")
                try:
                    image = self.client.images.pull(image_name)
                except docker.errors.APIError as e:
                    logger.error("Failed pulling image")
                    return None, f"Failed pulling image {image_name} Exception : {e}"

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
                privileged=True,
            )
            logger.success(f"Container created successfully: {container.name}")
            return container, "Success"

        except docker.errors.APIError as e:
            logger.error(f"Error creating container: {e}")
            return None, f"Error creating container: {e}"
        finally:
            self.lock.release()

    def list_container(self, name):
        self.lock.acquire()
        try:
            container = self.client.containers.get(name)
            return container
        except docker.errors.NotFound:
            logger.error(f"Container {name} not found")
            return None
        except docker.errors.APIError as e:
            logger.error(f"Error getting container: {e}")
            return None
        finally:
            self.lock.release()

    def start_container(self, container_id_or_name):
        self.lock.acquire()
        try:
            container = self.client.containers.get(container_id_or_name)
            container.start()
            logger.success(f"Container {container_id_or_name} started successfully")
            return True
        except docker.errors.NotFound:
            logger.error(f"Container {container_id_or_name} not found")
            return False
        except docker.errors.APIError as e:
            logger.error(f"Error stopping container: {e}")
            return False
        finally:
            self.lock.release()

    def stop_container(self, container_id_or_name):
        self.lock.acquire()
        try:
            container = self.client.containers.get(container_id_or_name)
            container.stop()
            logger.success(f"Container {container_id_or_name} stopped successfully")
            return True
        except docker.errors.NotFound:
            logger.error(f"Container {container_id_or_name} not found")
            return False
        except docker.errors.APIError as e:
            logger.error(f"Error stopping container: {e}")
            return False
        finally:
            self.lock.release()


    def restart_container(self, container_id_or_name):
        self.lock.acquire()
        try:
            container = self.client.containers.get(container_id_or_name)
            container.restart()
            logger.success(f"Container {container_id_or_name} restarted successfully")
            return True
        except docker.errors.NotFound:
            logger.error(f"Container {container_id_or_name} not found")
            return False
        except docker.errors.APIError as e:
            logger.error(f"Error stopping container: {e}")
            return False
        finally:
            self.lock.release()

    def remove_container(self, container_id_or_name, force=False):
        self.lock.acquire()
        try:
            container = self.client.containers.get(container_id_or_name)
            container.remove(force=force)
            logger.success(f"Container {container_id_or_name} removed successfully")
            return True
        except docker.errors.NotFound:
            logger.error(f"Container {container_id_or_name} not found")
            return False
        except docker.errors.APIError as e:
            logger.error(f"Error removing container: {e}")
            return False
        finally:
            self.lock.release()

    def get_container_stats(self, container):
        self.lock.acquire()
        try:
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
                logger.error(f"Error calculating stats: {str(e)}")
                return {
                    "cpu_usage": 0,
                    "memory_usage": 0,
                    "memory_used": 0,
                    "memory_limit": 0,
                }
        finally:
            self.lock.release()


class DockerHelper:
    def is_valid_dir(self, dir):
        if not os.path.exists(dir):
            return False, "Destination directory does not exist."
        if not os.path.isdir(dir):
            return False, "Destination path is not a directory."
        if not os.listdir(dir):
            return False, "Destination directory is empty."
        return True, "Destination directory is valid."

    def is_valid_sign(self, dir):
        signature_file = f"{dir}/signature.txt"
        if not os.path.exists(signature_file):
            return False, "Signature file does not exist."
        with open(signature_file, "r") as file:
            content = file.read()
            if "Timestamp:" not in content or "Unique Hash:" not in content:
                return False, "Signature file is missing required content."
        return True, "Signature file is valid."

    def generate_user_hash(self, username: str) -> str:
        hash_obj = hashlib.sha256(username.encode())
        return hash_obj.hexdigest()[:16]

    def setup_workdir(self, user, dir_template, dir_deploy):
        valid_dir, dir_error = self.is_valid_dir(dir_deploy)
        valid_sign, sign_error = self.is_valid_sign(dir_deploy)

        if valid_dir and valid_sign:
            logger.success("Valid workdir exists")
            return True

        logger.warning(f"{dir_error}, {sign_error}")

        try:
            os.makedirs(dir_deploy, exist_ok=True)

            for item in os.listdir(dir_template):
                src_path = os.path.join(dir_template, item)
                dst_path = os.path.join(dir_deploy, item)

                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                elif os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            unique_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
            signature_file_path = os.path.join(dir_deploy, "signature.txt")
            with open(signature_file_path, "w") as signature_file:
                signature_file.write(f"Timestamp: {timestamp}\n")
                signature_file.write(f"Unique Hash: {unique_hash}\n")

            return True
        except Exception as e:
            logger.error(f"Failed setting up workdir for user {user}: {e}")
            return False

    def create_overlay(self, base_image_path, overlay_image_path):
        try:
            command = f"qemu-img create -f qcow2 -b {base_image_path} -F qcow2 {overlay_image_path}"
            subprocess.check_call(command, shell=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create overlay image: {e}")
            return False

    def get_contianer_name(self, user):
        name = f"code-server-{user}-{self.generate_user_hash(user)}"
        return name


# Initialize Docker manager
docker_manager = DockerContainerManager()
docker_helper = DockerHelper()

# Static file serving directory
STATIC_DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/downloads')

# Ensure the downloads directory exists
os.makedirs(STATIC_DOWNLOADS_DIR, exist_ok=True)

def init_backend_routes(app):
    @app.route('/downloads/<path:filename>')
    def download_file(filename):
        return send_from_directory(STATIC_DOWNLOADS_DIR, filename, as_attachment=True)

    @app.route("/api/containers", methods=["POST"])
    def create_container():
        data = request.get_json()
        user = data["user"]
        session_token = data["session_token"]

        load_dotenv("../.env", override=True)
        env = {
            "PUID": os.geteuid(),
            "PGID": os.getegid(),
            "TZ": "Etc/UTC",
            "DEFAULT_WORKSPACE": os.getenv("DEFAULT_WORKSPACE", "/config/workspace"),
            "SUDO_PASSWORD": os.getenv("SUDO_PASSWORD", "abc"),
        }

        docker_image_name = os.getenv("DOCKER_IMAGE", "cxl.io/dev/code-server")
        docker_image_tag = os.getenv("DOCKER_TAG", "latest")

        dir_template = os.getenv("WORKDIR_TEMPLATE", "/opt/cxl/")
        dir_deploy = (
            os.getenv("WORKDIR_DEPLOY", "/home/vms/")
            + f"{user}-{docker_helper.generate_user_hash(user)}"
        )

        if not docker_helper.setup_workdir(user, dir_template, dir_deploy):
            return jsonify({"success": False, "error": "Failed setting up work dir"}), 400

        guest_os_list = [item.strip() for item in os.getenv("GUEST_OS_LIST").split(",")]
        for guest_os in guest_os_list:
            dst_path = (
                f"{dir_deploy}/guestos/{os.path.basename(os.path.dirname(guest_os))}"
            )
            os.makedirs(dst_path, exist_ok=True)
            file_name = os.path.basename(guest_os)
            name, ext = os.path.splitext(file_name)
            new_file_name = f"{dst_path}/{name}_overlay{ext}"

            if not docker_helper.create_overlay(guest_os, new_file_name):
                return jsonify({"success": False, "error": "Failed creating guest os overlay"}), 400

        # TODO revamp this section
        container_name = docker_helper.get_contianer_name(user)
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
            container, error = docker_manager.create_container(
                image_name=f"{docker_image_name}:{docker_image_tag}",
                container_name=container_name,
                ports=ports,
                volumes=volumes,
                environment=env,
                cpu_count=int(os.getenv("DOCKER_CPU", 2)),
                cpu_percent=int(os.getenv("DOCKER_CPU_PERCENT", 100)),
                memory_limit=os.getenv("DOCKER_MEM_LMT", "2g"),
                memory_swap=os.getenv("DOCKER_MEM_SWAP", "3g"),
                host_name=os.getenv("DOCKER_HOSTNAME", "cxl-qvp"),
            )

            if container:
                logger.success(f"Created container: {str(container.id)}")
                return jsonify(
                    {
                        "success": True,
                        "container": {
                            "id": container.id,
                            "name": container.name,
                            "status": container.status,
                        },
                    }
                )
            logger.error(f"Failed to start container: {str(error)}")
            return jsonify({"success": False, "error": {str(error)}}), 400

        except Exception as e:
            logger.error(f"Failed to start container: {str(e)}")
            return jsonify({"success": False, "error": {str(error)}}), 400

    @app.route("/api/containers/<string:name>", methods=["GET"])
    def get_container(name):
        container = docker_manager.list_container(name)
        if container:
            return jsonify(
                {
                    "success": True,
                    "container": {
                        "id": container.id,
                        "name": container.name,
                        "status": container.status,
                        "image": (
                            container.image.tags[0] if container.image.tags else "None"
                        ),
                        "created": container.attrs["Created"],
                    },
                }
            )
        return jsonify({"success": False, "error": "Container not found"}), 404

    @app.route("/api/containers/<string:container_id>/start", methods=["POST"])
    def start_container(container_id):
        if docker_manager.start_container(container_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Failed to stop container"}), 400

    @app.route("/api/containers/<string:container_id>/stop", methods=["POST"])
    def stop_container(container_id):
        if docker_manager.stop_container(container_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Failed to stop container"}), 400

    @app.route("/api/containers/<string:container_id>/remove", methods=["POST"])
    def remove_container(container_id):
        if docker_manager.remove_container(container_id, force=True):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Failed to remove container"}), 400

    @app.route("/api/containers/<string:container_id>/restart", methods=["POST"])
    def restart_container(container_id):
        if docker_manager.restart_container(container_id):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Failed to remove container"}), 400
    
    @app.route("/api/containers/<string:container_id>/stats", methods=["GET"])
    def get_stats(container_id):
        container = docker_manager.list_container(container_id)
        if container:
            stats = docker_manager.get_container_stats(container)
            return jsonify({"success": True, "stats": stats})
        return jsonify({"success": False, "error": "Container not found"}), 404

    @app.route("/api/containers/<string:container_id>/ports", methods=["GET"])
    def get_port_info(container_id):
        port_manager = PortManager()
        new_ports = port_manager.get_allocated_ports(container_id)
        start_port = int(new_ports["start_port"])
        
        port_info = {
            "code_port": start_port,
            "ssh_port": start_port + 1,
            "spice_port": start_port + 2,
            "fm_ui_port": start_port + 3,
            "fm_port": start_port + 4
        }
        
        return jsonify(port_info)