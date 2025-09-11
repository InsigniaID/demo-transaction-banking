from fastapi import APIRouter

from .auth import router as auth_router
from .transactions import router as transaction_router

api_router = APIRouter()

api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(transaction_router, prefix="/transaction", tags=["transactions"])