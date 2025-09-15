"""Database utility functions for connection handling and retries."""

import time
from typing import Callable, TypeVar, Any
from contextlib import contextmanager
from sqlalchemy.exc import OperationalError, DatabaseError, InvalidRequestError
from sqlalchemy.orm import Session

T = TypeVar('T')

def retry_db_operation(
    operation: Callable[[], T],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0
) -> T:
    """
    Retry database operations with exponential backoff and proper rollback handling.

    Args:
        operation: Function to execute that may fail due to DB issues
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry

    Returns:
        Result of the operation

    Raises:
        Exception: The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return operation()
        except (OperationalError, DatabaseError, InvalidRequestError) as e:
            last_exception = e
            print(f"🔧 DB ERROR (attempt {attempt + 1}): {e}")

            # Handle specific SQLAlchemy errors
            if any(error_type in str(e) for error_type in [
                "PendingRollbackError",
                "rollback",
                "invalid transaction",
                "server closed the connection",
                "connection was closed",
                "Lost connection",
                "MySQL server has gone away",
                "server closed the connection unexpectedly"
            ]):
                print("🔧 Detected transaction/connection error - attempting recovery")
                try:
                    # Try to get the session from the operation context and rollback
                    import inspect
                    frame = inspect.currentframe()
                    while frame:
                        if 'db' in frame.f_locals:
                            db_session = frame.f_locals['db']
                            try:
                                if hasattr(db_session, 'rollback'):
                                    print("🔧 Rolling back pending transaction")
                                    db_session.rollback()
                            except Exception:
                                pass  # Ignore rollback errors on dead connections

                            try:
                                if hasattr(db_session, 'close'):
                                    print("🔧 Closing session for fresh connection")
                                    db_session.close()
                            except Exception:
                                pass  # Ignore close errors on dead connections

                            # Try to dispose engine connections if accessible
                            try:
                                if hasattr(db_session, 'bind') and hasattr(db_session.bind, 'dispose'):
                                    print("🔧 Disposing engine connections")
                                    db_session.bind.dispose()
                            except Exception:
                                pass
                            break
                        frame = frame.f_back
                except Exception as rollback_error:
                    print(f"🔧 Failed to recover session: {rollback_error}")

            if attempt == max_retries:
                # Last attempt failed, re-raise the exception
                raise e

            # Wait before retrying with exponential backoff
            wait_time = delay * (backoff_factor ** attempt)
            print(f"🔧 Waiting {wait_time}s before retry {attempt + 2}")
            time.sleep(wait_time)

    # This should never be reached, but just in case
    if last_exception:
        raise last_exception


def safe_db_query(db: Session, query_func: Callable[[Session], T]) -> T:
    """
    Execute a database query with automatic retry logic and rollback handling.

    Args:
        db: SQLAlchemy database session
        query_func: Function that takes a session and returns query result

    Returns:
        Query result

    Raises:
        DatabaseError: If all retry attempts fail
    """
    def operation():
        try:
            # Check if we need to rollback first
            if hasattr(db, 'in_transaction') and db.in_transaction():
                if hasattr(db, 'get_transaction') and db.get_transaction():
                    if db.get_transaction().is_active:
                        print("🔧 Active transaction detected - rolling back before query")
                        db.rollback()
        except Exception as rollback_error:
            print(f"🔧 Rollback check failed: {rollback_error}")
            # Force rollback anyway
            try:
                db.rollback()
            except:
                pass

        return query_func(db)

    def operation_with_session():
        try:
            return operation()
        except Exception as e:
            # Always rollback on error to prevent PendingRollbackError
            try:
                print(f"🔧 Query failed, rolling back: {e}")
                db.rollback()
            except Exception as rollback_error:
                print(f"🔧 Rollback failed: {rollback_error}")
            raise e

    return retry_db_operation(operation_with_session)


def check_db_connection(db: Session) -> bool:
    """
    Check if database connection is healthy.

    Args:
        db: SQLAlchemy database session

    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        # Execute a simple query to test connection
        db.execute("SELECT 1")
        return True
    except (OperationalError, DatabaseError):
        return False


def get_db_error_details(error: Exception) -> dict:
    """
    Extract detailed information from database errors.

    Args:
        error: Database exception

    Returns:
        Dictionary with error details
    """
    details = {
        "exception_type": type(error).__name__,
        "error_message": str(error)
    }

    # Extract PostgreSQL-specific error codes if available
    if hasattr(error, 'orig') and error.orig:
        details["pg_code"] = getattr(error.orig, 'pgcode', None)
        details["pg_message"] = getattr(error.orig, 'pgerror', None)

    # Extract SQLAlchemy-specific details
    if hasattr(error, 'statement'):
        details["sql_statement"] = str(error.statement)

    if hasattr(error, 'params'):
        details["sql_params"] = str(error.params)

    return details


@contextmanager
def safe_db_session(db: Session):
    """
    Context manager for safe database session handling with automatic rollback.

    Args:
        db: SQLAlchemy database session

    Usage:
        with safe_db_session(db) as session:
            result = session.query(User).first()
    """
    try:
        print("🔧 Starting safe database session")

        # Check if session needs cleanup first
        try:
            if hasattr(db, 'in_transaction') and db.in_transaction():
                print("🔧 Rolling back existing transaction")
                db.rollback()
        except Exception as cleanup_error:
            print(f"🔧 Session cleanup warning: {cleanup_error}")

        yield db

        # If we get here, operation was successful
        if hasattr(db, 'commit'):
            db.commit()
        print("🔧 Database session completed successfully")

    except Exception as e:
        print(f"🔧 Database session error: {e}")
        try:
            db.rollback()
            print("🔧 Rolled back transaction due to error")
        except Exception as rollback_error:
            print(f"🔧 Rollback failed: {rollback_error}")
        raise e
    finally:
        print("🔧 Safe database session ended")