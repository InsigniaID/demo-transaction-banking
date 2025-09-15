from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DatabaseError, InvalidRequestError

from ...api.deps import get_db
from ...auth import get_current_user
from ...models import TransactionHistory, User, Account
from ...schemas import (
    UserCreate, UserWithAccountsResponse, RegisterResponse,
    PINValidationRequest, PINValidationResponse, EnhancedLoginRequest,
    EnhancedLoginResponse
)
from ...security import get_password_hash, get_pin_hash, verify_password, verify_pin, create_access_token
from ...services.auth_service import auth_service, AuthService
from ...services.location_service import location_service
from ...database_utils import safe_db_query, get_db_error_details

router = APIRouter()


@router.post("/auth/login")
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """Universal login endpoint supporting both OAuth2 form data and enhanced JSON requests."""
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    # Determine request type and extract data
    content_type = request.headers.get("content-type", "")
    is_json = "application/json" in content_type

    print(f"🔍 TRACE: Login request - Content-Type: {content_type}")
    if is_json:
        # JSON request with enhanced features
        try:
            json_data = await request.json()
            login_data = EnhancedLoginRequest(**json_data)
            username = login_data.username
            password = login_data.password
            location_enabled = login_data.locationDetectionEnabled or False
            selected_location = login_data.selectedLocation or ""
            crash_enabled = login_data.crashSimulatorEnabled or False
            crash_type = login_data.crashType or ""
            db_error_sim = login_data.databaseErrorSimulationEnabled or False
            request_payload = login_data.model_dump()
            print("🔍 TRACE: JSON request with enhanced features")
        except Exception as e:
            print(f"🔍 TRACE: JSON parsing error: {e}")
            if is_json:
                return EnhancedLoginResponse(success=False, error="Invalid JSON data")
            else:
                raise HTTPException(status_code=400, detail="Invalid JSON data")
    else:
        # Form data request (OAuth2 compatible + enhanced features)
        try:
            form_data = await request.form()
            print(f"🔍 TRACE: Form data received: {form_data}")
            username = form_data.get("username")
            password = form_data.get("password")
            if not username or not password:
                raise HTTPException(status_code=400, detail="Username and password required")

            # Extract enhanced features from form data if present (using snake_case field names)
            location_enabled = form_data.get("location_detection_enabled", "false").lower() == "true"
            selected_location = form_data.get("selected_location", "")
            crash_enabled = form_data.get("crash_simulator_enabled", "false").lower() == "true"
            print(f"🔍 TRACE: crash_enabled from form data: {form_data.get('crash_simulator_enabled')}")

            crash_type = form_data.get("crash_type", "")
            db_error_sim = form_data.get("database_error_simulation_enabled", "false").lower() == "true"

            request_payload = {
                "username": username,
                "endpoint": "/auth/login",
                "locationDetectionEnabled": location_enabled,
                "selectedLocation": selected_location,
                "crashSimulatorEnabled": crash_enabled,
                "crashType": crash_type,
                "databaseErrorSimulationEnabled": db_error_sim
            }
            print("🔍 TRACE: Form data request (OAuth2 + enhanced features)")
        except HTTPException:
            raise
        except Exception as e:
            print(f"🔍 TRACE: Form data parsing error: {e}")
            raise HTTPException(status_code=400, detail="Invalid form data")

    print(f"🔍 TRACE: Login for '{username}' - Location:{location_enabled}, Crash:{crash_enabled}")

    try:
        # 1. VALIDATION PHASE
        # Validate location if enabled
        if location_enabled and selected_location:
            if not location_service.get_location_info(selected_location):
                await auth_service.send_login_error_event(
                    error_type="invalid_location",
                    username=username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=f"Invalid location: {selected_location}",
                    request_payload=request_payload
                )
                if is_json:
                    return EnhancedLoginResponse(success=False, error="Invalid location")
                else:
                    raise HTTPException(status_code=400, detail="Invalid location")

        # Validate crash type if enabled
        if crash_enabled:
            if not crash_type:
                await auth_service.send_login_error_event(
                    error_type="missing_crash_type",
                    username=username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message="Crash simulator enabled but no crash type specified",
                    request_payload=request_payload
                )
                error_msg = "Crash simulator enabled but no crash type specified"
                if is_json:
                    return EnhancedLoginResponse(success=False, error=error_msg)
                else:
                    raise HTTPException(status_code=400, detail=error_msg)

            valid_crash_types = ["runtime", "memory", "infinite-loop", "network", "state"]
            if crash_type not in valid_crash_types:
                await auth_service.send_login_error_event(
                    error_type="invalid_crash_type",
                    username=username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=f"Invalid crash type: {crash_type}",
                    request_payload=request_payload
                )
                error_msg = f"Invalid crash type: {crash_type}"
                if is_json:
                    return EnhancedLoginResponse(success=False, error=error_msg)
                else:
                    raise HTTPException(status_code=400, detail=error_msg)

        # Database error simulation
        if db_error_sim:
            await auth_service.send_login_error_event(
                error_type="database_error_simulation",
                username=username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Simulated database error for testing",
                request_payload=request_payload
            )
            error_msg = "Database service temporarily unavailable (simulated)"
            if is_json:
                return EnhancedLoginResponse(success=False, error=error_msg)
            else:
                raise HTTPException(status_code=503, detail=error_msg)

        # 2. DATABASE QUERY PHASE
        try:
            user = safe_db_query(
                db,
                lambda session: session.query(User).filter(User.username == username).first()
            )
        except (OperationalError, DatabaseError, InvalidRequestError) as db_error:
            error_details = get_db_error_details(db_error)
            await auth_service.send_login_error_event(
                error_type="database_error",
                username=username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=f"Database connection error: {str(db_error)}",
                error_details=error_details,
                request_payload=request_payload
            )
            error_msg = "Database service temporarily unavailable"
            if is_json:
                return EnhancedLoginResponse(success=False, error=error_msg)
            else:
                raise HTTPException(status_code=503, detail=error_msg)

        # 3. AUTHENTICATION PHASE
        if not user:
            await auth_service.send_login_error_event(
                error_type="user_not_found",
                username=username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="User not found",
                request_payload=request_payload
            )
            await auth_service.handle_failed_login(username, user, ip_address, user_agent)
            if is_json:
                return EnhancedLoginResponse(success=False, error="Invalid credentials")
            else:
                raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(password, user.hashed_password):
            await auth_service.send_login_error_event(
                error_type="invalid_password",
                username=username,
                customer_id=user.customer_id,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Invalid password",
                request_payload=request_payload
            )
            await auth_service.handle_failed_login(username, user, ip_address, user_agent)
            if is_json:
                return EnhancedLoginResponse(success=False, error="Invalid credentials")
            else:
                raise HTTPException(status_code=401, detail="Invalid credentials")

        # 4. CRASH SIMULATION PHASE (AFTER valid credentials)
        print(f"🔍 TRACE: Crash check - enabled:{crash_enabled}, type:'{crash_type}'")
        if crash_enabled and crash_type:
            print("🔍 TRACE: ✅ EXECUTING crash simulation")
            from ...services.crash_simulator import crash_simulator
            error_message = crash_simulator.simulate_crash(crash_type)
            print(f"🔍 TRACE: ✅ Crash simulation completed: {error_message}")
            print(f"🔍 TRACE: Selected location {selected_location}")

            await auth_service.send_crash_simulator_event(
                crash_type=crash_type,
                username=username,
                customer_id=user.customer_id,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=error_message,
                selected_location=selected_location,
                stack_trace="Simulated crash - no actual exception"
            )

            print("🔍 TRACE: ❌ LOGIN FAILED due to crash simulation")
            error_msg = f"Crash simulation triggered: {error_message}"
            if is_json:
                return EnhancedLoginResponse(success=False, error=error_msg)
            else:
                raise HTTPException(status_code=500, detail=error_msg)

        # 5. LOCATION SECURITY CHECK
        suspicious_activity = None
        if location_enabled and selected_location:
            suspicious_activity, previous_location = location_service.check_suspicious_location(
                username, selected_location
            )

            if suspicious_activity and suspicious_activity.isSuspicious:
                current_location = location_service.get_location_info(selected_location)
                await auth_service.send_location_suspicious_event(
                    username=username,
                    customer_id=user.customer_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    current_location=current_location,
                    previous_location=previous_location,
                    suspicious_activity=suspicious_activity
                )

        # 6. SUCCESS PHASE
        print("🔍 TRACE: ✅ LOGIN SUCCESS")
        await auth_service.handle_successful_login(username, user, ip_address, user_agent, selected_location)

        token = create_access_token({"sub": user.username})

        if is_json:
            response = EnhancedLoginResponse(
                access_token=token,
                success=True
            )
            if suspicious_activity and suspicious_activity.isSuspicious:
                response.suspiciousActivity = suspicious_activity
            return response
        else:
            return {"access_token": token, "token_type": "bearer"}

    except HTTPException:
        # Re-raise HTTPExceptions (like crash simulation errors) without catching them
        raise
    except Exception as e:
        # Catch-all error handler for unexpected errors only
        print(f"🔍 TRACE: ❌ Unexpected error: {e}")
        await auth_service.send_login_error_event(
            error_type="server_error",
            username=username,
            customer_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=str(e),
            error_details={"exception_type": type(e).__name__},
            request_payload=request_payload
        )

        if is_json:
            return EnhancedLoginResponse(success=False, error="Internal server error")
        else:
            raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/otp")
async def sample_otp_user(request: Request,
                          current_user: User = Depends(get_current_user),
                          reason: str = None):
    await AuthService.handle_otp_error(request, current_user, reason)

    return {"status": "success", "message": reason}


@router.post("/auth/otp/advanced")
async def sample_otp_advanced_user(request: Request,
                                   current_user: User = Depends(get_current_user),
                                   reason: str = None):
    await AuthService.handle_otp_advanced_error(request, current_user, reason)

    return {"status": "success", "message": reason}


# Keep the other endpoints unchanged
@router.post("/auth/register", response_model=RegisterResponse)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create new user account."""
    try:
        existing_user = safe_db_query(
            db,
            lambda session: session.query(User).filter(User.username == user.username).first()
        )
    except (OperationalError, DatabaseError, InvalidRequestError) as db_error:
        error_details = get_db_error_details(db_error)
        await auth_service.send_login_error_event(
            error_type="database_error",
            username=user.username,
            customer_id=None,
            ip_address="unknown",
            user_agent="unknown",
            error_message=f"Database connection error during registration: {str(db_error)}",
            error_details=error_details,
            request_payload={"username": user.username, "endpoint": "/auth/register"}
        )
        raise HTTPException(
            status_code=503,
            detail="Database service temporarily unavailable"
        )

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    try:
        last_user = safe_db_query(
            db,
            lambda session: session.query(User).order_by(User.created_at.desc()).first()
        )
    except (OperationalError, DatabaseError, InvalidRequestError) as db_error:
        error_details = get_db_error_details(db_error)
        await auth_service.send_login_error_event(
            error_type="database_error",
            username=user.username,
            customer_id=None,
            ip_address="unknown",
            user_agent="unknown",
            error_message=f"Database connection error during registration: {str(db_error)}",
            error_details=error_details,
            request_payload={"username": user.username, "endpoint": "/auth/register"}
        )
        raise HTTPException(
            status_code=503,
            detail="Database service temporarily unavailable"
        )

    if last_user and last_user.customer_id:
        last_number = int(last_user.customer_id.split("-")[1])
    else:
        last_number = 0

    new_customer_id = f"CUST-{last_number+1:06d}"
    hashed_pw = get_password_hash(user.password)
    hashed_pin = get_pin_hash(user.pin)
    db_user = User(
        username=user.username,
        hashed_password=hashed_pw,
        hashed_pin=hashed_pin,
        customer_id=new_customer_id
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Auto-create default savings account
    default_account = Account(
        user_id=db_user.id,
        account_number=f"ACC{new_customer_id.split('-')[1]}001",
        account_type="savings",
        balance=0.00,
        currency="IDR",
        status="active"
    )

    db.add(default_account)
    db.commit()
    db.refresh(default_account)

    return RegisterResponse(
        user=db_user,
        message="Registration successful! Default savings account created.",
        default_account_number=default_account.account_number
    )


@router.get("/auth/me", response_model=UserWithAccountsResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current authenticated user information with accounts."""
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()

    return UserWithAccountsResponse(
        id=current_user.id,
        username=current_user.username,
        customer_id=current_user.customer_id,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        accounts=accounts
    )


@router.get("/auth/accounts")
def get_current_user_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's accounts."""
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    
    return {
        "user_id": current_user.id,
        "customer_id": current_user.customer_id,
        "username": current_user.username,
        "accounts": [
            {
                "id": str(acc.id),
                "account_number": acc.account_number,
                "account_type": acc.account_type,
                "balance": float(acc.balance),
                "currency": acc.currency,
                "status": acc.status
            }
            for acc in accounts
        ]
    }


@router.get("/auth/histories")
def get_current_user_histories(current_user: User = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    histories = (db.query(TransactionHistory)
                 .filter(TransactionHistory.user_id == current_user.id)
                 .order_by(desc(TransactionHistory.created_at))
                 .all())

    return [{
        "transaction_id": str(his.id),
        "transaction_date": his.created_at,
        "transaction_type": his.transaction_type,
        "amount": his.amount,
        "currency": his.currency,
        "status": his.status,
        "description": his.description,
        "recipient_name": his.recipient_name,
        "recipient_number": his.recipient_account,
    } for his in histories]


@router.get("/auth/account-list")
def get_account_list(current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    accounts = (db.query(Account.account_number, User.username)
                .join(User, Account.user_id == User.id)
                .all())

    return [{
        "username": username,
        "account_number": account_number
    } for account_number, username in accounts]


@router.post("/auth/create-default-account")
def create_default_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create default account for user if they don't have any."""
    existing_accounts = db.query(Account).filter(Account.user_id == current_user.id).count()
    
    if existing_accounts > 0:
        raise HTTPException(
            status_code=400, 
            detail="User already has accounts"
        )
    
    # Create default savings account
    account_number = f"ACC{current_user.customer_id.split('-')[1]}001"
    default_account = Account(
        user_id=current_user.id,
        account_number=account_number,
        account_type="savings",
        balance=0.00,
        currency="IDR",
        status="active"
    )
    
    db.add(default_account)
    db.commit()
    db.refresh(default_account)
    
    return {
        "message": "Default account created successfully",
        "account": {
            "id": str(default_account.id),
            "account_number": default_account.account_number,
            "account_type": default_account.account_type,
            "balance": float(default_account.balance),
            "currency": default_account.currency,
            "status": default_account.status
        }
    }


@router.post("/auth/validate-pin", response_model=PINValidationResponse)
async def validate_pin(
    pin_data: PINValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate user PIN."""
    if verify_pin(pin_data.pin, current_user.hashed_pin):
        return PINValidationResponse(valid=True, message="PIN is valid")
    else:
        return PINValidationResponse(valid=False, message="Invalid PIN")