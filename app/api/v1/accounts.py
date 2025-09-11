from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from decimal import Decimal
import uuid

from ...api.deps import get_db
from ...auth import get_current_user
from ...models import User, Account, TransactionHistory
from ...schemas import (
    AccountResponse, TransactionHistoryResponse, 
    AccountBalanceResponse, CreateAccountRequest
)

router = APIRouter()


@router.get("/accounts", response_model=List[AccountResponse])
async def get_user_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all accounts for current user."""
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    return accounts


@router.post("/accounts", response_model=AccountResponse)
async def create_account(
    account_data: CreateAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new account for user."""
    # Generate unique account number
    account_number = f"ACC{current_user.customer_id.split('-')[1]}{len(current_user.accounts) + 1:03d}"
    
    account = Account(
        user_id=current_user.id,
        account_number=account_number,
        account_type=account_data.account_type,
        balance=account_data.initial_balance
    )
    
    db.add(account)
    db.commit()
    db.refresh(account)
    
    return account


@router.get("/accounts/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get account balance."""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user.id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return AccountBalanceResponse(
        account_number=account.account_number,
        balance=account.balance,
        currency=account.currency,
        account_type=account.account_type,
        status=account.status
    )


@router.get("/accounts/{account_id}/transactions", response_model=List[TransactionHistoryResponse])
async def get_account_transactions(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip")
):
    """Get transaction history for specific account."""
    # Verify account belongs to user
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user.id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    transactions = db.query(TransactionHistory).filter(
        TransactionHistory.account_id == account_id
    ).order_by(
        TransactionHistory.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return transactions


@router.get("/transactions", response_model=List[TransactionHistoryResponse])
async def get_user_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip"),
    transaction_type: str = Query(None, description="Filter by transaction type")
):
    """Get all transaction history for current user."""
    query = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id
    )
    
    if transaction_type:
        query = query.filter(TransactionHistory.transaction_type == transaction_type)
    
    transactions = query.order_by(
        TransactionHistory.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return transactions


@router.get("/transactions/{transaction_id}", response_model=TransactionHistoryResponse)
async def get_transaction_detail(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific transaction detail."""
    transaction = db.query(TransactionHistory).filter(
        TransactionHistory.transaction_id == transaction_id,
        TransactionHistory.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return transaction