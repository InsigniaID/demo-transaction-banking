from fastapi import APIRouter, Depends, HTTPException, Request

from ...auth import get_current_user
from ...models import User
from ...services.atm_service import ATMServices

router = APIRouter()


@router.post("/insufficient")
async def sample_insufficient_balance(request: Request,
                                      current_user: User = Depends(get_current_user)):
    ATMServices.atm_service(request, current_user)

    return {"status": "success", "message": "atm machine is insufficient saldo"}