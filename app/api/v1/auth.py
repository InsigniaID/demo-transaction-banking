from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ...api.deps import get_db
from ...auth import get_current_user
from ...models import User, Account, TransactionHistory
from ...schemas import UserCreate, UserResponse, UserWithAccountsResponse, RegisterResponse, PINValidationRequest, PINValidationResponse
from ...security import get_password_hash, get_pin_hash, verify_password, verify_pin, create_access_token
from ...services.auth_service import auth_service

router = APIRouter()


@router.post("/auth/register", response_model=RegisterResponse)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create new user account."""
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
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """User login endpoint."""
    user = db.query(User).filter(User.username == form_data.username).first()
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    if not user or not verify_password(form_data.password, user.hashed_password):
        await auth_service.handle_failed_login(
            form_data.username, user, ip_address, user_agent
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await auth_service.handle_successful_login(
        form_data.username, user, ip_address, user_agent
    )

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


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