from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...auth import get_current_user
from ...models import User, Account
from ...schemas import UserCreate, UserResponse, RegisterResponse, PINValidationRequest, PINValidationResponse
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


@router.get("/auth/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return current_user


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