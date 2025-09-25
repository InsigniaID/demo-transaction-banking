from fastapi import APIRouter, Depends, HTTPException, Request

from ...auth import get_current_user
from ...models import User
from ...services.infra_service import InfraServices

router = APIRouter()


@router.post("/server")
async def sample_server(request: Request,
                        current_user: User = Depends(get_current_user)):
    InfraServices.infra_service_cpu(request, current_user)

    return {"status": "success", "message": "cpu spike"}


@router.post("/driver")
async def sample_server(request: Request,
                        current_user: User = Depends(get_current_user)):
    InfraServices.infra_service_driver(request, current_user)

    return {"status": "success", "message": "server crash"}


@router.post("/security/sqli")
async def sample_server(request: Request,
                        current_user: User = Depends(get_current_user)):
    InfraServices.data_security(request, current_user)

    return {"status": "success", "message": "SQL injection"}


@router.post("/security/brute-force")
async def sample_server(request: Request,
                        current_user: User = Depends(get_current_user)):
    InfraServices.data_security_brute_force(request, current_user)

    return {"status": "success", "message": "brute force"}


@router.post("/security/ddos")
async def sample_server(request: Request,
                        current_user: User = Depends(get_current_user)):
    InfraServices.data_security_ddos(request, current_user)

    return {"status": "success", "message": "ddos"}
