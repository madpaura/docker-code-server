import sqlite3
from loguru import logger

class PortManager:
    def __init__(self, db_path="port_manager.db"):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        """Initialize the database and create the table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS port_allocations (
                    user_id TEXT PRIMARY KEY,
                    code_port_host TEXT,
                    ssh_port_host TEXT,
                    spice_port_host TEXT
                )
            ''')
            conn.commit()

    def allocate_ports(self, user_id):
        """Allocate unique ports to a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if the user already has allocated ports
            cursor.execute("SELECT * FROM port_allocations WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                logger.error(f"Ports already allocated for user {user_id}.")
                return None

            # Find available ports
            allocated_ports = self._get_allocated_ports()
            new_ports = self._find_available_ports(allocated_ports)

            if not new_ports:
                logger.error("No available ports to allocate.")
                return None

            # Allocate ports to the user
            cursor.execute('''
                INSERT INTO port_allocations (user_id, code_port_host, ssh_port_host, spice_port_host)
                VALUES (?, ?, ?, ?)
            ''', (user_id, new_ports["code_port_host"], new_ports["ssh_port_host"], new_ports["spice_port_host"]))
            conn.commit()

            logger.info(f"Ports allocated for user {user_id}: {new_ports}")
            return new_ports

    def deallocate_ports(self, user_id):
        """Deallocate ports from a user and make them available for reuse."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if the user has allocated ports
            cursor.execute("SELECT * FROM port_allocations WHERE user_id = ?", (user_id,))
            user_ports = cursor.fetchone()
            if not user_ports:
                logger.error(f"No ports allocated for user {user_id}.")

            # Deallocate ports
            cursor.execute("DELETE FROM port_allocations WHERE user_id = ?", (user_id,))
            conn.commit()

            logger.success(f"Ports deallocated for user {user_id}: {user_ports[1:]}")
            return None

    def get_allocated_ports(self, user_id):
        """Get allocated ports for a specific user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM port_allocations WHERE user_id = ?", (user_id,))
            user_ports = cursor.fetchone()
            if not user_ports:
                logger.error(f"No ports allocated for user {user_id}.")
                return None

            return {
                "code_port_host": user_ports[1],
                "ssh_port_host": user_ports[2],
                "spice_port_host": user_ports[3]
            }

    def _get_allocated_ports(self):
        """Get all currently allocated ports."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code_port_host, ssh_port_host, spice_port_host FROM port_allocations")
            return cursor.fetchall()

    def _find_available_ports(self, allocated_ports):
        """Find available ports that are not already allocated."""
        base_ports = {
            "code_port_host": 8443,
            "ssh_port_host": 2222,
            "spice_port_host": 3100
        }

        # Convert allocated_ports (list of tuples) to a set of strings for easy comparison
        allocated_ports_set = {f"{p[0]},{p[1]},{p[2]}" for p in allocated_ports}

        # Find the next available ports
        while True:
            new_ports = {
                "code_port_host": str(base_ports["code_port_host"]),
                "ssh_port_host": str(base_ports["ssh_port_host"]),
                "spice_port_host": str(base_ports["spice_port_host"])
            }

            # Check if the new_ports combination is already allocated
            if f"{new_ports['code_port_host']},{new_ports['ssh_port_host']},{new_ports['spice_port_host']}" not in allocated_ports_set:
                return new_ports

            # Increment ports for the next iteration
            base_ports["code_port_host"] += 1
            base_ports["ssh_port_host"] += 1
            base_ports["spice_port_host"] += 1
