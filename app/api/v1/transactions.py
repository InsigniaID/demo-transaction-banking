from fastapi import APIRouter, Depends, Request, Body
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...auth import get_current_user
from ...models import User
from ...schemas import (
    GenerateQRISRequest, GenerateQRISResponse,
    ConsumeQRISRequest, ConsumeQRISResponse,
    TransactionCorporateInput, FraudDataLegitimate
)
from ...services.qris_service import QRISService
from ...services.transaction_service import TransactionService
from ...services.enhanced_transaction_service import EnhancedTransactionService
from ...services.pin_validation_service import pin_validation_service

router = APIRouter()


@router.post("/retail/qris-generate", response_model=GenerateQRISResponse)
async def create_retail_transaction_gen(
    data: GenerateQRISRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Generate QRIS code for retail transaction."""
    # Validate PIN first
    await pin_validation_service.validate_pin_or_fail(
        current_user, 
        data.pin, 
        "qris_generate",
        data.amount,
        {"account_number": data.account_number, "merchant_name": data.merchant_name}
    )
    
    return QRISService.generate_qris(data, current_user.customer_id)


@router.post("/retail/qris-consume", response_model=ConsumeQRISResponse)
async def create_retail_transaction_consume(
    data: ConsumeQRISRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Consume QRIS code for retail transaction."""
    qris_data, qris_id = QRISService.validate_and_consume_qris(data, current_user.customer_id)
    
    # Validate PIN before processing payment
    await pin_validation_service.validate_pin_or_fail(
        current_user, 
        data.pin, 
        "qris_consume",
        qris_data["amount"],
        {"account_number": data.account_number, "qris_id": qris_id, "merchant_name": qris_data["merchant_name"]}
    )
    
    transaction_data = await EnhancedTransactionService.create_enhanced_retail_transaction_data(
        qris_data, current_user.customer_id, data.account_number
    )
    
    await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)
    
    return ConsumeQRISResponse(
        qris_id=qris_id,
        status="SUCCESS",
        message=f"Payment of {qris_data['amount']} {qris_data['currency']} to {qris_data['merchant_name']} completed."
    )


@router.post("/corporate")
async def create_corporate_transaction(
    request: Request,
    tx: TransactionCorporateInput = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Process corporate transaction."""
    # Validate PIN first
    await pin_validation_service.validate_pin_or_fail(
        current_user, 
        tx.pin, 
        "corporate_transaction",
        tx.amount,
        {
            "account_number": tx.account_number, 
            "transaction_type": tx.transaction_type,
            "merchant_name": tx.merchant_name
        }
    )
    
    tx_dict = tx.model_dump()
    
    transaction_data = await EnhancedTransactionService.create_enhanced_corporate_transaction_data(
        tx_dict, current_user.customer_id, dict(request.headers), request.client.host
    )
    
    await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)
    
    return {"status": "success", "transaction": transaction_data}


@router.post("/velocity-violation")
async def create_velocity_violation(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report velocity violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@router.post("/compliance-violation/aml-reporting")
async def create_aml_reporting(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report AML compliance violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@router.post("/compliance-violation/kyc-gap")
async def create_kyc_gap(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report KYC gap violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}