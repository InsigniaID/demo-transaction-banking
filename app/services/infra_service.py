from datetime import datetime, timezone

from app import mqtt_client
from app.schemas import StandardKafkaEvent


class InfraServices:
    @staticmethod
    def infra_service(request, current_user):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="premises_error",
                                       error_type="premises_error",
                                       customer_id=current_user.customer_id,
                                       device_type="server",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            mqtt_client.publish("infra-banking", event.json(), qos=1)

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}

