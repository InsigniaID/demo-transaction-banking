import uuid
import random
from datetime import datetime
from typing import Dict, Any, Optional

from ..kafka_producer import send_transaction


class EnhancedTransactionService:
    @staticmethod
    def calculate_transaction_fee(amount: float, transaction_type: str, channel: str) -> float:
        """Calculate transaction fee based on amount, type and channel."""
        base_fees = {
            "transfer": {"mobile_app": 2500, "web": 3000, "atm": 5000},
            "withdrawal": {"mobile_app": 0, "web": 0, "atm": 10000},
            "pos_purchase": {"mobile_app": 0, "web": 0, "atm": 0},
            "bill_payment": {"mobile_app": 2000, "web": 2500, "atm": 3000},
            "salary_credit": {"mobile_app": 0, "web": 0, "atm": 0}
        }
        
        base_fee = base_fees.get(transaction_type, {}).get(channel, 2500)
        
        # Additional fee for large amounts
        if amount > 10000000:  # > 10M
            base_fee += amount * 0.001  # 0.1%
        elif amount > 1000000:  # > 1M
            base_fee += amount * 0.0005  # 0.05%
            
        return round(base_fee, 0)

    @staticmethod
    def generate_account_balances(customer_id: str, amount: float) -> Dict[str, float]:
        """Generate realistic account balances before/after transaction."""
        # Simulate different balance ranges based on customer ID
        customer_hash = hash(customer_id) % 10
        
        base_balance_ranges = [
            (500000, 2000000),     # Low balance customers
            (2000000, 10000000),   # Medium balance customers  
            (10000000, 50000000),  # High balance customers
        ]
        
        range_idx = customer_hash % len(base_balance_ranges)
        min_bal, max_bal = base_balance_ranges[range_idx]
        
        # Ensure sufficient balance for transaction
        before_balance = random.uniform(max(min_bal, amount * 1.5), max_bal)
        after_balance = before_balance - amount
        
        return {
            "account_balance_before": round(before_balance, 2),
            "account_balance_after": round(after_balance, 2)
        }

    @staticmethod
    def generate_enhanced_device_data(request_headers: dict, client_host: str) -> Dict[str, Any]:
        """Generate enhanced device fingerprinting data."""
        return {
            "device_id": request_headers.get("X-Device-ID", f"dev_unknown_{uuid.uuid4().hex[:8]}"),
            "device_type": request_headers.get("X-Device-Type", "mobile"),
            "device_os": request_headers.get("X-Device-OS", "Unknown"),
            "device_browser": request_headers.get("X-Device-Browser", "Unknown"),
            "device_is_trusted": request_headers.get("X-Device-Trusted", "false") == "true",
            "device_fingerprint": f"fp_{uuid.uuid4().hex[:16]}",
            "device_screen_resolution": request_headers.get("X-Screen-Resolution", "1920x1080"),
            "device_timezone": request_headers.get("X-Timezone", "Asia/Jakarta"),
            "device_language": request_headers.get("X-Language", "id-ID"),
            "ip_address": client_host,
            "user_agent": request_headers.get("user-agent", "Unknown"),
            "session_id": request_headers.get("X-Session-ID", f"sess_{uuid.uuid4().hex[:8]}"),
        }

    @staticmethod
    async def create_enhanced_retail_transaction_data(
        qris_data: dict,
        customer_id: str,
        account_number: str,
        request_data: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Create enhanced retail transaction data for QRIS consumption."""
        now = datetime.utcnow()
        amount = qris_data["amount"]
        
        # Calculate fees and balances
        fee = EnhancedTransactionService.calculate_transaction_fee(amount, "pos_purchase", "mobile_app")
        balances = EnhancedTransactionService.generate_account_balances(customer_id, amount + fee)
        
        return {
            "timestamp": now.isoformat(),
            "log_type": "transaction",
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "customer_id": customer_id,
            "account_number": account_number,
            "customer_segment": "retail",
            "transaction_type": "pos_purchase",
            "amount": amount,
            "currency": qris_data["currency"],
            "transaction_fee": fee,
            "total_amount": amount + fee,
            "channel": "mobile_app",
            "status": "success",
            "branch_code": "BR-0001",
            "province": "DKI Jakarta",
            "city": "Jakarta Selatan",
            "latitude": -6.261493,
            "longitude": 106.810600,
            "processing_time_ms": random.randint(800, 2500),
            "business_date": now.date().isoformat(),
            
            # Account balances
            **balances,
            
            # Customer demographics (more realistic)
            "customer_age": random.randint(18, 65),
            "customer_gender": random.choice(["M", "F"]),
            "customer_occupation": random.choice(["karyawan", "wiraswasta", "pns", "pensiunan", "mahasiswa"]),
            "customer_income_bracket": random.choice(["<3jt", "3-5jt", "5-10jt", "10-25jt", ">25jt"]),
            "customer_education": random.choice(["SMA", "D3", "S1", "S2", "S3"]),
            "customer_marital_status": random.choice(["single", "married", "divorced"]),
            "customer_monthly_income": random.uniform(3000000, 25000000),
            "customer_credit_limit": random.uniform(10000000, 100000000),
            "customer_risk_score": round(random.uniform(0.1, 0.8), 3),
            "customer_kyc_level": random.choice(["basic", "enhanced", "premium"]),
            "customer_pep_status": random.choice([True, False]),
            "customer_previous_fraud_incidents": random.randint(0, 2),
            
            # Enhanced device data
            "device_id": f"dev_mobile_{uuid.uuid4().hex[:10]}",
            "device_type": "mobile",
            "device_os": random.choice(["Android 14", "Android 13", "iOS 17", "iOS 16"]),
            "device_browser": random.choice(["Chrome 120", "Safari 17", "Firefox 121"]),
            "device_is_trusted": random.choice([True, False]),
            "device_fingerprint": f"fp_{uuid.uuid4().hex[:16]}",
            "ip_address": f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
            "user_agent": "Mozilla/5.0 (Mobile; Banking App)",
            "session_id": f"sess_{uuid.uuid4().hex[:8]}",
            
            # Authentication method
            "auth_method": "pin",
            "auth_success": True,
            
            # Merchant data
            "merchant_name": qris_data["merchant_name"],
            "merchant_category": qris_data["merchant_category"],
            "merchant_id": f"MID{random.randint(10000000, 99999999)}",
            "terminal_id": f"TID{random.randint(100000, 999999)}",
            "qris_id": qris_data.get("qris_id"),
            
            # Transaction metadata
            "transaction_reference": f"REF{now.strftime('%Y%m%d')}{random.randint(100000, 999999)}",
            "interchange_fee": round(amount * 0.007, 2),  # 0.7% typical interchange
            "settlement_date": (now.date()).isoformat(),
        }

    @staticmethod
    async def create_enhanced_corporate_transaction_data(
        transaction_data: dict,
        customer_id: str,
        request_headers: dict,
        client_host: str
    ) -> Dict[str, Any]:
        """Create enhanced corporate transaction data."""
        now = datetime.utcnow()
        amount = transaction_data["amount"]
        tx_type = transaction_data["transaction_type"]
        channel = transaction_data["channel"]
        
        # Calculate fees and balances
        fee = EnhancedTransactionService.calculate_transaction_fee(amount, tx_type, channel)
        balances = EnhancedTransactionService.generate_account_balances(customer_id, amount + fee)
        device_data = EnhancedTransactionService.generate_enhanced_device_data(request_headers, client_host)
        timestamp_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")

        enhanced_data = {
            "timestamp": timestamp_str,
            "log_type": "transaction",
            "login_status": "",
            "customer_id": customer_id,
            "alert_type": "",
            "alert_severity": "",
            "failed_attempts": "",
            "time_window_minutes": "",
            "login_attempts": "",
            "transaction_id": f"corp_{uuid.uuid4().hex[:12]}",
            "customer_segment": "corporate",
            "status": "success",
            "processing_time_ms": random.randint(500, 3000),
            "business_date": now.date().isoformat(),
            
            # Financial details
            "transaction_fee": fee,
            "total_amount": amount + fee,
            **balances,

            # ==MATCH FORMAT TRANSACTION FROM FAILED==
            "attempted_amount": transaction_data.get("amount"),
            "currency": "",
            "attempted_transaction_type": transaction_data.get("transaction_type"),
            "attempted_channel": transaction_data.get("channel"),
            "attempted_account_number": transaction_data.get("account_number"),
            "attempted_recipient_account": transaction_data.get("recipient_account_number"),
            "attempted_merchant_name": transaction_data.get("merchant_name"),
            "attempted_merchant_category": transaction_data.get("merchant_category"),
            
            # Enhanced authentication
            "auth_method": "pin",
            "auth_success": True,
            "auth_timestamp": now.isoformat(),

            # ==MATCH FORMAT TRANSACTION FROM FAILED==
            "error_type": "",
            "error_code": "",
            "error_detail": "",
            "validation_stage": "",

            # Enhanced transaction metadata
            "transaction_description": transaction_data.get("transaction_description", "Corporate transaction"),
            
            # Recipient information for transfers
            "recipient_account_number": transaction_data.get("recipient_account_number"),
            "recipient_account_name": transaction_data.get("recipient_account_name"),
            "recipient_bank_code": transaction_data.get("recipient_bank_code"),
            "reference_number": "",
            
            # Compliance & risk
            "risk_assessment_score": round(random.uniform(0.1, 0.3), 3),
            "fraud_indicator": "false",
            "aml_screening_result": "pass",
            "sanction_screening_result": "pass",
            "compliance_status": "approved",
            
            # Settlement information
            "settlement_date": now.date().isoformat(),
            "settlement_status": "pending",
            "clearing_code": f"CLR{random.randint(100000, 999999)}",
            "transaction_type": "",
            "requested_amount": "",
            "failure_reason": "",
            "failure_message": "",
            "limits": "",
            "account_number": transaction_data.get("account_number"),
            "amount": "",
            "channel": "",
            "branch_code": "",
            "province": "",
            "city": "",
            "merchant_name": "",
            "merchant_category": "",
            "merchant_id": "",
            "terminal_id": "",
            "latitude": "",
            "longitude": "",
            "device_id": "",
            "device_type": "",
            "device_os": "",
            "device_browser": "",
            "device_is_trusted": "",
            "ip_address": "",
            "user_agent": "",
            "session_id": "",
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
            "device_fingerprint": "",
            "qris_id": "",
            "transaction_reference": "",
            "interchange_fee": "",
            "db_transaction_id": "",
            "balance_after": "",
            "qris_status": ""
        }
        
        # Merge with original transaction data (excluding 'pin' for security)
        transaction_copy = transaction_data.copy()
        transaction_copy.pop('pin', None)  # Remove PIN from logs
        
        enhanced_data.update(transaction_copy)
        return enhanced_data

    @staticmethod
    async def create_error_transaction_data(
            error_type: str,
            error_code: int,
            error_detail: Any,
            transaction_input: dict,
            customer_id: str,
            request_headers: dict,
            client_host: str,
            validation_stage: str = None
    ) -> Dict[str, Any]:
        """Create error transaction data for Kafka logging."""
        now = datetime.utcnow()
        device_data = EnhancedTransactionService.generate_enhanced_device_data(request_headers, client_host)

        # Remove sensitive data
        safe_transaction_input = transaction_input.copy()
        safe_transaction_input.pop('pin', None)
        timestamp_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")

        error_data = {
            "timestamp": timestamp_str,
            "log_type": "transaction_error",
            "login_status": "",
            "customer_id": customer_id,
            "alert_type": "",
            "alert_severity": "",
            "failed_attempts": "",
            "time_window_minutes": "",
            "login_attempts": "",
            "transaction_id": f"err_{uuid.uuid4().hex[:12]}",
            "customer_segment": "corporate",
            "status": "failed",
            "processing_time_ms": random.randint(100, 1000),
            "business_date": now.date().isoformat(),

            # ==MATCH FORMAT TRANSACTION FROM SUCCESS==
            "transaction_fee": 0,
            "total_amount": 1000000.0,
            "account_balance_before": 33500132.73,
            "account_balance_after": 32500132.73,

            # Original transaction attempt data
            "attempted_amount": transaction_input.get("amount"),
            "currency": "",
            "attempted_transaction_type": transaction_input.get("transaction_type"),
            "attempted_channel": transaction_input.get("channel"),
            "attempted_account_number": transaction_input.get("account_number"),
            "attempted_recipient_account": transaction_input.get("recipient_account_number"),
            "attempted_merchant_name": transaction_input.get("merchant_name"),
            "attempted_merchant_category": transaction_input.get("merchant_category"),

            # ==MATCH FORMAT TRANSACTION FROM SUCCESS==
            "auth_method": "pin",
            "auth_success": True,
            "auth_timestamp": now.isoformat(),

            # Error details
            "error_type": error_type,
            "error_code": error_code,
            "error_detail": error_detail,
            "validation_stage": validation_stage,
            # "account_validation", "transaction_validation", "pin_validation", etc.

            # ==MATCH FORMAT TRANSACTION FROM SUCCESS==
            "transaction_description": transaction_input.get("transaction_description"),

            # ==MATCH FORMAT TRANSACTION FROM SUCCESS==
            "recipient_account_number": transaction_input.get("recipient_account_number"),
            "recipient_account_name": transaction_input.get("recipient_account_name"),
            "recipient_bank_code": transaction_input.get("recipient_bank_code"),
            "reference_number": transaction_input.get("reference_number"),

            # Risk and compliance
            "risk_assessment_score": round(random.uniform(0.6, 0.9), 3),  # Higher risk for failed transactions
            "fraud_indicator": error_type in ["pin_validation_failed", "suspicious_activity"],
            "aml_screening_result": "pass",
            "sanction_screening_result": "pass",
            "compliance_status": random.choice(["rejected", "denied", "non-compliant"]),

            # ==MATCH FORMAT TRANSACTION FROM SUCCESS==
            "settlement_date": "",
            "settlement_status": "failed",
            "clearing_code": "",
            "transaction_type": "",
            "requested_amount": "",
            "failure_reason": "",
            "failure_message": "",
            "limits": "",
            "account_number": "",
            "amount": "",
            "channel": "",
            "branch_code": "",
            "province": "",
            "city": "",
            "merchant_name": "",
            "merchant_category": "",
            "merchant_id": "",
            "terminal_id": "",
            "latitude": "",
            "longitude": "",
            "device_id": "",
            "device_type": "",
            "device_os": "",
            "device_browser": "",
            "device_is_trusted": "",
            "ip_address": "",
            "user_agent": "",
            "session_id": "",
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
            "device_fingerprint": "",
            "qris_id": "",
            "transaction_reference": "",
            "interchange_fee": "",
            "db_transaction_id": "",
            "balance_after": "",
            "qris_status": ""
        }

        return error_data

    @staticmethod
    async def send_error_to_kafka(error_data: Dict[str, Any]) -> None:
        print("KAFKA ERROR\n", error_data)
        """Send error transaction data to Kafka."""
        await send_transaction(error_data)

    @staticmethod
    async def send_transaction_to_kafka(transaction_data: Dict[str, Any]) -> None:
        print("KAFKA SUCCESS \n", transaction_data)
        """Send enhanced transaction data to Kafka."""
        await send_transaction(transaction_data)