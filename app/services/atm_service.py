from datetime import datetime, timezone

from app import mqtt_client
from app.schemas import StandardKafkaEvent


class ATMServices:
    @staticmethod
    def atm_service(request, current_user):
        try:
            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="atm_insufficient",
                                       error_type="insufficient_machine",
                                       customer_id=current_user.customer_id,
                                       device_type="atm_machine",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"))

            mqtt_client.publish("infra-banking", event.json(), qos=1)

        except Exception as e:
            return {"status": "error", "message": f"{str(e)}"}

