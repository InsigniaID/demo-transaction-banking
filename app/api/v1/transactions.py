from decimal import Decimal
import random
import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Body, HTTPException
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...auth import get_current_user
from ...kafka_producer import send_transaction
from ...models import User, Account, TransactionHistory
from ...schemas import (
    GenerateQRISRequest, GenerateQRISResponse,
    ConsumeQRISRequest, ConsumeQRISResponse,
    TransactionCorporateInput, FraudDataLegitimate, DetectionResult, StandardKafkaEvent
)
from ...services import transaction_recording_service
from ...services.foundry_service import FoundryAnalytics
from ...services.qris_service import QRISService
from ...services.transaction_recording_service import TransactionRecordingService
from ...services.transaction_service import TransactionService
from ...services.enhanced_transaction_service import EnhancedTransactionService
from ...services.pin_validation_service import pin_validation_service
from ...services.transaction_validation_service import transaction_validation_service, TransactionValidationService


router = APIRouter()


def _get_crash_error_detail(crash_type: str) -> str:
    """Get detailed error message with traceback for specific crash types."""
    crash_details = {
        "runtime": [
            """ZeroDivisionError: division by zero
  File "app/api/v1/transactions.py", line 455, in create_corporate_transaction
    result = amount / 0
  File "app/services/transaction_service.py", line 89, in calculate_fee
    fee_rate = total_amount / zero_divisor
ZeroDivisionError: division by zero""",

            """TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'
  File "app/api/v1/transactions.py", line 467, in create_corporate_transaction
    total = balance + amount
  File "app/services/balance_service.py", line 42, in add_amount
    return current_balance + new_amount
TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'""",

            """AttributeError: 'NoneType' object has no attribute 'amount'
  File "app/api/v1/transactions.py", line 478, in create_corporate_transaction
    fee = transaction.amount * 0.01
  File "app/models.py", line 156, in amount
    return self._amount.value
AttributeError: 'NoneType' object has no attribute 'amount'""",

            """IndexError: list index out of range
  File "app/api/v1/transactions.py", line 491, in create_corporate_transaction
    first_item = transaction_list[0]
  File "app/services/transaction_processor.py", line 234, in get_first_transaction
    return transactions[index]
IndexError: list index out of range""",

            """KeyError: 'transaction_id'
  File "app/api/v1/transactions.py", line 502, in create_corporate_transaction
    tx_id = request_data['transaction_id']
  File "app/utils/request_parser.py", line 67, in extract_transaction_id
    return data[key]
KeyError: 'transaction_id'""",

            """UnboundLocalError: local variable 'result' referenced before assignment
  File "app/api/v1/transactions.py", line 513, in create_corporate_transaction
    return result.value
  File "app/services/calculation_service.py", line 123, in compute_result
    if condition: result = compute()
UnboundLocalError: local variable 'result' referenced before assignment""",

            """FloatingPointError: float division by zero
  File "app/api/v1/transactions.py", line 524, in create_corporate_transaction
    ratio = float('inf') / 0.0
  File "app/utils/math_operations.py", line 45, in calculate_ratio
    return numerator / denominator
FloatingPointError: float division by zero"""
        ],

        "memory": [
            """MemoryError: cannot allocate 8388608000 bytes
  File "app/api/v1/transactions.py", line 456, in create_corporate_transaction
    large_data = [0] * (10**9)
  File "app/services/enhanced_transaction_service.py", line 234, in process_data
    buffer = bytearray(sys.maxsize)
MemoryError: cannot allocate memory""",

            """MemoryError: unable to allocate 4294967296 bytes
  File "app/api/v1/transactions.py", line 489, in create_corporate_transaction
    transaction_log = ' '.join(['X'] * 1000000000)
  File "app/services/logging_service.py", line 67, in create_log_entry
    log_buffer = b'\\x00' * buffer_size
MemoryError: unable to allocate array with shape (4294967296,)""",

            """OverflowError: Python int too large to convert to C long
  File "app/api/v1/transactions.py", line 501, in create_corporate_transaction
    mega_number = 2 ** (2 ** 32)
  File "app/utils/number_utils.py", line 23, in process_large_number
    return int(value) * multiplier
OverflowError: Python int too large to convert to C long""",

            """MemoryError: out of memory
  File "app/api/v1/transactions.py", line 535, in create_corporate_transaction
    huge_dict = {i: f'data_{i}' * 1000000 for i in range(1000000)}
  File "app/services/data_processor.py", line 89, in create_lookup_table
    return {k: v for k, v in massive_dataset}
MemoryError: out of memory""",

            """ResourceWarning: unclosed file descriptor leaked
  File "app/api/v1/transactions.py", line 546, in create_corporate_transaction
    files = [open(f'temp_{i}.log', 'w') for i in range(100000)]
  File "app/utils/file_manager.py", line 156, in create_temp_files
    return [tempfile.NamedTemporaryFile() for _ in range(count)]
ResourceWarning: too many open file descriptors""",

            """SystemError: null argument to internal routine
  File "app/api/v1/transactions.py", line 557, in create_corporate_transaction
    corrupted_memory = ctypes.cast(0, ctypes.py_object).value
  File "app/services/memory_manager.py", line 234, in access_raw_memory
    return ctypes.string_at(address, size)
SystemError: null argument to internal routine"""
        ],

        "infinite-loop": [
            """TimeoutError: operation timed out after 30.0 seconds
  File "app/api/v1/transactions.py", line 457, in create_corporate_transaction
    await transaction_processor.process()
  File "app/services/transaction_service.py", line 156, in process
    while True: counter += 1
TimeoutError: transaction processing exceeded maximum time limit""",

            """asyncio.TimeoutError: Task was cancelled after 45.0 seconds
  File "app/api/v1/transactions.py", line 469, in create_corporate_transaction
    result = await asyncio.wait_for(slow_operation(), timeout=45)
  File "app/services/slow_service.py", line 89, in complex_calculation
    while not converged: iterations += 1
asyncio.TimeoutError: Task was cancelled after 45.0 seconds""",

            """RecursionError: maximum recursion depth exceeded
  File "app/api/v1/transactions.py", line 481, in create_corporate_transaction
    validate_recursive(data, depth=0)
  File "app/validators/recursive_validator.py", line 34, in validate_recursive
    return validate_recursive(item, depth + 1)
RecursionError: maximum recursion depth exceeded in comparison""",

            """KeyboardInterrupt: operation was interrupted
  File "app/api/v1/transactions.py", line 492, in create_corporate_transaction
    result = infinite_calculation()
  File "app/services/math_processor.py", line 67, in infinite_calculation
    while True: compute_prime_numbers()
KeyboardInterrupt: operation was interrupted by user""",

            """RuntimeError: maximum number of iterations exceeded
  File "app/api/v1/transactions.py", line 503, in create_corporate_transaction
    convergence = iterative_solver.solve()
  File "app/algorithms/solver.py", line 145, in solve
    while error > tolerance: iteration += 1
RuntimeError: failed to converge after 1000000 iterations""",

            """concurrent.futures.TimeoutError: task did not complete within 60 seconds
  File "app/api/v1/transactions.py", line 514, in create_corporate_transaction
    future_result = executor.submit(heavy_computation).result(timeout=60)
  File "app/services/parallel_processor.py", line 234, in heavy_computation
    while processing: time.sleep(0.1)
concurrent.futures.TimeoutError: task did not complete within 60 seconds"""
        ],

        "network": [
            """ConnectionError: HTTPSConnectionPool(host='payment-gateway.bank.com', port=443)
  File "app/api/v1/transactions.py", line 458, in create_corporate_transaction
    response = await gateway_client.send_payment()
  File "app/services/payment_gateway.py", line 45, in send_payment
    conn = httpx.post('https://payment-gateway.bank.com/api/payments')
ConnectionError: failed to connect to external payment gateway""",

            """requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.bank-central.id', port=443)
  File "app/api/v1/transactions.py", line 472, in create_corporate_transaction
    validation = await central_bank.validate_transfer()
  File "app/services/central_bank_service.py", line 78, in validate_transfer
    response = requests.get(url, timeout=5)
requests.exceptions.ReadTimeout: Read timed out after 5.0 seconds""",

            """socket.gaierror: [Errno -2] Name or service not known
  File "app/api/v1/transactions.py", line 484, in create_corporate_transaction
    await fraud_check.verify_transaction()
  File "app/services/fraud_detection.py", line 123, in verify_transaction
    sock.connect((hostname, port))
socket.gaierror: [Errno -2] Name or service not known: 'fraud-api.nonexistent.com'""",

            """urllib3.exceptions.MaxRetryError: HTTPSConnectionPool exceeded retry limit
  File "app/api/v1/transactions.py", line 495, in create_corporate_transaction
    response = await external_api.call_with_retry()
  File "app/services/external_api.py", line 156, in call_with_retry
    return requests.get(url, timeout=30)
urllib3.exceptions.MaxRetryError: exceeded maximum retry attempts (5)""",

            """ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
  File "app/api/v1/transactions.py", line 506, in create_corporate_transaction
    secure_response = await ssl_client.secure_call()
  File "app/services/ssl_client.py", line 89, in secure_call
    return httpx.get(url, verify=True)
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed""",

            """aiohttp.ClientConnectorError: Cannot connect to host timeout
  File "app/api/v1/transactions.py", line 517, in create_corporate_transaction
    async_response = await aiohttp_client.get(api_url)
  File "app/services/async_client.py", line 234, in get
    return await session.get(url)
aiohttp.ClientConnectorError: Cannot connect to host api.timeout.com:443""",

            """requests.exceptions.ConnectionError: ('Connection aborted.', RemoteDisconnected)
  File "app/api/v1/transactions.py", line 528, in create_corporate_transaction
    bank_response = requests.post(bank_api_url, data=payload)
  File "app/services/bank_connector.py", line 67, in post_transaction
    return self.session.post(url, json=data)
requests.exceptions.ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))"""
        ],

        "state": [
            """ValueError: invalid literal for int() with base 10: 'corrupted_data'
  File "app/api/v1/transactions.py", line 459, in create_corporate_transaction
    account_balance = int(corrupted_balance)
  File "app/services/account_service.py", line 78, in get_balance
    return Decimal(balance_str)
ValueError: transaction data corrupted during processing""",

            """KeyError: 'account_id'
  File "app/api/v1/transactions.py", line 476, in create_corporate_transaction
    account_data = user_accounts[tx.account_id]
  File "app/services/cache_service.py", line 156, in get_account_cache
    return self.cache[key]['data']
KeyError: 'account_id' not found in cached data structure""",

            """json.JSONDecodeError: Expecting ',' delimiter: line 1 column 67 (char 66)
  File "app/api/v1/transactions.py", line 487, in create_corporate_transaction
    metadata = json.loads(transaction_metadata)
  File "app/utils/json_parser.py", line 34, in parse_transaction_data
    return json.loads(raw_data)
json.JSONDecodeError: Invalid JSON format in transaction metadata""",

            """AssertionError: Account balance cannot be negative
  File "app/api/v1/transactions.py", line 498, in create_corporate_transaction
    assert account.balance >= 0, "Account balance cannot be negative"
  File "app/models/account.py", line 89, in validate_balance
    assert self.balance >= Decimal('0'), error_message
AssertionError: Account balance cannot be negative: -1500.50""",

            """UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0
  File "app/api/v1/transactions.py", line 509, in create_corporate_transaction
    decoded_data = transaction_blob.decode('utf-8')
  File "app/services/data_decoder.py", line 45, in decode_transaction_data
    return raw_bytes.decode(encoding)
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte""",

            """pickle.UnpicklingError: invalid load key, '\\x00'
  File "app/api/v1/transactions.py", line 520, in create_corporate_transaction
    session_data = pickle.loads(corrupted_session)
  File "app/services/session_manager.py", line 67, in deserialize_session
    return pickle.loads(session_bytes)
pickle.UnpicklingError: invalid load key, '\\x00'""",

            """decimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]
  File "app/api/v1/transactions.py", line 531, in create_corporate_transaction
    precise_amount = Decimal(malformed_amount)
  File "app/utils/decimal_converter.py", line 23, in convert_to_decimal
    return Decimal(value)
decimal.InvalidOperation: Invalid decimal format: 'NaN.123'"""
        ],

        "server_error": [
            """psycopg2.OperationalError: connection to server on socket "/tmp/.s.PGSQL.5432" failed
  File "app/api/v1/transactions.py", line 460, in create_corporate_transaction
    db.commit()
  File "app/database.py", line 23, in commit
    self.session.commit()
  File "sqlalchemy/orm/session.py", line 1428, in commit
    self._connection.commit()
psycopg2.OperationalError: database connection failed during transaction""",

            """redis.exceptions.ConnectionError: Error 111 connecting to redis:6379
  File "app/api/v1/transactions.py", line 473, in create_corporate_transaction
    await cache.set_transaction_state(tx_id, status)
  File "app/services/redis_service.py", line 67, in set_transaction_state
    return await self.redis.set(key, value)
redis.exceptions.ConnectionError: Connection refused by Redis server""",

            """kafka.errors.NoBrokersAvailable: NoBrokersAvailable
  File "app/api/v1/transactions.py", line 491, in create_corporate_transaction
    await send_transaction_event(event_data)
  File "app/kafka_producer.py", line 45, in send_transaction
    await producer.send(topic, value=data)
kafka.errors.NoBrokersAvailable: Unable to find any available brokers""",

            """sqlalchemy.exc.DatabaseError: (psycopg2.errors.DeadlockDetected)
  File "app/api/v1/transactions.py", line 502, in create_corporate_transaction
    db.execute(update_query, params)
  File "app/services/database_service.py", line 156, in execute_transaction
    return session.execute(stmt, parameters)
sqlalchemy.exc.DatabaseError: (psycopg2.errors.DeadlockDetected) deadlock detected""",

            """elasticsearch.exceptions.ConnectionError: Connection to Elasticsearch failed
  File "app/api/v1/transactions.py", line 513, in create_corporate_transaction
    search_result = await elasticsearch_client.index(document)
  File "app/services/search_service.py", line 89, in index_transaction
    return await self.es.index(index=index_name, document=doc)
elasticsearch.exceptions.ConnectionError: Connection to Elasticsearch cluster failed""",

            """celery.exceptions.WorkerLostError: Worker exited prematurely
  File "app/api/v1/transactions.py", line 524, in create_corporate_transaction
    task_result = background_task.delay(transaction_data)
  File "app/tasks/transaction_tasks.py", line 67, in process_transaction
    return heavy_processing(data)
celery.exceptions.WorkerLostError: Worker exited prematurely during task execution""",

            """botocore.exceptions.EndpointConnectionError: Could not connect to AWS S3
  File "app/api/v1/transactions.py", line 535, in create_corporate_transaction
    s3_response = await s3_client.put_object(bucket, key, data)
  File "app/services/s3_service.py", line 45, in upload_transaction_log
    return await self.s3.put_object(Bucket=bucket, Key=key, Body=body)
botocore.exceptions.EndpointConnectionError: Could not connect to the endpoint URL""",

            """pymongo.errors.ServerSelectionTimeoutError: No MongoDB servers available
  File "app/api/v1/transactions.py", line 546, in create_corporate_transaction
    mongo_result = await mongo_client.insert_document(collection, document)
  File "app/services/mongo_service.py", line 78, in insert_document
    return await self.db[collection].insert_one(doc)
pymongo.errors.ServerSelectionTimeoutError: timed out waiting for MongoDB server selection"""
        ]
    }

    # Return random variation for each crash type
    variations = crash_details.get(crash_type, [f"Unknown error: {crash_type}"])
    return random.choice(variations)


@router.get("/limits")
def get_transaction_limits():
    """Get current transaction limits and rules."""
    return {
        "limits": transaction_validation_service.get_transaction_limits(),
        "rules": {
            "balance_check": "Transaction amount must not exceed account balance",
            "minimum_amount": "Minimum transaction amount is Rp 1,000",
            "maximum_amount": "Maximum transaction amount per transaction is Rp 10,000,000", 
            "daily_limit": "Maximum total transactions per day is Rp 20,000,000",
            "account_status": "Account must be active to process transactions"
        },
        "validation_order": [
            "account_status",
            "minimum_amount", 
            "maximum_amount",
            "balance_check",
            "daily_limit_check"
        ]
    }


@router.post("/retail/qris-generate", response_model=GenerateQRISResponse)
async def create_retail_transaction_gen(
    data: GenerateQRISRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Generate QRIS code for retail transaction."""
    try:
        # Generate QRIS without PIN validation (per user request)
        return QRISService.generate_qris(data, current_user.customer_id)
    
    except HTTPException as e:
        # Re-raise HTTPExceptions as they are already properly formatted
        raise e
    except Exception as e:
        # Catch any other unexpected errors and provide detailed info
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Failed to generate QRIS",
                "message": str(e),
                "error_type": type(e).__name__
            }
        )


@router.post("/retail/qris-consume", response_model=ConsumeQRISResponse)
async def create_retail_transaction_consume(
        request: Request,
        data: ConsumeQRISRequest = Body(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Consume QRIS code for retail transaction with proper transaction recording."""
    try:
        print(f"QRIS Consume - User: {current_user.username}, Customer ID: {current_user.customer_id}")
        print(f"QRIS Consume - Request data: qris_code={data.qris_code[:20]}..., pin=***")

        # Get user's default account (first active account)
        print(f"QRIS Consume - Looking for accounts for user ID: {current_user.id}")

        all_user_accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
        print(f"QRIS Consume - All user accounts: {[acc.account_number for acc in all_user_accounts]}")

        user_account = db.query(Account).filter(
            Account.user_id == current_user.id,
            Account.status == "active"
        ).first()

        print(f"QRIS Consume - Active account found: {user_account.account_number if user_account else 'None'}")
        if user_account:
            print(
                f"QRIS Consume - Account details: {user_account.account_number}, Status: {user_account.status}, Balance: {user_account.balance}")

        if not user_account:
            print("QRIS Consume - No active account found")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "No active account found",
                    "message": "User does not have any active accounts to process payment."
                }
            )

        print(f"QRIS Consume - Validating QRIS...")
        qris_data, qris_id = await QRISService.validate_and_consume_qris(
            data,
            current_user.customer_id,
            db,
            request_headers=dict(request.headers),
            client_host=request.client.host if request.client else "unknown"
        )
        print("========", qris_data, qris_id)
        print(f"QRIS Consume - QRIS validated, ID: {qris_id}")

        # Prepare additional data for validation and recording
        additional_data = {
            "qris_id": qris_id,
            "merchant_name": qris_data["merchant_name"],
            "merchant_category": qris_data["merchant_category"],
            "reference_number": qris_id,
            "recipient_name": qris_data["merchant_name"]
        }

        # Validate transaction (balance, limits, etc.)
        print(f"QRIS Consume - Validating transaction amount: {qris_data['amount']}")
        await transaction_validation_service.validate_transaction(
            user=current_user,
            account=user_account,
            amount=qris_data["amount"],
            transaction_type="qris_consume",
            db=db,
            additional_data=additional_data
        )
        print("QRIS Consume - Transaction validation passed")

        # Validate PIN after transaction validation
        await pin_validation_service.validate_pin_or_fail(
            current_user,
            data.pin,
            data.crash_type,
            "qris_consume",
            qris_data["amount"],
            {"account_number": user_account.account_number, "qris_id": qris_id,
             "merchant_name": qris_data["merchant_name"]}
        )

        if data.crash_type:
            raise Exception(f"Simulated crash at PIN validation: {data.crash_type}")

        # Update account balance and create transaction history
        balance_before = user_account.balance
        amount_decimal = Decimal(str(qris_data["amount"]))
        user_account.balance -= amount_decimal
        balance_after = user_account.balance

        # Create transaction history record
        transaction_history = TransactionHistory(
            user_id=current_user.id,
            account_id=user_account.id,
            transaction_id=qris_id,
            transaction_type="qris_consume",
            amount=qris_data["amount"],
            currency=qris_data["currency"],
            balance_before=balance_before,
            balance_after=balance_after,
            status="success",
            description=f"QRIS payment to {qris_data['merchant_name']}",
            reference_number=qris_id,
            recipient_account=None,
            recipient_name=qris_data["merchant_name"],
            channel="mobile_app"
        )

        db.add(transaction_history)
        db.commit()
        db.refresh(user_account)
        db.refresh(transaction_history)

        transaction_data = await EnhancedTransactionService.create_enhanced_retail_transaction_data(
            qris_data, current_user.customer_id, user_account.account_number
        )

        # Add transaction_id from our database record
        transaction_data["db_transaction_id"] = qris_id
        transaction_data["balance_after"] = balance_after
        transaction_data["qris_status"] = "CONSUMED"

        extra_fields = {
            "login_status": "success",
            "alert_type": "",
            "alert_severity": "",
            "failed_attempts": "",
            "time_window_minutes": "",
            "login_attempts": "",
            "attempted_amount": "",
            "attempted_transaction_type": "",
            "attempted_channel": "",
            "attempted_account_number": "",
            "attempted_recipient_account": "",
            "attempted_merchant_name": "",
            "attempted_merchant_category": "",
            "auth_timestamp": "",
            "error_type": data.crash_type,
            "error_code": "",
            "error_detail": "",
            "validation_stage": "",
            "transaction_description": "",
            "recipient_account_number": "",
            "recipient_account_name": "",
            "recipient_bank_code": "",
            "reference_number": "",
            "risk_assessment_score": "",
            "fraud_indicator": "",
            "aml_screening_result": "",
            "sanction_screening_result": "",
            "compliance_status": "",
            "settlement_status": "",
            "clearing_code": "",
            "requested_amount": "",
            "failure_reason": "",
            "failure_message": "",
            "limits": ""
        }

        for k, v in extra_fields.items():
            transaction_data.setdefault(k, v)

        # Send to Kafka for additional processing (notifications, analytics, etc.)
        await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)
        print("QRIS Consume - Transaction sent to Kafka")

        return ConsumeQRISResponse(
            qris_id=qris_id,
            status="SUCCESS",
            message=f"Payment of {qris_data['amount']} {qris_data['currency']} to {qris_data['merchant_name']} completed from account {user_account.account_number}.",
            transaction_id=qris_id,  # Return our transaction ID
            balance_after=balance_after
        )

    except HTTPException as e:
        # Record failed transaction for audit (don't raise if this fails)
        try:
            if 'user_account' in locals() and 'qris_data' in locals():
                await TransactionRecordingService.record_failed_transaction(
                    user=current_user,
                    account=user_account,
                    amount=qris_data["amount"],
                    transaction_type="qris_consume",
                    failure_reason=str(e.detail),
                    db=db,
                    additional_data=additional_data if 'additional_data' in locals() else {}
                )
                db.commit()  # Commit the failed transaction record
        except Exception as record_error:
            print(f"Failed to record failed transaction: {record_error}")

        # Re-raise the original HTTPException
        raise e
    except Exception as e:
        # Record failed transaction for unexpected errors
        try:
            if 'user_account' in locals():
                amount = qris_data["amount"] if 'qris_data' in locals() else Decimal("0")
                await TransactionRecordingService.record_failed_transaction(
                    user=current_user,
                    account=user_account,
                    amount=amount,
                    transaction_type="qris_consume",
                    failure_reason=f"System error: {str(e)}",
                    db=db,
                    additional_data=additional_data if 'additional_data' in locals() else {}
                )
                db.commit()
        except Exception as record_error:
            print(f"Failed to record failed transaction: {record_error}")

        # Catch any other unexpected errors and provide detailed info
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to consume QRIS",
                "message": str(e),
                "error_type": type(e).__name__
            }
        )


@router.post("/qris/scan")
async def scan_qris(request: Request,
                    current_user: User = Depends(get_current_user)):
    await TransactionService.error_qris_scan(request, current_user)

    return {"status": "error", "message": "error_scan_qris"}


@router.post("/corporate")
async def create_corporate_transaction(
        request: Request,
        tx: TransactionCorporateInput = Body(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Process corporate transaction."""
    validation_stage = None

    try:
        # Stage 1: Account validation
        validation_stage = "account_validation"
        user_account = db.query(Account).filter(Account.user_id == current_user.id,
                                                Account.account_number == tx.account_number,
                                                Account.status == "active").first()

        if not user_account:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Account not found",
                    "message": f"Active account {tx.account_number} not found for current user"
                }
            )

        # Stage 1.5: Recipient account validation
        validation_stage = "recipient_account_validation"
        recipient_account = db.query(Account).filter(Account.account_number == tx.recipient_account_number,
                                                     Account.status == "active").first()

        if not recipient_account:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Recipient account not found",
                    "message": f"Active recipient account {tx.recipient_account_number} not found"
                }
            )

        # Prevent self-transfer
        if user_account.account_number == recipient_account.account_number:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid transfer",
                    "message": "Cannot transfer to the same account"
                }
            )

        # Stage 2: Transaction validation
        validation_stage = "transaction_validation"
        await transaction_validation_service.validate_transaction(
            user=current_user,
            account=user_account,
            amount=tx.amount,
            transaction_type=tx.transaction_type,
            db=db,
            additional_data={
                "merchant_name": tx.merchant_name,
                "merchant_category": tx.merchant_category,
                "channel": tx.channel,
                "recipient_account": tx.recipient_account_number
            }
        )

        # Stage 2.5: Fraud detection for large transfers
        if tx.transaction_type == "transfer" and tx.amount >= 100000000:
            # Check for recent large transfers in the last 10 minutes
            ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
            recent_large_transfers = db.query(TransactionHistory).filter(
                TransactionHistory.user_id == current_user.id,
                TransactionHistory.transaction_type == "transfer_out",
                TransactionHistory.amount >= 100000000,
                TransactionHistory.created_at >= ten_minutes_ago,
                TransactionHistory.status == "success"
            ).all()

            # If more than 3 large transfers in 10 minutes, send fraud alert to Kafka
            if len(recent_large_transfers) >= 3:
                print(f"FRAUD ALERT: User {current_user.customer_id} has made {len(recent_large_transfers) + 1} large transfers (>100M) within 10 minutes")

                # Create fraud detection log data
                fraud_data = await EnhancedTransactionService.create_error_transaction_data(
                    error_type="fraud_alert_large_transfers",
                    error_code=200,  # Not an error, just an alert
                    error_detail={
                        "message": f"User has made {len(recent_large_transfers) + 1} transfers greater than 100,000,000 within 10 minutes",
                        "current_transfer_amount": tx.amount,
                        "recent_transfers_count": len(recent_large_transfers),
                        "recent_transfer_amounts": [float(t.amount) for t in recent_large_transfers],
                        "time_window_minutes": 10,
                        "threshold_amount": 100000000,
                        "recipient_account": tx.recipient_account_number,
                        "alert_severity": "HIGH"
                    },
                    transaction_input=tx.model_dump(),
                    customer_id=current_user.customer_id,
                    request_headers=dict(request.headers),
                    client_host=request.client.host if request.client else "unknown",
                    validation_stage="fraud_detection"
                )

                # Override some fields for fraud alert
                fraud_data["log_type"] = "fraud_alert"
                fraud_data["alert_type"] = "multiple_large_transfers"
                fraud_data["alert_severity"] = "HIGH"
                fraud_data["risk_assessment_score"] = 0.95
                fraud_data["fraud_indicator"] = True

                # Send fraud alert to Kafka
                await EnhancedTransactionService.send_error_to_kafka(fraud_data)

        # Stage 3: PIN validation
        validation_stage = "pin_validation"
        await pin_validation_service.validate_pin_or_fail(
            current_user,
            tx.pin,
            tx.crash_type,
            "corporate_transaction",
            tx.amount,
            {
                "account_number": tx.account_number,
                "transaction_type": tx.transaction_type,
                "merchant_name": tx.merchant_name
            }
        )

        client_host = request.client.host
        amount_decimal = Decimal(str(tx.amount))

        # Store balances before transaction
        sender_balance_before = user_account.balance

        # Stage 4: Balance updates
        validation_stage = "balance_update"

        # Update sender balance (debit)
        user_account.balance -= amount_decimal
        sender_balance_after = user_account.balance

        # Update recipient balance (credit)
        recipient_account.balance += amount_decimal

        # Stage 5: Transaction processing
        validation_stage = "transaction_processing"
        error_type = tx.crash_type
        tx_dict = tx.model_dump()

        transaction_data = await EnhancedTransactionService.create_enhanced_corporate_transaction_data(
            tx_dict, current_user.customer_id, dict(request.headers), request.client.host
        )
        transaction_service_data = await TransactionService.create_corporate_transaction_data(
            transaction_data=transaction_data,
            customer_id=str(current_user.customer_id),
            request_headers=dict(request.headers),
            client_host=client_host
        )

        # Create transaction history record for SENDER
        transaction_history = TransactionHistory(
            user_id=current_user.id,
            account_id=user_account.id,
            transaction_id=transaction_service_data["transaction_id"],
            transaction_type="transfer_out",
            amount=amount_decimal,
            currency=tx.currency,
            balance_before=Decimal(str(sender_balance_before)),
            balance_after=Decimal(str(sender_balance_after)),
            status="success",
            description=tx.transaction_description,
            reference_number=tx.reference_number,
            recipient_account=tx.recipient_account_number,
            recipient_name=tx.recipient_account_name,
            channel="mobile_app"
        )

        # Add both transaction histories
        db.add(transaction_history)

        # Commit all changes together
        db.commit()

        # Refresh all objects
        db.refresh(user_account)
        db.refresh(recipient_account)
        db.refresh(transaction_history)

        # Crash simulation after successful transaction commit
        if tx.crash_type:
            raise Exception(f"Simulated crash after transaction commit: {tx.crash_type}")

        extra_fields = {
            "customer_age": random.randint(25, 60),
            "customer_gender": random.choice(["M", "F"]),
            "customer_occupation": random.choice(["karyawan", "wiraswasta", "pns", "direktur", "manager"]),
            "customer_income_bracket": random.choice(["5-10jt", "10-25jt", "25-50jt", ">50jt"]),
            "customer_education": random.choice(["S1", "S2", "S3"]),
            "customer_marital_status": random.choice(["married", "single"]),
            "customer_monthly_income": random.uniform(10000000, 100000000),
            "customer_credit_limit": random.uniform(50000000, 500000000),
            "customer_risk_score": round(random.uniform(0.1, 0.4), 3),
            "customer_kyc_level": random.choice(["enhanced", "premium"]),
            "customer_pep_status": random.choice([True, False]),
            "customer_previous_fraud_incidents": random.randint(0, 1),
            "device_fingerprint": f"fp_{uuid.uuid4().hex[:16]}",
            "qris_id": "",
            "transaction_reference": f"REF{datetime.utcnow().strftime('%Y%m%d')}{random.randint(100000, 999999)}",
            "interchange_fee": round(float(tx.amount) * 0.005, 2),
            "db_transaction_id": f"db_{uuid.uuid4().hex[:12]}",
            "balance_after": float(sender_balance_after),
            "qris_status": "",
            "error_type": error_type if error_type else "",
            "error_code": "CRASH_SIMULATION" if error_type else "",
            "error_detail": _get_crash_error_detail(error_type) if error_type else ""
        }

        for k, v in extra_fields.items():
            transaction_data.setdefault(k, v)

        print("====create_corporate_transaction\n", transaction_data)
        await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)

        return {"status": "success", "transaction": transaction_data}

    except HTTPException as http_exc:
        # Rollback any database changes
        db.rollback()

        # Send HTTP error to Kafka
        error_data = await EnhancedTransactionService.create_error_transaction_data(
            error_type="http_error",
            error_code=http_exc.status_code,
            error_detail=http_exc.detail,
            transaction_input=tx.model_dump(),
            customer_id=current_user.customer_id,
            request_headers=dict(request.headers),
            client_host=request.client.host,
            validation_stage=validation_stage
        )

        cities = [
            {"country": "Indonesia", "city": "Jakarta", "lat": -6.2088, "lon": 106.8456},
            {"country": "Indonesia", "city": "Bandung", "lat": -6.9175, "lon": 107.6191},
            {"country": "Indonesia", "city": "Surabaya", "lat": -7.2575, "lon": 112.7521},
            {"country": "Indonesia", "city": "Medan", "lat": 3.5952, "lon": 98.6722},
            {"country": "Indonesia", "city": "Denpasar", "lat": -8.65, "lon": 115.2167},
            {"country": "Indonesia", "city": "Makassar", "lat": -5.1477, "lon": 119.4327},
        ]

        geo_info = random.choice(cities)

        extra_fields = {
            "account_number": "",
            "amount": "",
            "channel": "",
            "branch_code": "string",
            "province": "string",
            "city": "string",
            "merchant_name": "string",
            "merchant_category": "string",
            "merchant_id": "string",
            "terminal_id": "string",
            "latitude": geo_info["lat"],
            "longitude": geo_info["lon"],
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

        for k, v in extra_fields.items():
            error_data.setdefault(k, v)

        print("====create_corporate_transaction==EXCEPTION==1==\n", error_data)
        await EnhancedTransactionService.send_error_to_kafka(error_data)

        # Re-raise the original exception
        raise http_exc

    except Exception as exc:
        # Rollback any database changes
        db.rollback()

        # Send system error to Kafka
        # Check if this is a crash simulation
        crash_detail = None
        if "Simulated crash" in str(exc) and tx.crash_type:
            crash_detail = _get_crash_error_detail(tx.crash_type)

        error_data = await EnhancedTransactionService.create_error_transaction_data(
            error_type="system_error",
            error_code=500,
            error_detail={
                "error": "Failed to process corporate transaction",
                "message": str(exc),
                "error_type": type(exc).__name__,
                "traceback": crash_detail if crash_detail else str(exc)
            },
            transaction_input=tx.model_dump(),
            customer_id=current_user.customer_id,
            request_headers=dict(request.headers),
            client_host=request.client.host,
            validation_stage=validation_stage
        )
        print("====create_corporate_transaction==EXCEPTION==2==\n", error_data)
        await EnhancedTransactionService.send_error_to_kafka(error_data)

        # Raise HTTP exception for client
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to process corporate transaction",
                "message": str(exc),
                "error_type": type(exc).__name__
            }
        )


@router.post("/anomaly-detection")
async def anomaly_detection(result: DetectionResult, db: Session = Depends(get_db)):
    def remove_empty_fields(obj):
        if isinstance(obj, dict):
            return {k: remove_empty_fields(v) for k, v in obj.items() if v not in [None, ""]}

        elif isinstance(obj, list):
            return [remove_empty_fields(v) for v in obj if v not in [None, ""]]

        else:
            return obj

    clean_result = remove_empty_fields(result.model_dump())

    try:
        now = datetime.utcnow()
        success_event = StandardKafkaEvent(timestamp=now,
                                           log_type="anomaly_detection",
                                           processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
                                           aml_screening_result=json.dumps(clean_result))
        event_data = success_event.model_dump(exclude_none=True)
        event_data['timestamp'] = success_event.timestamp.isoformat() + 'Z'

        # await send_transaction(event_data)
        await FoundryAnalytics.foundry_processing(event_data, db)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


@router.post("/velocity-violation")
async def create_velocity_violation(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report velocity violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@router.post("/compliance-violation/aml-reporting")
async def create_aml_reporting(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report AML compliance violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@router.post("/compliance-violation/kyc-gap")
async def create_kyc_gap(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report KYC gap violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}
