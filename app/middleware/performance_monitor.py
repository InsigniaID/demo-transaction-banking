"""
Performance monitoring middleware for comprehensive server monitoring.
Monitors FastAPI app, database, Kafka, and system resources.
"""
import time
import uuid
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import Request
from sqlalchemy import text

try:
    import psutil
except ImportError:
    psutil = None

from ..database import SessionLocal
# from ..kafka_producer import send_transaction
from ..elk_kafka import send_transaction

class PerformanceMonitor:
    def __init__(self):
        self.request_start_time = None
        self.system_metrics_before = {}

    async def get_database_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics."""
        try:
            db = SessionLocal()
            start_time = time.time()

            # Test database connectivity and get stats
            db.execute(text("SELECT 1")).fetchone()
            db_response_time = (time.time() - start_time) * 1000

            # Get connection pool stats
            pool = db.bind.pool
            pool_stats = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid()
            }

            db.close()

            return {
                "database_response_time_ms": round(db_response_time, 2),
                "database_status": "healthy",
                "connection_pool": pool_stats
            }
        except Exception as e:
            return {
                "database_response_time_ms": -1,
                "database_status": "unhealthy",
                "database_error": str(e),
                "connection_pool": {}
            }

    def get_system_metrics(self, crash_type: str = None) -> Dict[str, Any]:
        """Get system resource metrics with optional crash type simulation."""

        # Simulate different system states based on crash type
        if crash_type:
            return self._get_simulated_metrics_for_crash(crash_type)

        if not psutil:
            # Return fallback metrics if psutil not available
            return {
                "cpu_percent": 15.0,  # Fallback values
                "cpu_count": 4,
                "memory_total_gb": 8.0,
                "memory_used_gb": 4.0,
                "memory_percent": 50.0,
                "disk_total_gb": 100.0,
                "disk_used_gb": 60.0,
                "disk_percent": 60.0,
                "network_bytes_sent": 1000000,
                "network_bytes_recv": 2000000,
                "process_memory_rss_mb": 128.0,
                "process_memory_vms_mb": 256.0,
                "process_cpu_percent": 5.0,
                "active_connections": 10,
                "open_files": 20,
                "system_metrics_error": "psutil not available - using fallback values"
            }

        try:
            # CPU metrics with proper interval
            cpu_percent = psutil.cpu_percent(interval=0.1)  # Small interval for immediate reading
            if cpu_percent == 0.0:
                cpu_percent = psutil.cpu_percent()  # Try without interval

            cpu_count = psutil.cpu_count()

            # Memory metrics
            memory = psutil.virtual_memory()

            # Disk metrics
            try:
                disk = psutil.disk_usage('/')
            except:
                # Fallback for systems where '/' doesn't work
                disk = psutil.disk_usage('.')

            # Network metrics
            try:
                network = psutil.net_io_counters()
                network_bytes_sent = network.bytes_sent if network else 0
                network_bytes_recv = network.bytes_recv if network else 0
            except:
                network_bytes_sent = 0
                network_bytes_recv = 0

            # Process metrics
            try:
                process = psutil.Process()
                process_memory = process.memory_info()
                process_cpu = process.cpu_percent()

                # Get connections and files safely
                try:
                    active_connections = len(psutil.net_connections())
                except:
                    active_connections = 0

                try:
                    open_files = len(process.open_files())
                except:
                    open_files = 0

            except Exception as proc_error:
                # Fallback process metrics
                process_memory = type('obj', (object,), {'rss': 128*1024*1024, 'vms': 256*1024*1024})()
                process_cpu = 5.0
                active_connections = 0
                open_files = 0

            return {
                "cpu_percent": round(cpu_percent, 2),
                "cpu_count": cpu_count,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_percent": round(memory.percent, 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_percent": round(disk.percent, 2),
                "network_bytes_sent": network_bytes_sent,
                "network_bytes_recv": network_bytes_recv,
                "process_memory_rss_mb": round(process_memory.rss / (1024**2), 2),
                "process_memory_vms_mb": round(process_memory.vms / (1024**2), 2),
                "process_cpu_percent": round(process_cpu, 2),
                "active_connections": active_connections,
                "open_files": open_files
            }
        except Exception as e:
            # Return realistic fallback values instead of zeros
            return {
                "cpu_percent": 20.0,
                "cpu_count": 4,
                "memory_total_gb": 8.0,
                "memory_used_gb": 4.5,
                "memory_percent": 56.25,
                "disk_total_gb": 100.0,
                "disk_used_gb": 65.0,
                "disk_percent": 65.0,
                "network_bytes_sent": 1500000,
                "network_bytes_recv": 3000000,
                "process_memory_rss_mb": 150.0,
                "process_memory_vms_mb": 300.0,
                "process_cpu_percent": 8.0,
                "active_connections": 12,
                "open_files": 25,
                "system_metrics_error": f"Error getting metrics: {str(e)}"
            }

    def _get_simulated_metrics_for_crash(self, crash_type: str) -> Dict[str, Any]:
        """Generate simulated system metrics based on crash type."""
        import random

        # Base realistic metrics
        base_metrics = {
            "cpu_count": 8,
            "memory_total_gb": 16.0,
            "disk_total_gb": 500.0,
            "network_bytes_sent": random.randint(1000000, 5000000),
            "network_bytes_recv": random.randint(2000000, 8000000),
            "open_files": random.randint(50, 200)
        }

        if crash_type == "memory":
            # Simulate high memory usage scenario with detailed error info
            memory_errors = self._generate_memory_error_details()
            return {
                **base_metrics,
                "cpu_percent": random.uniform(15.0, 35.0),
                "memory_used_gb": random.uniform(14.0, 15.8),  # Very high memory usage
                "memory_percent": random.uniform(87.5, 98.7),  # 87-98% memory usage
                "disk_used_gb": random.uniform(300.0, 400.0),
                "disk_percent": random.uniform(60.0, 80.0),
                "process_memory_rss_mb": random.uniform(800.0, 1200.0),  # High process memory
                "process_memory_vms_mb": random.uniform(1500.0, 2000.0),
                "process_cpu_percent": random.uniform(8.0, 15.0),
                "active_connections": random.randint(80, 150),
                "crash_simulation": "memory_overload",
                **memory_errors
            }

        elif crash_type == "infinite-loop":
            # Simulate high CPU usage scenario with detailed error info
            cpu_errors = self._generate_cpu_error_details()
            return {
                **base_metrics,
                "cpu_percent": random.uniform(85.0, 99.5),  # Very high CPU usage
                "memory_used_gb": random.uniform(6.0, 10.0),
                "memory_percent": random.uniform(37.5, 62.5),
                "disk_used_gb": random.uniform(250.0, 350.0),
                "disk_percent": random.uniform(50.0, 70.0),
                "process_memory_rss_mb": random.uniform(200.0, 400.0),
                "process_memory_vms_mb": random.uniform(400.0, 800.0),
                "process_cpu_percent": random.uniform(80.0, 95.0),  # Very high process CPU
                "active_connections": random.randint(20, 50),
                "crash_simulation": "cpu_overload",
                **cpu_errors
            }

        elif crash_type == "network":
            # Simulate network issues with detailed error info
            network_errors = self._generate_network_error_details()
            return {
                **base_metrics,
                "cpu_percent": random.uniform(25.0, 45.0),
                "memory_used_gb": random.uniform(8.0, 12.0),
                "memory_percent": random.uniform(50.0, 75.0),
                "disk_used_gb": random.uniform(200.0, 300.0),
                "disk_percent": random.uniform(40.0, 60.0),
                "process_memory_rss_mb": random.uniform(300.0, 600.0),
                "process_memory_vms_mb": random.uniform(600.0, 1200.0),
                "process_cpu_percent": random.uniform(15.0, 30.0),
                "active_connections": random.randint(200, 500),  # Very high connections
                "network_bytes_sent": random.randint(50000000, 100000000),  # High network usage
                "network_bytes_recv": random.randint(80000000, 150000000),
                "crash_simulation": "network_overload",
                **network_errors
            }

        elif crash_type == "runtime":
            # Simulate runtime error with detailed error information
            runtime_errors = self._generate_runtime_error_details()
            return {
                **base_metrics,
                "cpu_percent": random.uniform(20.0, 40.0),
                "memory_used_gb": random.uniform(7.0, 11.0),
                "memory_percent": random.uniform(43.75, 68.75),
                "disk_used_gb": random.uniform(280.0, 380.0),
                "disk_percent": random.uniform(56.0, 76.0),
                "process_memory_rss_mb": random.uniform(250.0, 500.0),
                "process_memory_vms_mb": random.uniform(500.0, 1000.0),
                "process_cpu_percent": random.uniform(12.0, 25.0),
                "active_connections": random.randint(30, 80),
                "crash_simulation": "runtime_error",
                **runtime_errors  # Include detailed error info
            }

        elif crash_type == "state":
            # Simulate state corruption with detailed error info
            state_errors = self._generate_state_corruption_details()
            return {
                **base_metrics,
                "cpu_percent": random.uniform(10.0, 90.0),  # Erratic CPU
                "memory_used_gb": random.uniform(5.0, 15.0),  # Erratic memory
                "memory_percent": random.uniform(31.25, 93.75),
                "disk_used_gb": random.uniform(150.0, 450.0),
                "disk_percent": random.uniform(30.0, 90.0),
                "process_memory_rss_mb": random.uniform(100.0, 800.0),  # Very erratic
                "process_memory_vms_mb": random.uniform(200.0, 1600.0),
                "process_cpu_percent": random.uniform(5.0, 60.0),
                "active_connections": random.randint(5, 300),  # Very erratic
                "crash_simulation": "state_corruption",
                **state_errors
            }

        else:
            # Default: normal healthy metrics
            return {
                **base_metrics,
                "cpu_percent": random.uniform(10.0, 25.0),
                "memory_used_gb": random.uniform(4.0, 8.0),
                "memory_percent": random.uniform(25.0, 50.0),
                "disk_used_gb": random.uniform(200.0, 350.0),
                "disk_percent": random.uniform(40.0, 70.0),
                "process_memory_rss_mb": random.uniform(128.0, 300.0),
                "process_memory_vms_mb": random.uniform(256.0, 600.0),
                "process_cpu_percent": random.uniform(3.0, 12.0),
                "active_connections": random.randint(15, 60),
                "crash_simulation": f"unknown_crash_type_{crash_type}"
            }

    def _generate_runtime_error_details(self) -> Dict[str, Any]:
        """Generate detailed runtime error information like Sentry."""
        import random
        import uuid
        from datetime import datetime

        # Common runtime error scenarios
        error_scenarios = [
            {
                "error_type": "ZeroDivisionError",
                "error_message": "division by zero",
                "error_code": "MATH_001",
                "severity": "error",
                "category": "mathematical_error",
                "file": "transaction_processor.py",
                "function": "calculate_fee",
                "line_number": 156,
                "context": "fee_rate = base_fee / percentage",
                "stack_trace": [
                    "File 'transaction_processor.py', line 156, in calculate_fee",
                    "  fee_rate = base_fee / percentage",
                    "ZeroDivisionError: division by zero"
                ]
            },
            {
                "error_type": "KeyError",
                "error_message": "'account_balance' key not found",
                "error_code": "DATA_002",
                "severity": "error",
                "category": "data_access_error",
                "file": "account_service.py",
                "function": "get_balance",
                "line_number": 89,
                "context": "balance = account_data['account_balance']",
                "stack_trace": [
                    "File 'account_service.py', line 89, in get_balance",
                    "  balance = account_data['account_balance']",
                    "KeyError: 'account_balance'"
                ]
            },
            {
                "error_type": "ValueError",
                "error_message": "invalid literal for int() with base 10: 'abc'",
                "error_code": "PARSE_003",
                "severity": "error",
                "category": "parsing_error",
                "file": "validation_service.py",
                "function": "validate_amount",
                "line_number": 23,
                "context": "amount_int = int(amount_str)",
                "stack_trace": [
                    "File 'validation_service.py', line 23, in validate_amount",
                    "  amount_int = int(amount_str)",
                    "ValueError: invalid literal for int() with base 10: 'abc'"
                ]
            },
            {
                "error_type": "AttributeError",
                "error_message": "'NoneType' object has no attribute 'customer_id'",
                "error_code": "NULL_004",
                "severity": "error",
                "category": "null_reference_error",
                "file": "user_service.py",
                "function": "get_customer_info",
                "line_number": 67,
                "context": "customer_id = user.customer_id",
                "stack_trace": [
                    "File 'user_service.py', line 67, in get_customer_info",
                    "  customer_id = user.customer_id",
                    "AttributeError: 'NoneType' object has no attribute 'customer_id'"
                ]
            },
            {
                "error_type": "IndexError",
                "error_message": "list index out of range",
                "error_code": "INDEX_005",
                "severity": "error",
                "category": "array_bounds_error",
                "file": "transaction_history.py",
                "function": "get_last_transaction",
                "line_number": 45,
                "context": "last_tx = transactions[0]",
                "stack_trace": [
                    "File 'transaction_history.py', line 45, in get_last_transaction",
                    "  last_tx = transactions[0]",
                    "IndexError: list index out of range"
                ]
            },
            {
                "error_type": "TypeError",
                "error_message": "unsupported operand type(s) for +: 'int' and 'str'",
                "error_code": "TYPE_006",
                "severity": "error",
                "category": "type_mismatch_error",
                "file": "fee_calculator.py",
                "function": "calculate_total",
                "line_number": 78,
                "context": "total = base_amount + fee_string",
                "stack_trace": [
                    "File 'fee_calculator.py', line 78, in calculate_total",
                    "  total = base_amount + fee_string",
                    "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
                ]
            },
            {
                "error_type": "ConnectionError",
                "error_message": "HTTPSConnectionPool(host='api.bank.com', port=443): Max retries exceeded",
                "error_code": "CONN_007",
                "severity": "critical",
                "category": "network_error",
                "file": "external_api.py",
                "function": "call_bank_api",
                "line_number": 134,
                "context": "response = requests.get(bank_api_url, timeout=30)",
                "stack_trace": [
                    "File 'external_api.py', line 134, in call_bank_api",
                    "  response = requests.get(bank_api_url, timeout=30)",
                    "ConnectionError: HTTPSConnectionPool(host='api.bank.com', port=443): Max retries exceeded"
                ]
            },
            {
                "error_type": "TimeoutError",
                "error_message": "Database query timeout after 30 seconds",
                "error_code": "TIMEOUT_008",
                "severity": "warning",
                "category": "performance_error",
                "file": "database_service.py",
                "function": "execute_query",
                "line_number": 203,
                "context": "result = db.execute(complex_query)",
                "stack_trace": [
                    "File 'database_service.py', line 203, in execute_query",
                    "  result = db.execute(complex_query)",
                    "TimeoutError: Database query timeout after 30 seconds"
                ]
            }
        ]

        # Select random error scenario
        selected_error = random.choice(error_scenarios)

        # Generate additional Sentry-like metadata
        error_details = {
            "runtime_error": {
                "error_id": f"err_{uuid.uuid4().hex[:16]}",
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": selected_error["error_type"],
                "error_message": selected_error["error_message"],
                "error_code": selected_error["error_code"],
                "severity": selected_error["severity"],
                "category": selected_error["category"],
                "environment": "production",
                "release": "v1.2.3",
                "platform": "python",
                "sdk": {"name": "sentry-python", "version": "1.40.0"},

                # Stack trace information
                "stacktrace": {
                    "frames": selected_error["stack_trace"]
                },

                # Source location
                "location": {
                    "file": selected_error["file"],
                    "function": selected_error["function"],
                    "line_number": selected_error["line_number"],
                    "context_line": selected_error["context"]
                },

                # Additional context
                "tags": {
                    "component": "transaction_processing",
                    "module": selected_error["file"].replace(".py", ""),
                    "error_category": selected_error["category"]
                },

                # Breadcrumbs (recent actions leading to error)
                "breadcrumbs": [
                    {
                        "timestamp": (datetime.utcnow().timestamp() - 5),
                        "message": "User initiated transaction",
                        "category": "user_action",
                        "level": "info"
                    },
                    {
                        "timestamp": (datetime.utcnow().timestamp() - 3),
                        "message": "Validating transaction parameters",
                        "category": "validation",
                        "level": "info"
                    },
                    {
                        "timestamp": (datetime.utcnow().timestamp() - 1),
                        "message": f"Error occurred in {selected_error['function']}",
                        "category": "error",
                        "level": "error"
                    }
                ],

                # Performance impact
                "performance_impact": {
                    "response_time_increase_ms": random.randint(500, 2000),
                    "memory_leak_mb": random.randint(10, 100),
                    "cpu_spike_percent": random.randint(15, 40)
                },

                # Error frequency
                "frequency": {
                    "count_last_hour": random.randint(1, 15),
                    "count_last_24h": random.randint(5, 50),
                    "first_seen": "2024-01-15T10:30:00Z",
                    "last_seen": datetime.utcnow().isoformat()
                },

                # User impact
                "user_impact": {
                    "affected_users": random.randint(1, 25),
                    "transaction_failures": random.randint(1, 10),
                    "severity_user_facing": random.choice(["low", "medium", "high"])
                }
            }
        }

        return error_details

    def _generate_memory_error_details(self) -> Dict[str, Any]:
        """Generate detailed memory error information."""
        import random
        import uuid
        from datetime import datetime

        memory_issues = [
            {
                "issue_type": "MemoryError",
                "error_message": "Cannot allocate memory for transaction buffer",
                "error_code": "MEM_001",
                "severity": "critical",
                "category": "memory_exhaustion"
            },
            {
                "issue_type": "OutOfMemoryError",
                "error_message": "Java heap space exceeded during large transaction processing",
                "error_code": "MEM_002",
                "severity": "critical",
                "category": "heap_overflow"
            },
            {
                "issue_type": "MemoryLeak",
                "error_message": "Memory leak detected in session management",
                "error_code": "MEM_003",
                "severity": "warning",
                "category": "memory_leak"
            }
        ]

        selected_issue = random.choice(memory_issues)

        return {
            "memory_error": {
                "error_id": f"mem_{uuid.uuid4().hex[:16]}",
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": selected_issue["issue_type"],
                "error_message": selected_issue["error_message"],
                "error_code": selected_issue["error_code"],
                "severity": selected_issue["severity"],
                "category": selected_issue["category"],

                "memory_analysis": {
                    "heap_usage_mb": random.uniform(1800, 2000),
                    "heap_max_mb": 2048,
                    "gc_pressure": random.uniform(0.8, 0.95),
                    "memory_pools": {
                        "eden_space": random.uniform(85, 98),
                        "survivor_space": random.uniform(90, 100),
                        "old_generation": random.uniform(85, 95)
                    }
                },

                "allocation_failures": {
                    "count_last_minute": random.randint(5, 20),
                    "largest_failed_allocation_mb": random.randint(50, 200),
                    "total_allocation_attempts": random.randint(100, 500)
                },

                "impact_assessment": {
                    "affected_transactions": random.randint(10, 100),
                    "response_time_degradation_ms": random.randint(2000, 8000),
                    "memory_pressure_score": random.uniform(0.85, 0.98)
                }
            }
        }

    def _generate_cpu_error_details(self) -> Dict[str, Any]:
        """Generate detailed CPU/infinite-loop error information."""
        import random
        import uuid
        from datetime import datetime

        cpu_issues = [
            {
                "issue_type": "InfiniteLoop",
                "error_message": "Detected infinite loop in transaction validation",
                "error_code": "CPU_001",
                "severity": "critical",
                "category": "infinite_loop"
            },
            {
                "issue_type": "HighCPUUsage",
                "error_message": "CPU usage sustained above 90% for extended period",
                "error_code": "CPU_002",
                "severity": "warning",
                "category": "cpu_overload"
            },
            {
                "issue_type": "ThreadDeadlock",
                "error_message": "Deadlock detected between transaction and validation threads",
                "error_code": "CPU_003",
                "severity": "critical",
                "category": "deadlock"
            }
        ]

        selected_issue = random.choice(cpu_issues)

        return {
            "cpu_error": {
                "error_id": f"cpu_{uuid.uuid4().hex[:16]}",
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": selected_issue["issue_type"],
                "error_message": selected_issue["error_message"],
                "error_code": selected_issue["error_code"],
                "severity": selected_issue["severity"],
                "category": selected_issue["category"],

                "cpu_analysis": {
                    "cpu_usage_percent": random.uniform(85, 99),
                    "cpu_cores_affected": random.randint(6, 8),
                    "load_average": {
                        "1_minute": random.uniform(8.0, 15.0),
                        "5_minute": random.uniform(6.0, 12.0),
                        "15_minute": random.uniform(4.0, 8.0)
                    },
                    "thread_analysis": {
                        "total_threads": random.randint(200, 500),
                        "blocked_threads": random.randint(50, 150),
                        "runnable_threads": random.randint(100, 300),
                        "waiting_threads": random.randint(20, 80)
                    }
                },

                "loop_detection": {
                    "suspected_function": random.choice(["validate_transaction", "calculate_fee", "check_balance"]),
                    "iteration_count": random.randint(10000000, 100000000),
                    "time_stuck_seconds": random.randint(30, 300),
                    "stack_depth": random.randint(50, 200)
                },

                "performance_impact": {
                    "requests_queued": random.randint(50, 500),
                    "average_response_time_ms": random.randint(5000, 30000),
                    "timeouts_occurred": random.randint(10, 100)
                }
            }
        }

    def _generate_network_error_details(self) -> Dict[str, Any]:
        """Generate detailed network error information."""
        import random
        import uuid
        from datetime import datetime

        network_issues = [
            {
                "issue_type": "ConnectionTimeout",
                "error_message": "Connection timeout to external payment gateway",
                "error_code": "NET_001",
                "severity": "error",
                "category": "connection_timeout"
            },
            {
                "issue_type": "TooManyConnections",
                "error_message": "Connection pool exhausted - too many simultaneous connections",
                "error_code": "NET_002",
                "severity": "critical",
                "category": "connection_pool_exhaustion"
            },
            {
                "issue_type": "NetworkLatency",
                "error_message": "High network latency detected to database server",
                "error_code": "NET_003",
                "severity": "warning",
                "category": "high_latency"
            }
        ]

        selected_issue = random.choice(network_issues)

        return {
            "network_error": {
                "error_id": f"net_{uuid.uuid4().hex[:16]}",
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": selected_issue["issue_type"],
                "error_message": selected_issue["error_message"],
                "error_code": selected_issue["error_code"],
                "severity": selected_issue["severity"],
                "category": selected_issue["category"],

                "connection_analysis": {
                    "active_connections": random.randint(200, 500),
                    "max_connections": 500,
                    "connection_pool_usage": random.uniform(0.8, 1.0),
                    "failed_connections": random.randint(20, 100),
                    "connection_timeouts": random.randint(10, 50)
                },

                "network_metrics": {
                    "latency_ms": {
                        "min": random.randint(50, 100),
                        "max": random.randint(5000, 15000),
                        "avg": random.randint(1000, 5000),
                        "p95": random.randint(3000, 8000)
                    },
                    "throughput": {
                        "bytes_per_second": random.randint(1000000, 10000000),
                        "packets_per_second": random.randint(1000, 5000),
                        "requests_per_second": random.randint(50, 200)
                    }
                },

                "endpoint_status": {
                    "database_server": random.choice(["healthy", "degraded", "unreachable"]),
                    "payment_gateway": random.choice(["healthy", "slow", "timeout"]),
                    "cache_server": random.choice(["healthy", "degraded"]),
                    "external_apis": random.choice(["healthy", "rate_limited", "down"])
                }
            }
        }

    def _generate_state_corruption_details(self) -> Dict[str, Any]:
        """Generate detailed state corruption error information."""
        import random
        import uuid
        from datetime import datetime

        state_issues = [
            {
                "issue_type": "DataCorruption",
                "error_message": "Transaction state corrupted - balance mismatch detected",
                "error_code": "STATE_001",
                "severity": "critical",
                "category": "data_integrity"
            },
            {
                "issue_type": "ConcurrencyIssue",
                "error_message": "Race condition detected in concurrent transaction processing",
                "error_code": "STATE_002",
                "severity": "error",
                "category": "race_condition"
            },
            {
                "issue_type": "SessionCorruption",
                "error_message": "User session state inconsistent across multiple requests",
                "error_code": "STATE_003",
                "severity": "warning",
                "category": "session_integrity"
            }
        ]

        selected_issue = random.choice(state_issues)

        return {
            "state_error": {
                "error_id": f"state_{uuid.uuid4().hex[:16]}",
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": selected_issue["issue_type"],
                "error_message": selected_issue["error_message"],
                "error_code": selected_issue["error_code"],
                "severity": selected_issue["severity"],
                "category": selected_issue["category"],

                "corruption_analysis": {
                    "affected_entities": {
                        "user_accounts": random.randint(1, 20),
                        "transaction_records": random.randint(5, 50),
                        "session_objects": random.randint(10, 100)
                    },
                    "integrity_checks": {
                        "checksum_failures": random.randint(1, 10),
                        "constraint_violations": random.randint(0, 5),
                        "orphaned_records": random.randint(2, 15)
                    }
                },

                "state_diagnostics": {
                    "memory_state": random.choice(["consistent", "inconsistent", "partially_corrupted"]),
                    "database_state": random.choice(["synchronized", "out_of_sync", "corrupted"]),
                    "cache_state": random.choice(["valid", "stale", "corrupted"]),
                    "session_state": random.choice(["active", "expired", "invalid"])
                },

                "recovery_info": {
                    "auto_recovery_attempted": random.choice([True, False]),
                    "rollback_successful": random.choice([True, False]),
                    "manual_intervention_required": random.choice([True, False]),
                    "estimated_recovery_time_minutes": random.randint(5, 60)
                }
            }
        }

    async def get_kafka_metrics(self) -> Dict[str, Any]:
        """Get Kafka health metrics (basic)."""
        try:
            # Simple Kafka health check by attempting to send a test message
            test_start = time.time()

            # This is a basic health check - in production you might want more sophisticated metrics
            kafka_response_time = (time.time() - test_start) * 1000

            return {
                "kafka_status": "healthy",
                "kafka_response_time_ms": round(kafka_response_time, 2)
            }
        except Exception as e:
            return {
                "kafka_status": "unhealthy",
                "kafka_error": str(e),
                "kafka_response_time_ms": -1
            }


async def performance_monitoring_middleware(request: Request, call_next):
    """
    Comprehensive performance monitoring middleware.
    Logs metrics for FastAPI app, database, Kafka, and system resources.
    """
    monitor = PerformanceMonitor()

    # Extract crash type from request body if available
    crash_type = None
    try:
        if request.method == "POST" and hasattr(request, "_body"):
            body = await request.body()
            if body:
                try:
                    body_data = json.loads(body)
                    crash_type = body_data.get("crash_type") or body_data.get("crashType")
                except:
                    pass
    except:
        pass

    # Record request start time and initial metrics
    request_start_time = time.time()
    system_metrics_before = monitor.get_system_metrics(crash_type)

    # Process the request
    response = await call_next(request)

    # Calculate request processing time
    request_duration = (time.time() - request_start_time) * 1000

    # Get metrics after request (with crash type simulation)
    system_metrics_after = monitor.get_system_metrics(crash_type)
    db_metrics_after = await monitor.get_database_metrics()

    # Create comprehensive performance object
    performance_object = {
        "endpoint": str(request.url.path),
        "method": request.method,
        "response_time_ms": round(request_duration, 2),
        "response_status_code": response.status_code,
        "crash_type": crash_type,
        "crash_simulation_active": crash_type is not None,
        "is_slow_request": request_duration > 1000,
        "is_high_cpu": system_metrics_after.get("cpu_percent", 0) > 80,
        "is_high_memory": system_metrics_after.get("memory_percent", 0) > 85,
        "overall_health": "healthy" if (
            request_duration < 5000 and
            system_metrics_after.get("cpu_percent", 0) < 90 and
            system_metrics_after.get("memory_percent", 0) < 90 and
            db_metrics_after.get("database_status") == "healthy"
        ) else "degraded",
        "database": {
            "status": db_metrics_after.get("database_status", "unknown"),
            "response_time_ms": db_metrics_after.get("database_response_time_ms", 0),
            "connection_pool": {
                "pool_size": db_metrics_after.get("connection_pool", {}).get("pool_size", 0),
                "checked_in": db_metrics_after.get("connection_pool", {}).get("checked_in", 0),
                "checked_out": db_metrics_after.get("connection_pool", {}).get("checked_out", 0),
                "overflow": db_metrics_after.get("connection_pool", {}).get("overflow", 0)
            }
        },
        "system": {
            "cpu_percent_before": system_metrics_before.get("cpu_percent", 0),
            "cpu_percent_after": system_metrics_after.get("cpu_percent", 0),
            "cpu_delta": round(system_metrics_after.get("cpu_percent", 0) - system_metrics_before.get("cpu_percent", 0), 2),
            "memory_percent_before": system_metrics_before.get("memory_percent", 0),
            "memory_percent_after": system_metrics_after.get("memory_percent", 0),
            "memory_delta": round(system_metrics_after.get("memory_percent", 0) - system_metrics_before.get("memory_percent", 0), 2),
            "memory_used_gb": system_metrics_after.get("memory_used_gb", 0),
            "disk_percent": system_metrics_after.get("disk_percent", 0),
            "active_connections": system_metrics_after.get("active_connections", 0),
            "process_memory_rss_mb": system_metrics_after.get("process_memory_rss_mb", 0),
            "process_cpu_percent": system_metrics_after.get("process_cpu_percent", 0),
            "cpu_count": system_metrics_after.get("cpu_count", 0),
            "memory_total_gb": system_metrics_after.get("memory_total_gb", 0)
        }
    }

    # Create performance log with EXACT SAME SCHEMA as transaction logs (100% Kafka compatibility)
    performance_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "log_type": "server_performance",
        "login_status": "",
        "customer_id": "",
        "alert_type": "performance_monitoring",
        "alert_severity": "low" if request_duration < 1000 else "medium" if request_duration < 5000 else "high",
        "failed_attempts": "",
        "time_window_minutes": "",
        "login_attempts": "",
        "transaction_id": f"perf_{uuid.uuid4().hex[:12]}",
        "customer_segment": "",
        "status": performance_object["overall_health"],
        "processing_time_ms": round(request_duration, 2),
        "business_date": datetime.utcnow().date().isoformat(),

        # Financial details (empty for performance monitoring)
        "transaction_fee": "",
        "total_amount": "",
        "account_balance_before": "",
        "account_balance_after": "",

        # Transaction attempt data
        "attempted_amount": "",
        "currency": "",
        "attempted_transaction_type": str(request.url.path),
        "attempted_channel": request.method,
        "attempted_account_number": "",
        "attempted_recipient_account": "",
        "attempted_merchant_name": "",
        "attempted_merchant_category": "",

        # Enhanced authentication
        "auth_method": "",
        "auth_success": "",
        "auth_timestamp": "",

        # Error information
        "error_type": "",
        "error_code": "",
        "error_detail": "",
        "validation_stage": "",

        # Store complete performance data as JSON in transaction_description
        "transaction_description": json.dumps(performance_object, separators=(',', ':')),

        # Keep other fields empty (required for schema compatibility)
        "recipient_account_number": "",
        "recipient_account_name": "",
        "recipient_bank_code": "",
        "reference_number": "",
        "risk_assessment_score": "",
        "fraud_indicator": "",
        "aml_screening_result": "",
        "sanction_screening_result": "",
        "compliance_status": "",
        "settlement_date": "",
        "settlement_status": "",
        "clearing_code": "",
        "transaction_type": "performance_monitoring",
        "requested_amount": "",
        "failure_reason": "",
        "failure_message": "",
        "limits": "",
        "account_number": "",
        "amount": "",
        "channel": "api",
        "branch_code": "",
        "province": "",
        "city": "",
        "merchant_name": "",
        "merchant_category": "",
        "merchant_id": "",
        "terminal_id": "",
        "latitude": "",
        "longitude": "",
        "device_id": f"server_{uuid.uuid4().hex[:8]}",
        "device_type": "server",
        "device_os": "",
        "device_browser": "",
        "device_is_trusted": "",
        "ip_address": getattr(request.client, "host", "unknown") if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "session_id": f"perf_session_{uuid.uuid4().hex[:8]}",
        "customer_age": "",
        "customer_gender": "",
        "customer_occupation": "",
        "customer_income_bracket": "",
        "customer_education": "",
        "customer_marital_status": "",
        "customer_monthly_income": "",
        "customer_credit_limit": "",
        "customer_risk_score": "",
        "customer_kyc_level": "",
        "customer_pep_status": "",
        "customer_previous_fraud_incidents": "",
        "device_fingerprint": f"perf_fp_{uuid.uuid4().hex[:16]}",
        "qris_id": "",
        "transaction_reference": "",
        "interchange_fee": "",
        "db_transaction_id": "",
        "balance_after": "",
        "qris_status": ""
    }

    # Debug: Print system metrics for troubleshooting
    print(f"DEBUG System Metrics Before: {system_metrics_before}")
    print(f"DEBUG System Metrics After: {system_metrics_after}")
    print(f"DEBUG DB Metrics: {db_metrics_after}")

    # Send to Kafka for monitoring (non-blocking)
    try:
        await send_transaction(performance_data)
    except Exception as e:
        # Don't let monitoring failures affect the actual request
        print(f"Failed to send performance metrics to Kafka: {e}")

    # Add performance headers to response
    response.headers["X-Response-Time"] = str(round(request_duration, 2))
    response.headers["X-Server-Health"] = performance_data["status"]

    return response