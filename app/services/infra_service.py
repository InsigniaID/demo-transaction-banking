from datetime import datetime, timezone

from app import mqtt_client
from app.schemas import StandardKafkaEvent


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
                                       error_type="driver_error",
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