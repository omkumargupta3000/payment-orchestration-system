from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.payment import PaymentCreateRequest, PaymentResponse
from app.services import payment_service

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("", response_model=PaymentResponse)
def create_payment(payload: PaymentCreateRequest, db: Session = Depends(get_db)):
    try:
        transaction = payment_service.create_payment(db, payload)
    except IntegrityError:
        # extremely unlikely race condition on idempotency_key uniqueness -
        # roll back and re-fetch the row that won the race
        db.rollback()
        transaction = payment_service.get_transaction_by_idempotency_key(
            db, payload.idempotency_key
        )
        if transaction is None:
            raise HTTPException(status_code=500, detail="Could not process payment")

    return transaction


@router.get("", response_model=list[PaymentResponse])
def list_payments(
    status: Optional[str] = Query(default=None),
    psp: Optional[str] = Query(default=None),
    transaction_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    if transaction_id:
        transaction = payment_service.get_transaction(db, transaction_id)
        return [transaction]

    return payment_service.list_transactions(db, status=status, psp=psp)


@router.get("/{transaction_id}", response_model=PaymentResponse)
def get_payment(transaction_id: str, db: Session = Depends(get_db)):
    return payment_service.get_transaction(db, transaction_id)
