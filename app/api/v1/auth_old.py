from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DatabaseError, InvalidRequestError

from ...api.deps import get_db
from ...auth import get_current_user
from ...models import User, Account
from ...schemas import (
    UserCreate, UserResponse, UserWithAccountsResponse, RegisterResponse,
    PINValidationRequest, PINValidationResponse, EnhancedLoginRequest,
    EnhancedLoginResponse, SuspiciousActivity
)
from ...security import get_password_hash, get_pin_hash, verify_password, verify_pin, create_access_token
from ...services.auth_service import auth_service
from ...services.location_service import location_service
from ...database_utils import safe_db_query, get_db_error_details

router = APIRouter()


@router.post("/auth/register", response_model=RegisterResponse)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create new user account."""
    try:
        existing_user = safe_db_query(
            db,
            lambda session: session.query(User).filter(User.username == user.username).first()
        )
    except (OperationalError, DatabaseError) as db_error:
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
    except (OperationalError, DatabaseError) as db_error:
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


@router.post("/users/", response_model=UserResponse)
async def create_user_legacy(user: UserCreate, db: Session = Depends(get_db)):
    """Legacy endpoint for user creation (backward compatibility)."""
    # Reuse the registration logic but return only user data
    existing_user = db.query(User).filter(User.username == user.username).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    last_user = db.query(User).order_by(User.created_at.desc()).first()

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

    return db_user


@router.post("/auth/login")
async def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    enhanced_data: EnhancedLoginRequest = None
):
    """Enhanced user login endpoint supporting both form data and JSON."""
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    # Determine if this is JSON request or form data
    content_type = request.headers.get("content-type", "")
    is_json_request = "application/json" in content_type

    # Parse login data from appropriate source
    if is_json_request and enhanced_data:
        # JSON request with enhanced features
        login_data = enhanced_data
        request_payload = enhanced_data.model_dump()
        print("🔍 TRACE: JSON request detected with enhanced features")
    else:
        # Form data request (OAuth2 compatible)
        login_data = EnhancedLoginRequest(
            username=form_data.username,
            password=form_data.password,
            locationDetectionEnabled=False,
            selectedLocation="",
            crashSimulatorEnabled=False,
            crashType="",
            databaseErrorSimulationEnabled=False
        )
        request_payload = {"username": form_data.username, "endpoint": "/auth/login"}
        print("🔍 TRACE: Form data request detected")

    print(f"🔍 TRACE: Login request for user '{login_data.username}'")
    print(f"🔍 TRACE: Enhanced features - Location: {login_data.locationDetectionEnabled}, Crash: {login_data.crashSimulatorEnabled}")

    try:
        # Pre-validation handling (crash simulation, location checks)
        enhancement_result = await auth_service.handle_enhanced_login_attempt(
            username=login_data.username,
            password=login_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
            location_detection_enabled=login_data.locationDetectionEnabled,
            selected_location=login_data.selectedLocation,
            crash_simulator_enabled=login_data.crashSimulatorEnabled,
            crash_type=login_data.crashType,
            request_payload=request_payload
        )

        # Validate location if enabled
        if login_data.locationDetectionEnabled and login_data.selectedLocation:
            if not location_service.get_location_info(login_data.selectedLocation):
                await auth_service.send_login_error_event(
                    error_type="invalid_location",
                    username=login_data.username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=f"Invalid location: {login_data.selectedLocation}",
                    error_details={"available_locations": list(location_service.location_data.keys())},
                    request_payload=request_payload
                )
                if is_json_request:
                    return EnhancedLoginResponse(success=False, error="Invalid location")
                else:
                    raise HTTPException(status_code=400, detail="Invalid location")

        # Validate crash type if enabled
        print(f"🔍 TRACE: crashSimulatorEnabled = {login_data.crashSimulatorEnabled}")
        print(f"🔍 TRACE: crashType = '{login_data.crashType}'")

        if login_data.crashSimulatorEnabled:
            print("🔍 TRACE: Entering crash simulator validation block")

            if not login_data.crashType:
                print("🔍 TRACE: No crash type specified - returning error")
                await auth_service.send_login_error_event(
                    error_type="missing_crash_type",
                    username=login_data.username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message="Crash simulator enabled but no crash type specified",
                    request_payload=request_payload
                )
                if is_json_request:
                    return EnhancedLoginResponse(success=False, error="Crash simulator enabled but no crash type specified")
                else:
                    raise HTTPException(status_code=400, detail="Crash simulator enabled but no crash type specified")

            valid_crash_types = ["runtime", "memory", "infinite-loop", "network", "state"]
            if login_data.crashType not in valid_crash_types:
                print(f"🔍 TRACE: Invalid crash type '{login_data.crashType}' - returning error")
                await auth_service.send_login_error_event(
                    error_type="invalid_crash_type",
                    username=login_data.username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=f"Invalid crash type: {login_data.crashType}",
                    error_details={"available_crash_types": valid_crash_types},
                    request_payload=request_payload
                )
                if is_json_request:
                    return EnhancedLoginResponse(success=False, error=f"Invalid crash type: {login_data.crashType}")
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid crash type: {login_data.crashType}")

            print(f"🔍 TRACE: Crash type '{login_data.crashType}' is valid - continuing")
        else:
            print("🔍 TRACE: Crash simulator NOT enabled - skipping validation")

        # Database error simulation if enabled
        if login_data.databaseErrorSimulationEnabled:
            await auth_service.send_login_error_event(
                error_type="database_error_simulation",
                username=login_data.username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Simulated database error for testing",
                error_details={"simulation": True, "error_type": "connection_timeout"},
                request_payload=request_payload
            )
            if is_json_request:
                return EnhancedLoginResponse(success=False, error="Database service temporarily unavailable (simulated)")
            else:
                raise HTTPException(status_code=503, detail="Database service temporarily unavailable (simulated)")

        # Database query with error handling and retries
        try:
            user = safe_db_query(
                db,
                lambda session: session.query(User).filter(User.username == login_data.username).first()
            )
        except (OperationalError, DatabaseError, InvalidRequestError) as db_error:
            error_details = get_db_error_details(db_error)
            await auth_service.send_login_error_event(
                error_type="database_error",
                username=login_data.username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=f"Database connection error after retries: {str(db_error)}",
                error_details=error_details,
                request_payload=request_payload
            )
            if is_json_request:
                return EnhancedLoginResponse(success=False, error="Database service temporarily unavailable")
            else:
                raise HTTPException(status_code=503, detail="Database service temporarily unavailable")

        if not user:
            await auth_service.send_login_error_event(
                error_type="user_not_found",
                username=login_data.username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="User not found",
                request_payload=request_payload
            )
            await auth_service.handle_failed_login(
                login_data.username, user, ip_address, user_agent
            )
            if is_json_request:
                return EnhancedLoginResponse(success=False, error="Invalid credentials")
            else:
                raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(login_data.password, user.hashed_password):
            await auth_service.send_login_error_event(
                error_type="invalid_password",
                username=login_data.username,
                customer_id=user.customer_id,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Invalid password",
                request_payload=request_payload
            )
            await auth_service.handle_failed_login(
                login_data.username, user, ip_address, user_agent
            )
            if is_json_request:
                return EnhancedLoginResponse(success=False, error="Invalid credentials")
            else:
                raise HTTPException(status_code=401, detail="Invalid credentials")

        # Execute crash simulation AFTER successful credential validation
        print(f"🔍 TRACE: About to check crash simulator execution")
        print(f"🔍 TRACE: crashSimulatorEnabled = {login_data.crashSimulatorEnabled}")
        print(f"🔍 TRACE: crashType = '{login_data.crashType}'")
        print(f"🔍 TRACE: Condition result = {login_data.crashSimulatorEnabled and login_data.crashType}")

        if login_data.crashSimulatorEnabled and login_data.crashType:
            print("🔍 TRACE: ✅ ENTERING crash simulation execution block")
            try:
                from ...services.crash_simulator import crash_simulator
                print(f"🔍 TRACE: About to call crash_simulator.simulate_crash('{login_data.crashType}')")
                crash_simulator.simulate_crash(login_data.crashType)
                print("🔍 TRACE: ⚠️ Crash simulation completed WITHOUT exception")
                error_message = f"Crash simulation completed without exception for type: {login_data.crashType}"
                stack_trace = "No exception thrown"
            except Exception as crash_error:
                print(f"🔍 TRACE: ✅ Crash simulation threw exception: {crash_error}")
                error_message = str(crash_error)
                stack_trace = crash_simulator.get_stack_trace()

            print(f"🔍 TRACE: About to send crash event to Kafka")
            await auth_service.send_crash_simulator_event(
                crash_type=login_data.crashType,
                username=login_data.username,
                customer_id=user.customer_id,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=error_message,
                stack_trace=stack_trace
            )

            print(f"🔍 TRACE: ❌ RETURNING ERROR - Login should FAIL due to crash simulation")
            if is_json_request:
                return EnhancedLoginResponse(success=False, error=f"Crash simulation triggered: {error_message}")
            else:
                raise HTTPException(status_code=500, detail=f"Crash simulation triggered: {error_message}")
        else:
            print("🔍 TRACE: ⏭️ SKIPPING crash simulation execution - condition not met")

        # Send location suspicious activity event if detected
        suspicious_activity = enhancement_result.get("suspicious_activity")
        if suspicious_activity and suspicious_activity.isSuspicious:
            current_location = location_service.get_location_info(login_data.selectedLocation)
            _, previous_location = location_service.check_suspicious_location(
                login_data.username, login_data.selectedLocation
            )

            await auth_service.send_location_suspicious_event(
                username=login_data.username,
                customer_id=user.customer_id,
                ip_address=ip_address,
                user_agent=user_agent,
                current_location=current_location,
                previous_location=previous_location,
                suspicious_activity=suspicious_activity
            )

        # Successful login
        print("🔍 TRACE: ✅ Reached successful login section")
        print(f"🔍 TRACE: Final check - crashSimulatorEnabled = {login_data.crashSimulatorEnabled}")

        await auth_service.handle_successful_login(
            login_data.username, user, ip_address, user_agent
        )

        token = create_access_token({"sub": user.username})

        print("🔍 TRACE: ✅ RETURNING SUCCESS RESPONSE")
        if is_json_request:
            response = EnhancedLoginResponse(
                access_token=token,
                success=True
            )
            if suspicious_activity and suspicious_activity.isSuspicious:
                response.suspiciousActivity = suspicious_activity
            print(f"🔍 TRACE: JSON Response success = {response.success}")
            return response
        else:
            print("🔍 TRACE: Form data response success = True")
            return {"access_token": token, "token_type": "bearer"}

    except ValueError as ve:
        await auth_service.send_login_error_event(
            error_type="validation_error",
            username=login_data.username,
            customer_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=str(ve),
            error_details={"exception_type": "ValueError"},
            request_payload=request_payload
        )
        if is_json_request:
            return EnhancedLoginResponse(success=False, error=str(ve))
        else:
            raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        error_message = str(e)
        error_type = "crash_simulation" if "Simulated" in error_message else "server_error"

        await auth_service.send_login_error_event(
            error_type=error_type,
            username=login_data.username,
            customer_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message,
            error_details={"exception_type": type(e).__name__},
            request_payload=request_payload
        )

        if is_json_request:
            return EnhancedLoginResponse(
                success=False,
                error="Internal server error" if error_type == "server_error" else error_message
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Internal server error" if error_type == "server_error" else error_message
            )


@router.get("/auth/me", response_model=UserWithAccountsResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current authenticated user information with accounts."""
    # Get user's accounts
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    
    # Create response with accounts
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


@router.post("/auth/enhanced-login", response_model=EnhancedLoginResponse)
async def enhanced_login(
    request: Request,
    login_data: EnhancedLoginRequest,
    db: Session = Depends(get_db)
):
    """Enhanced login endpoint with location tracking and crash simulation."""
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")
    request_payload = login_data.model_dump()

    try:
        # Pre-validation handling (crash simulation, location checks)
        enhancement_result = await auth_service.handle_enhanced_login_attempt(
            username=login_data.username,
            password=login_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
            location_detection_enabled=login_data.locationDetectionEnabled,
            selected_location=login_data.selectedLocation,
            crash_simulator_enabled=login_data.crashSimulatorEnabled,
            crash_type=login_data.crashType,
            request_payload=request_payload
        )

        # Validate location if enabled
        if login_data.locationDetectionEnabled and login_data.selectedLocation:
            if not location_service.get_location_info(login_data.selectedLocation):
                await auth_service.send_login_error_event(
                    error_type="invalid_location",
                    username=login_data.username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=f"Invalid location: {login_data.selectedLocation}",
                    error_details={"available_locations": list(location_service.location_data.keys())},
                    request_payload=request_payload
                )
                return EnhancedLoginResponse(
                    success=False,
                    error="Invalid location"
                )

        # Validate crash type if enabled
        print(f"🔍 TRACE: crashSimulatorEnabled = {login_data.crashSimulatorEnabled}")
        print(f"🔍 TRACE: crashType = '{login_data.crashType}'")

        if login_data.crashSimulatorEnabled:
            print("🔍 TRACE: Entering crash simulator validation block")

            if not login_data.crashType:
                print("🔍 TRACE: No crash type specified - returning error")
                await auth_service.send_login_error_event(
                    error_type="missing_crash_type",
                    username=login_data.username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message="Crash simulator enabled but no crash type specified",
                    request_payload=request_payload
                )
                return EnhancedLoginResponse(
                    success=False,
                    error="Crash simulator enabled but no crash type specified"
                )

            valid_crash_types = ["runtime", "memory", "infinite-loop", "network", "state"]
            if login_data.crashType not in valid_crash_types:
                print(f"🔍 TRACE: Invalid crash type '{login_data.crashType}' - returning error")
                await auth_service.send_login_error_event(
                    error_type="invalid_crash_type",
                    username=login_data.username,
                    customer_id=None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message=f"Invalid crash type: {login_data.crashType}",
                    error_details={"available_crash_types": valid_crash_types},
                    request_payload=request_payload
                )
                return EnhancedLoginResponse(
                    success=False,
                    error=f"Invalid crash type: {login_data.crashType}"
                )

            print(f"🔍 TRACE: Crash type '{login_data.crashType}' is valid - continuing")
        else:
            print("🔍 TRACE: Crash simulator NOT enabled - skipping validation")

        # Database error simulation if enabled
        if login_data.databaseErrorSimulationEnabled:
            await auth_service.send_login_error_event(
                error_type="database_error_simulation",
                username=login_data.username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Simulated database error for testing",
                error_details={"simulation": True, "error_type": "connection_timeout"},
                request_payload=request_payload
            )
            return EnhancedLoginResponse(
                success=False,
                error="Database service temporarily unavailable (simulated)"
            )

        # Standard user authentication with database error handling and retries
        try:
            user = safe_db_query(
                db,
                lambda session: session.query(User).filter(User.username == login_data.username).first()
            )
        except (OperationalError, DatabaseError) as db_error:
            error_details = get_db_error_details(db_error)
            await auth_service.send_login_error_event(
                error_type="database_error",
                username=login_data.username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=f"Database connection error after retries: {str(db_error)}",
                error_details=error_details,
                request_payload=request_payload
            )
            return EnhancedLoginResponse(
                success=False,
                error="Database service temporarily unavailable"
            )

        if not user:
            await auth_service.send_login_error_event(
                error_type="user_not_found",
                username=login_data.username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="User not found",
                request_payload=request_payload
            )
            await auth_service.handle_failed_login(
                login_data.username, user, ip_address, user_agent
            )
            return EnhancedLoginResponse(
                success=False,
                error="Invalid credentials"
            )

        if not verify_password(login_data.password, user.hashed_password):
            await auth_service.send_login_error_event(
                error_type="invalid_password",
                username=login_data.username,
                customer_id=user.customer_id,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Invalid password",
                request_payload=request_payload
            )
            await auth_service.handle_failed_login(
                login_data.username, user, ip_address, user_agent
            )
            return EnhancedLoginResponse(
                success=False,
                error="Invalid credentials"
            )

        # Execute crash simulation AFTER successful credential validation
        # This ensures crash happens even with valid credentials
        print(f"🔍 TRACE: About to check crash simulator execution")
        print(f"🔍 TRACE: crashSimulatorEnabled = {login_data.crashSimulatorEnabled}")
        print(f"🔍 TRACE: crashType = '{login_data.crashType}'")
        print(f"🔍 TRACE: Condition result = {login_data.crashSimulatorEnabled and login_data.crashType}")

        if login_data.crashSimulatorEnabled and login_data.crashType:
            print("🔍 TRACE: ✅ ENTERING crash simulation execution block")
            try:
                from ...services.crash_simulator import crash_simulator
                print(f"🔍 TRACE: About to call crash_simulator.simulate_crash('{login_data.crashType}')")
                crash_simulator.simulate_crash(login_data.crashType)
                # If we reach here, crash simulation didn't throw an exception
                # But we still want login to fail when crash simulation is enabled
                print("🔍 TRACE: ⚠️ Crash simulation completed WITHOUT exception")
                error_message = f"Crash simulation completed without exception for type: {login_data.crashType}"
                stack_trace = "No exception thrown"
            except Exception as crash_error:
                print(f"🔍 TRACE: ✅ Crash simulation threw exception: {crash_error}")
                error_message = str(crash_error)
                stack_trace = crash_simulator.get_stack_trace()

            print(f"🔍 TRACE: About to send crash event to Kafka")
            # Always send crash event and fail login when crash simulation is enabled
            await auth_service.send_crash_simulator_event(
                crash_type=login_data.crashType,
                username=login_data.username,
                customer_id=user.customer_id,  # Now we have user info
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=error_message,
                stack_trace=stack_trace
            )

            print(f"🔍 TRACE: ❌ RETURNING ERROR - Login should FAIL due to crash simulation")
            # ALWAYS return error when crash simulation is enabled
            return EnhancedLoginResponse(
                success=False,
                error=f"Crash simulation triggered: {error_message}"
            )
        else:
            print("🔍 TRACE: ⏭️ SKIPPING crash simulation execution - condition not met")

        # Send location suspicious activity event if detected
        suspicious_activity = enhancement_result.get("suspicious_activity")
        if suspicious_activity and suspicious_activity.isSuspicious:
            current_location = location_service.get_location_info(login_data.selectedLocation)
            # Get previous location from location service
            _, previous_location = location_service.check_suspicious_location(
                login_data.username, login_data.selectedLocation
            )

            await auth_service.send_location_suspicious_event(
                username=login_data.username,
                customer_id=user.customer_id,
                ip_address=ip_address,
                user_agent=user_agent,
                current_location=current_location,
                previous_location=previous_location,
                suspicious_activity=suspicious_activity
            )

        # Successful login (only if no crash simulation enabled)
        print("🔍 TRACE: ✅ Reached successful login section")
        print(f"🔍 TRACE: Final check - crashSimulatorEnabled = {login_data.crashSimulatorEnabled}")

        await auth_service.handle_successful_login(
            login_data.username, user, ip_address, user_agent
        )

        token = create_access_token({"sub": user.username})

        response = EnhancedLoginResponse(
            access_token=token,
            success=True
        )

        # Add suspicious activity info if present
        if suspicious_activity and suspicious_activity.isSuspicious:
            response.suspiciousActivity = suspicious_activity

        print("🔍 TRACE: ✅ RETURNING SUCCESS RESPONSE")
        print(f"🔍 TRACE: Response success = {response.success}")
        return response

    except ValueError as ve:
        # Handle validation errors
        await auth_service.send_login_error_event(
            error_type="validation_error",
            username=login_data.username,
            customer_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=str(ve),
            error_details={"exception_type": "ValueError"},
            request_payload=request_payload
        )
        return EnhancedLoginResponse(
            success=False,
            error=str(ve)
        )

    except Exception as e:
        # Handle all other errors (including crash simulation)
        error_message = str(e)
        error_type = "crash_simulation" if "Simulated" in error_message else "server_error"

        await auth_service.send_login_error_event(
            error_type=error_type,
            username=login_data.username,
            customer_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message,
            error_details={"exception_type": type(e).__name__},
            request_payload=request_payload
        )

        return EnhancedLoginResponse(
            success=False,
            error="Internal server error" if error_type == "server_error" else error_message
        )