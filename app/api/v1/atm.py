import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from decouple import config

from ...auth import get_current_user
from ...models import User
from ...services.atm_service import ATMServices

router = APIRouter()
OWNER = "InsigniaID"
REPO = "msft-ticket-serv-trx"
GITHUB_API = f"https://api.github.com/repos/{OWNER}/{REPO}/issues"

GITHUB_TOKEN = config("GH_PAT")


@router.post("/insufficient")
async def sample_insufficient_balance(request: Request,
                                      amount: int,
                                      pin: str,
                                      current_user: User = Depends(get_current_user)):
    result = ATMServices.atm_service(request, amount, pin, current_user)

    return result


class Issue(BaseModel):
    title: str
    body: str = None
    labels: list[str] = []


@router.post("/create-issue")
def create_issue(issue: Issue):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=500, detail="Missing GitHub token")

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    payload = {
        "title": issue.title,
        "body": issue.body,
        "labels": issue.labels
    }

    response = requests.post(GITHUB_API, headers=headers, json=payload)

    if response.status_code == 201:
        return {"message": "Issue created successfully", "issue": response.json()}
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())