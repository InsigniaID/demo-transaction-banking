import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.kafka_producer import send_transaction
from app.models import TransactionHistory, Account, User, QRISTransaction


class TransactionRecordingService:
    """Service for recording transactions to database and ensuring data consistency."""

    @staticmethod
    async def record_successful_transaction(
            user: User,
            account: Account,
            amount: Decimal,
            transaction_type: str,
            db: Session,
            additional_data: Dict[str, Any] = None
    ) -> TransactionHistory:
        """
        Record a successful transaction to database.
        This should be called AFTER all validations pass but BEFORE processing payment.
        """
        try:
            additional_data = additional_data or {}

            # Generate unique transaction ID
            transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:8].upper()}"

            # Calculate balance before/after
            balance_before = account.balance
            balance_after = balance_before - amount  # For debit transactions

            # Create transaction record
            transaction_record = TransactionHistory(
                user_id=user.id,
                account_id=account.id,
                transaction_id=transaction_id,
                transaction_type=transaction_type,
                amount=amount,
                currency="IDR",
                balance_before=balance_before,
                balance_after=balance_after,
                status="success",  # Mark as success since validation passed
                description=TransactionRecordingService._generate_description(transaction_type, additional_data),
                reference_number=additional_data.get("reference_number"),
                recipient_account=additional_data.get("recipient_account"),
                recipient_name=additional_data.get("recipient_name", additional_data.get("merchant_name")),
                channel="mobile_app",  # or get from additional_data
                created_at=datetime.now()
            )

            # Save to database
            db.add(transaction_record)
            db.flush()  # Flush to get the ID but don't commit yet

            print(f"Transaction recorded successfully: {transaction_id} for user {user.customer_id}")

            # Send to Kafka for additional processing/notifications
            await TransactionRecordingService._send_transaction_event(
                transaction_record, user, account, additional_data
            )

            return transaction_record

        except SQLAlchemyError as e:
            print(f"Database error recording transaction: {str(e)}")
            db.rollback()
            raise Exception(f"Failed to record transaction: {str(e)}")
        except Exception as e:
            print(f"Unexpected error recording transaction: {str(e)}")
            db.rollback()
            raise

    @staticmethod
    async def record_failed_transaction(
            user: User,
            account: Account,
            amount: Decimal,
            transaction_type: str,
            failure_reason: str,
            db: Session,
            additional_data: Dict[str, Any] = None
    ) -> TransactionHistory:
        """
        Record a failed transaction for audit purposes.
        This helps in fraud detection and user behavior analysis.
        """
        try:
            additional_data = additional_data or {}

            # Generate unique transaction ID
            transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:8].upper()}"

            # Create failed transaction record
            transaction_record = TransactionHistory(
                user_id=user.id,
                account_id=account.id,
                transaction_id=transaction_id,
                transaction_type=transaction_type,
                amount=amount,
                currency="IDR",
                balance_before=account.balance,
                balance_after=account.balance,  # No balance change for failed transaction
                status="failed",
                description=f"Failed: {failure_reason}. {TransactionRecordingService._generate_description(transaction_type, additional_data)}",
                reference_number=additional_data.get("reference_number"),
                recipient_account=additional_data.get("recipient_account"),
                recipient_name=additional_data.get("recipient_name", additional_data.get("merchant_name")),
                channel="mobile_app",
                created_at=datetime.now()
            )

            # Save to database
            db.add(transaction_record)
            db.flush()

            print(f"Failed transaction recorded: {transaction_id} for user {user.customer_id}, reason: {failure_reason}")

            return transaction_record

        except Exception as e:
            print(f"Error recording failed transaction: {str(e)}")
            # Don't raise here as we don't want to mask the original failure
            return None

    @staticmethod
    async def update_account_balance(
            account: Account,
            new_balance: Decimal,
            db: Session
    ) -> None:
        """
        Update account balance after successful transaction.
        This should be called within the same database transaction.
        """
        try:
            old_balance = account.balance
            account.balance = new_balance
            db.flush()

            print(f"Account balance updated: {account.account_number} from {old_balance} to {new_balance}")

        except Exception as e:
            print(f"Failed to update account balance: {str(e)}")
            raise

    @staticmethod
    async def process_complete_transaction(
            user: User,
            account: Account,
            amount: Decimal,
            transaction_type: str,
            db: Session,
            additional_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Complete transaction processing with proper database recording.
        This combines recording + balance update in a single transaction.
        """
        try:
            # Start database transaction
            db.begin()

            # 1. Record the transaction
            transaction_record = await TransactionRecordingService.record_successful_transaction(
                user, account, amount, transaction_type, db, additional_data
            )

            # 2. Update account balance
            new_balance = account.balance - amount  # For debit transactions
            await TransactionRecordingService.update_account_balance(
                account, new_balance, db
            )

            # 3. Commit the transaction
            db.commit()

            print(f"Complete transaction processed successfully: {transaction_record.transaction_id}")

            return {
                "transaction_id": transaction_record.transaction_id,
                "status": "success",
                "balance_before": float(transaction_record.balance_before),
                "balance_after": float(transaction_record.balance_after),
                "created_at": transaction_record.created_at.isoformat()
            }

        except Exception as e:
            db.rollback()
            print(f"Complete transaction processing failed: {str(e)}")

            # Record failed transaction for audit
            await TransactionRecordingService.record_failed_transaction(
                user, account, amount, transaction_type, str(e), db, additional_data
            )

            raise

    @staticmethod
    def _generate_description(transaction_type: str, additional_data: Dict[str, Any]) -> str:
        """Generate transaction description based on type and additional data."""
        descriptions = {
            "qris_consume": f"QRIS Payment to {additional_data.get('merchant_name', 'Merchant')}",
            "transfer": f"Transfer to {additional_data.get('recipient_name', 'Recipient')}",
            "withdrawal": "Cash Withdrawal",
            "pos_purchase": f"POS Purchase at {additional_data.get('merchant_name', 'Merchant')}",
            "online_purchase": f"Online Purchase at {additional_data.get('merchant_name', 'Merchant')}"
        }

        return descriptions.get(transaction_type, f"Transaction: {transaction_type}")

    @staticmethod
    async def _send_transaction_event(
            transaction_record: TransactionHistory,
            user: User,
            account: Account,
            additional_data: Dict[str, Any]
    ) -> None:
        """Send transaction event to Kafka for notifications/further processing."""
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "log_type": "transaction_event",
                "event_type": "transaction_completed",
                "transaction_id": transaction_record.transaction_id,
                "customer_id": user.customer_id,
                "account_number": account.account_number,
                "transaction_type": transaction_record.transaction_type,
                "amount": float(transaction_record.amount),
                "balance_before": float(transaction_record.balance_before),
                "balance_after": float(transaction_record.balance_after),
                "status": transaction_record.status,
                "description": transaction_record.description,
                "additional_data": additional_data
            }

            await send_transaction(event_data)

        except Exception as e:
            print(f"Failed to send transaction event to Kafka: {str(e)}")

    @staticmethod
    async def process_complete_transaction(
            user: User,
            account: Account,
            amount: Decimal,
            transaction_type: str,
            db: Session,
            additional_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Complete transaction processing with proper database recording.
        This combines recording + balance update in a single transaction.
        For QRIS transactions, use record_qris_transaction instead.
        """
        try:
            # Start database transaction
            db.begin()

            # 1. Record the transaction
            transaction_record = await TransactionRecordingService.record_successful_transaction(
                user, account, amount, transaction_type, db, additional_data
            )

            # 2. Update account balance
            new_balance = account.balance - amount  # For debit transactions
            await TransactionRecordingService.update_account_balance(
                account, new_balance, db
            )

            # 3. Commit the transaction
            db.commit()

            print(f"Complete transaction processed successfully: {transaction_record.transaction_id}")

            return {
                "transaction_id": transaction_record.transaction_id,
                "status": "success",
                "balance_before": float(transaction_record.balance_before),
                "balance_after": float(transaction_record.balance_after),
                "created_at": transaction_record.created_at.isoformat()
            }

        except Exception as e:
            db.rollback()
            print(f"Complete transaction processing failed: {str(e)}")

            # Record failed transaction for audit
            await TransactionRecordingService.record_failed_transaction(
                user, account, amount, transaction_type, str(e), db, additional_data
            )

            raise

    @staticmethod
    async def get_qris_transaction_details(qris_id: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get QRIS transaction details with related transaction history."""
        try:
            qris_transaction = db.query(QRISTransaction).filter(
                QRISTransaction.qris_id == qris_id
            ).first()

            if not qris_transaction:
                return None

            # Get related transaction history
            transaction_history = db.query(TransactionHistory).filter(
                TransactionHistory.reference_number == qris_id
            ).first()

            return {
                "qris_id": qris_transaction.qris_id,
                "status": qris_transaction.status,
                "amount": float(qris_transaction.amount),
                "merchant_name": qris_transaction.merchant_name,
                "merchant_category": qris_transaction.merchant_category,
                "account_number": qris_transaction.account_number,
                "expired_at": qris_transaction.expired_at.isoformat() if qris_transaction.expired_at else None,
                "created_at": qris_transaction.created_at.isoformat(),
                "transaction_id": transaction_history.transaction_id if transaction_history else None,
                "balance_after": float(transaction_history.balance_after) if transaction_history else None
            }

        except Exception as e:
            print(f"Error fetching QRIS transaction details: {str(e)}")
            return None

    @staticmethod
    async def get_recent_transactions(
            user: User,
            db: Session,
            limit: int = 10,
            transaction_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent transactions for user."""
        try:
            query = db.query(TransactionHistory).filter(
                TransactionHistory.user_id == user.id
            )

            if transaction_type:
                query = query.filter(TransactionHistory.transaction_type == transaction_type)

            transactions = query.order_by(
                TransactionHistory.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    "transaction_id": tx.transaction_id,
                    "transaction_type": tx.transaction_type,
                    "amount": float(tx.amount),
                    "status": tx.status,
                    "description": tx.description,
                    "balance_after": float(tx.balance_after),
                    "created_at": tx.created_at.isoformat(),
                    "recipient_name": tx.recipient_name
                }
                for tx in transactions
            ]

        except Exception as e:
            print(f"Error fetching recent transactions: {str(e)}")
            return []