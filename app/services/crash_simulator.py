import traceback
import time
import threading


class CrashSimulator:
    def __init__(self):
        self.crash_handlers = {
            "runtime": self._simulate_runtime_error,
            "memory": self._simulate_memory_error,
            "infinite-loop": self._simulate_infinite_loop,
            "network": self._simulate_network_error,
            "state": self._simulate_state_corruption
        }

    def simulate_crash(self, crash_type: str) -> str:
        """Simulate different types of crashes/errors - just for logging, no actual crash."""
        print(f"🔍 CRASH SIMULATOR: simulate_crash() called with type '{crash_type}'")

        if crash_type not in self.crash_handlers:
            print(f"🔍 CRASH SIMULATOR: ❌ Unknown crash type '{crash_type}'")
            return f"Unknown crash type: {crash_type}"

        print(f"🔍 CRASH SIMULATOR: ✅ Valid crash type - simulating '{crash_type}' for logging")

        # Just return a simulated error message without actually crashing
        error_messages = {
            "runtime": "Simulated runtime error: division by zero",
            "memory": "Simulated memory error: out of memory",
            "infinite-loop": "Simulated infinite loop: process stuck in loop",
            "network": "Simulated network error: connection timeout",
            "state": "Simulated state corruption: invalid data state"
        }

        error_message = error_messages.get(crash_type, f"Simulated {crash_type} error")
        print(f"🔍 CRASH SIMULATOR: Generated error message: {error_message}")
        return error_message

    def _simulate_runtime_error(self):
        """Simulate a runtime error."""
        print("🔍 CRASH SIMULATOR: _simulate_runtime_error() called")
        # Divide by zero
        print("🔍 CRASH SIMULATOR: About to divide by zero")
        result = 1 / 0
        print(f"🔍 CRASH SIMULATOR: This should never print: {result}")

    def _simulate_memory_error(self):
        """Simulate a memory-related error."""
        # Try to allocate a huge amount of memory
        huge_list = [0] * (10**9)  # This will likely cause MemoryError

    def _simulate_infinite_loop(self):
        """Simulate an infinite loop that consumes CPU."""
        counter = 0
        while True:
            counter += 1
            # Add a small computation to make it realistic
            if counter % 1000000 == 0:
                time.sleep(0.001)  # Tiny sleep to prevent complete system freeze

    def _simulate_network_error(self):
        """Simulate a network-related error."""
        import socket
        # Try to connect to a non-existent host
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(("192.0.2.1", 80))  # RFC 5737 test address

    def _simulate_state_corruption(self):
        """Simulate state corruption by modifying critical data structures."""
        # Create a corrupted state scenario
        critical_data = {"user_id": 123, "balance": 1000.0}

        # Corrupt the data
        critical_data["balance"] = None
        critical_data["user_id"] = "corrupted_string_instead_of_int"

        # Try to perform operations on corrupted data
        total = critical_data["balance"] + 100  # This will raise TypeError

    def get_stack_trace(self) -> str:
        """Get current stack trace."""
        return traceback.format_exc()


crash_simulator = CrashSimulator()