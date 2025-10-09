import random
import requests
from datetime import datetime, timezone
from decouple import config
from app import mqtt_client
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

            mqtt_client.publish("infra-banking", event.json(), qos=1)

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

            mqtt_client.publish("infra-banking", event.json(), qos=1)

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

            mqtt_client.publish("infra-banking", event.json(), qos=1)

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

            mqtt_client.publish("infra-banking", event.json(), qos=1)

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

            mqtt_client.publish("infra-banking", event.json(), qos=1)

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}


    @staticmethod
    def sample_disk_space(request):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="disk_space",
                                       alert_type=f"Disk usage {random.randint(76, 97)}%",
                                       alert_severity="low",
                                       error_detail="mh-smbcserver",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            mqtt_client.publish("infra-banking", event.json(), qos=1)

            return {"status": "success", "message": "Event disk_space published"}

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}


    @staticmethod
    def sample_auto_restart(request):
        sample_k8s = random.choice(k8s)

        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="auto_restart",
                                       alert_type="Health check failed 3x",
                                       alert_severity="medium",
                                       error_detail=f"namespace: {sample_k8s['namespace']},"
                                                    f" pod: {sample_k8s['name']},"
                                                    " OutOfMemoryError"
                                                    " limit memory on this pod 200mb",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            mqtt_client.publish("infra-banking", event.json(), qos=1)

            base_url = config("EXT_API_TX")

            create_tx_url = f"{base_url}/api/transactions"
            create_tx_payload = {
                "userId": "user123",
                "amount": 100.50,
                "type": "credit",
                "description": "Payment received"
            }

            tx_response = requests.post(create_tx_url,
                                        headers={"Content-Type": "application/json"},
                                        json=create_tx_payload,
                                        timeout=10)
            tx_response.raise_for_status()

            mem_leak_url = f"{base_url}/api/oom/memory-leak"
            mem_leak_params = {"iterations": 10}

            leak_response = requests.post(mem_leak_url,
                                          params=mem_leak_params,
                                          timeout=10)
            leak_response.raise_for_status()

            return {
                "status": "success",
                "message": "Event published, transaction created, and memory leak triggered",
                "transaction_response": tx_response.json(),
                "memory_leak_response": leak_response.json(),
            }

        except requests.RequestException as e:
            return {"status": "error", "message": f"External API request failed: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}


    @staticmethod
    def sample_auto_rollback(request):
        sample_k8s = random.choice(k8s)

        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="auto_rollback",
                                       alert_type="critical bug",
                                       alert_severity="high",
                                       error_detail=f"namespace: {sample_k8s['namespace']},"
                                                    f" pod: {sample_k8s['name']},"
                                                    " 100%_transaction_fail,"
                                                    " error rate spikes from 2% to 45%",
                                       customer_id="",
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            mqtt_client.publish("infra-banking", event.json(), qos=1)
            deployment = "transaction-service"
            namespace = "ai-ops"

            url = f"{config("EXT_API_K8S")}/k8s/deployments/{deployment}/rollback"
            params = {"namespace": namespace}

            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {config('EXT_API_TOKEN')}"
            }

            response = requests.post(url, headers=headers, params=params, data="", timeout=15)
            response.raise_for_status()

            return {
                "status": "success",
                "message": "Event published and rollback triggered successfully",
                "external_api_response": response.json(),
            }

        except requests.RequestException as e:
            return {"status": "error", "message": f"External API request failed: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}