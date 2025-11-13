import random
import requests
from datetime import datetime, timezone
from decouple import config
# from app import mqtt_client
from app import elk_mqtt
from app.schemas import StandardKafkaEvent
from ..utils.pod_namespace import k8s


class InfraServices:
    @staticmethod
    def infra_service_cpu(request, current_user):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="infra_service",
                                       error_type="cpu_spike",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}

    @staticmethod
    def infra_service_driver(request, current_user):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="infra_service",
                                       error_type="server_crash",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}


    @staticmethod
    def data_security(request, current_user):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="data_security",
                                       error_type="WAF_BLOCK SQLi",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}


    @staticmethod
    def data_security_ddos(request, current_user):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="data_security",
                                       error_type="WAF_RATE_LIMIT DDoS Mitigation",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}


    @staticmethod
    def data_security_brute_force(request, current_user):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="data_security",
                                       error_type="WAF_RATE_LIMIT Brute Force",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}


    @staticmethod
    def sample_disk_space(request):
        try:
            base_url = config("EXT_API_K8S")
            node_name = "mh-smbcserver"
            disk_usage_url = f"{base_url}/k8s/nodes/{node_name}/disk-usage"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {config('EXT_API_TOKEN')}"
            }

            # Get disk usage from external API
            resp = requests.get(disk_usage_url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # Filter filesystem with mounted_on = "/"
            filesystems = data.get("filesystems", [])
            root_filesystem = next((fs for fs in filesystems if fs.get("mounted_on") == "/"), None)

            if not root_filesystem:
                return {"status": "error", "message": "Root filesystem (/) not found"}

            # Extract disk usage information
            disk_size = root_filesystem.get("size", "N/A")
            disk_used = root_filesystem.get("used", "N/A")
            disk_available = root_filesystem.get("available", "N/A")
            disk_use_percent = root_filesystem.get("use_percent", "N/A")

            event = StandardKafkaEvent(
                timestamp=datetime.now(timezone.utc),
                log_type="disk_space",
                alert_type=f"Disk usage above threshold",
                alert_severity="low",
                error_detail=(
                    f"happened at node: {node_name}, "
                    f"size: {disk_size}, "
                    f"used: {disk_used}, "
                    f"available: {disk_available}, "
                    f"usage: {disk_use_percent}"
                ),
                customer_id="",
                device_type="server",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

            return {
                "status": "success",
                "message": "Event disk_space published",
                "disk_info": root_filesystem
            }

        except requests.RequestException as e:
            return {"status": "error", "message": f"External API request failed: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}


    @staticmethod
    def sample_auto_restart(request):
        try:
            base_url = config("EXT_API_K8S")
            tx_url = config("EXT_API_TX")
            namespace = "ai-ops"
            pods_url = f"{base_url}/k8s/pods"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {config('EXT_API_TOKEN')}"
            }
            params = {"namespace": namespace}

            resp = requests.get(pods_url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            pods = data.get("pods", [])
            filtered_pods = [p for p in pods if "transaction-service" in p["name"]]

            if not filtered_pods:
                return {"status": "error", "message": "No matching pods found for 'transaction-service'"}

            sample_k8s = random.choice(filtered_pods)

            event = StandardKafkaEvent(
                timestamp=datetime.now(timezone.utc),
                log_type="auto_restart",
                alert_type="Health check failed 3x",
                alert_severity="medium",
                error_detail=(
                    f"namespace: {sample_k8s['namespace']}, "
                    f"pod: {sample_k8s['name']}, "
                    "OutOfMemoryError - limit memory on this pod 512mb"
                ),
                customer_id="",
                device_type="server",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

            tx_base = config("EXT_API_TX")

            create_tx_url = f"{tx_base}/api/transactions"
            create_tx_payload = {
                "userId": "user123",
                "amount": 100.50,
                "type": "credit",
                "description": "Payment received"
            }

            tx_response = requests.post(
                create_tx_url,
                headers={"Content-Type": "application/json"},
                json=create_tx_payload,
                timeout=10
            )
            tx_response.raise_for_status()

            mem_leak_url = f"{tx_url}/health/toggle"
            mem_leak_params = {"mode": "fast"}
            leak_response = requests.post(mem_leak_url, params=mem_leak_params, timeout=15)
            leak_response.raise_for_status()

            return {
                "status": "success",
                "message": "Event published, transaction created, and memory leak triggered",
                "selected_pod": sample_k8s,
                "transaction_response": tx_response.json(),
                "memory_leak_response": leak_response.json(),
            }

        except requests.RequestException as e:
            return {"status": "error", "message": f"External API request failed: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}


    @staticmethod
    def sample_auto_rollback(request):
        try:
            base_url = config("EXT_API_K8S")
            namespace = "ai-ops"
            pods_url = f"{base_url}/k8s/pods"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {config('EXT_API_TOKEN')}"
            }
            params = {"namespace": namespace}

            resp = requests.get(pods_url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            pods = data.get("pods", [])
            filtered_pods = [p for p in pods if "transaction-service" in p["name"]]

            if not filtered_pods:
                return {"status": "error", "message": "No matching pods found for 'transaction-service'"}

            sample_k8s = random.choice(filtered_pods)

            event = StandardKafkaEvent(
                timestamp=datetime.now(timezone.utc),
                log_type="auto_rollback",
                alert_type="critical bug",
                alert_severity="high",
                error_detail=(
                    f"namespace: {sample_k8s['namespace']}, "
                    f"pod: {sample_k8s['name']}, "
                    "service_cannot_startup"
                ),
                customer_id="",
                device_type="server",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )

            # mqtt_client.publish("infra-banking", event.json(), qos=1)
            elk_mqtt.publish_to_elk("infra-banking", event.json())

            deployment = "transaction-service"
            rollback_url = f"{base_url}/k8s/deployments/{deployment}/rollback"

            response = requests.post(
                rollback_url,
                headers=headers,
                params={"namespace": namespace},
                data="",
                timeout=15
            )
            response.raise_for_status()

            return {
                "status": "success",
                "message": "Event published and rollback triggered successfully",
                "external_api_response": response.json(),
                "selected_pod": sample_k8s
            }

        except requests.RequestException as e:
            return {"status": "error", "message": f"External API request failed: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}
