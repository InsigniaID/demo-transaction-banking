from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2, OAuth2PasswordBearer
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel, OAuthFlowPassword
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from . import models, database, security

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class OAuth2PasswordRequestFormForSwagger(OAuth2):
    def __init__(self, tokenUrl: str):
        flows = OAuthFlowsModel(password=OAuthFlowPassword(tokenUrl=tokenUrl))
        super().__init__(flows=flows, scheme_name="OAuth2Password")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def authenticate_user(db: Session, username: str, password: str, request: Request):
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user or not pwd_context.verify(password, user.hashed_password):
        failed = models.FailedLogin(username=username,
                                    ip_address=request.client.host,
                                    user_agent=request.headers.get("user-agent", "unknown"),
                                    failure_reason="invalid_password" if user else "user_not_found")

        db.add(failed)
        db.commit()

        return None

    return user


def get_current_user(token: str = Depends(oauth2_scheme)):
    print(f"Received token: {token}")

    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials",
                                          headers={"WWW-Authenticate": "Bearer"})

    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        print(f"Decoded payload: {payload}")
        username: str = payload.get("sub")
        print(f"Username from token: {username}")

        if username is None:
            print("Username is None!")
            raise credentials_exception

    except JWTError as e:
        print(f"JWT Error: {e}")
        raise credentials_exception

    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        print(f"User found: {user}")

        if user is None:
            print("User not found in database!")
            raise credentials_exception

        return user
    finally:
        db.close()
