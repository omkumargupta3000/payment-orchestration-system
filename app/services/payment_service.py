"""
The core orchestrator. This ties together idempotency checking, PSP routing,
simulated PSP calls, and retries.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.transaction import Transaction
from app.schemas.payment import PaymentCreateRequest
from app.services import routing_service, psp_service

MAX_RETRIES = 2


def create_payment(db: Session, payload: PaymentCreateRequest) -> Transaction:
    # --- 1. idempotency check -------------------------------------------------
    # If a transaction already exists with this idempotency key, we return it
    # as-is instead of processing the payment again. This is what stops a
    # network retry / accidental double-click from charging the customer twice.
    existing = (
        db.query(Transaction)
        .filter(Transaction.idempotency_key == payload.idempotency_key)
        .first()
    )
    if existing:
        return existing

    # --- 2. create the transaction in CREATED state ---------------------------
    transaction = Transaction(
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method=payload.payment_method,
        idempotency_key=payload.idempotency_key,
        status="CREATED",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # --- 3. process the payment (routing + simulated PSP calls + retries) -----
    _process_transaction(db, transaction)

    return transaction


def _process_transaction(db: Session, transaction: Transaction) -> None:
    """
    Moves a transaction through PROCESSING -> SUCCESS / FAILED, retrying with
    a different PSP on failure, up to MAX_RETRIES times.
    """
    attempted = []
    total_latency = 0

    transaction.status = "PROCESSING"
    db.commit()

    attempt_number = 0
    while attempt_number <= MAX_RETRIES:
        psp = routing_service.select_psp(db, exclude_names=attempted)

        if psp is None:
            # no more PSPs available to try - stop here
            transaction.status = "FAILED"
            transaction.attempted_psps = ",".join(attempted)
            transaction.processing_time_ms = total_latency
            db.commit()
            return

        result = psp_service.call_psp(psp.name, psp.success_rate, psp.avg_latency_ms)
        attempted.append(psp.name)
        total_latency += result["latency_ms"]

        if result["success"]:
            transaction.status = "SUCCESS"
            transaction.selected_psp = psp.name
            transaction.attempted_psps = ",".join(attempted)
            transaction.retry_count = attempt_number
            transaction.processing_time_ms = total_latency
            db.commit()
            return

        # this attempt failed - decide whether to retry
        attempt_number += 1
        if attempt_number <= MAX_RETRIES:
            transaction.status = "RETRYING"
            db.commit()

    # ran out of retries
    transaction.status = "FAILED"
    transaction.attempted_psps = ",".join(attempted)
    transaction.retry_count = attempt_number - 1
    transaction.processing_time_ms = total_latency
    db.commit()


def get_transaction_by_idempotency_key(db: Session, idempotency_key: str):
    return (
        db.query(Transaction)
        .filter(Transaction.idempotency_key == idempotency_key)
        .first()
    )


def get_transaction(db: Session, transaction_id: str) -> Transaction:
    transaction = (
        db.query(Transaction)
        .filter(Transaction.transaction_id == transaction_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def list_transactions(db: Session, status: str = None, psp: str = None, limit: int = 100):
    query = db.query(Transaction)

    if status:
        query = query.filter(Transaction.status == status.upper())
    if psp:
        query = query.filter(Transaction.selected_psp == psp)

    return query.order_by(Transaction.created_at.desc()).limit(limit).all()
