from datetime import datetime, timezone

from app import mqtt_client
from app.schemas import StandardKafkaEvent


class ATMState:
    TOTAL_BALANCE = 100_000_000
    balance = TOTAL_BALANCE

    @classmethod
    def withdraw(cls, amount: int):
        if amount > cls.balance:
            return False
        cls.balance -= amount
        return True

    @classmethod
    def get_balance(cls):
        return cls.balance

    @classmethod
    def is_low_balance(cls):
        return cls.balance <= (0.3 * cls.TOTAL_BALANCE)


class ATMServices:
    @staticmethod
    def atm_service(request, current_user, amount: int):
        try:
            success = ATMState.withdraw(amount)

            if not success:
                event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                           log_type="atm_insufficient",
                                           error_type="insufficient_machine",
                                           customer_id=current_user.customer_id,
                                           device_type="atm_machine",
                                           ip_address=request.client.host,
                                           user_agent=request.headers.get("user-agent"),
                                           requested_amount=amount,
                                           failure_reason="ATM balance insufficient",
                                           account_balance_before=ATMState.get_balance(),
                                           account_balance_after=ATMState.get_balance())

                mqtt_client.publish("infra-banking", event.json(), qos=1)

                return {"status": "error", "message": "Saldo ATM tidak cukup"}

            balance_before = ATMState.get_balance() + amount
            balance_after = ATMState.get_balance()

            event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                       log_type="atm_withdrawal",
                                       customer_id=current_user.customer_id,
                                       device_type="atm_machine",
                                       ip_address=request.client.host,
                                       user_agent=request.headers.get("user-agent"),
                                       requested_amount=amount,
                                       account_balance_before=balance_before,
                                       account_balance_after=balance_after,
                                       transaction_type="cash_withdrawal",
                                       status="success")

            mqtt_client.publish("infra-banking", event.json(), qos=1)

            if ATMState.is_low_balance():
                notif = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                           log_type="atm_low_balance",
                                           alert_type="low_balance",
                                           alert_severity="warning",
                                           device_type="atm_machine",
                                           ip_address=request.client.host,
                                           user_agent=request.headers.get("user-agent"),
                                           account_balance_after=ATMState.get_balance(),
                                           total_amount=ATMState.TOTAL_BALANCE,
                                           failure_message="ATM balance below 30%")

                mqtt_client.publish("infra-banking", notif.json(), qos=1)

            return {
                "status": "success",
                "message": f"withdraw {amount} successfully"
            }

        except Exception as e:
            err_event = StandardKafkaEvent(timestamp=datetime.now(timezone.utc),
                                           log_type="atm_error",
                                           error_type="exception",
                                           error_detail=str(e),
                                           device_type="atm_machine",
                                           ip_address=request.client.host,
                                           user_agent=request.headers.get("user-agent"))

            mqtt_client.publish("infra-banking", err_event.json(), qos=1)

            return {"status": "error", "message": str(e)}

