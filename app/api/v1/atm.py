from fastapi import APIRouter, Depends, HTTPException, Request

from ...auth import get_current_user
from ...models import User
from ...services.atm_service import ATMServices

router = APIRouter()


@router.post("/insufficient")
async def sample_insufficient_balance(request: Request,
                                      amount: int,
                                      current_user: User = Depends(get_current_user)):
    result = ATMServices.atm_service(request, current_user, amount)

    return result


@router.post("/insufficient")
async def sample():
    pass