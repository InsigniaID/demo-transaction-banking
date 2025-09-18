from fastapi import APIRouter, Depends, HTTPException, Request

from ...auth import get_current_user
from ...models import User
from ...services.infra_service import InfraServices

router = APIRouter()


@router.post("/server")
async def sample_server(request: Request,
                        current_user: User = Depends(get_current_user)):
    InfraServices.infra_service(request, current_user)

    return {"status": "success", "message": "server error"}


