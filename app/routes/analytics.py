from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transaction import Transaction
from app.models.psp import PSP

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    total = db.query(func.count(Transaction.id)).scalar() or 0
    successful = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.status == "SUCCESS")
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.status == "FAILED")
        .scalar()
        or 0
    )
    total_amount = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.status == "SUCCESS")
        .scalar()
        or 0
    )
    avg_latency = (
        db.query(func.coalesce(func.avg(Transaction.processing_time_ms), 0))
        .filter(Transaction.status.in_(["SUCCESS", "FAILED"]))
        .scalar()
        or 0
    )

    success_rate = (successful / total * 100) if total > 0 else 0

    return {
        "total_transactions": total,
        "successful_transactions": successful,
        "failed_transactions": failed,
        "success_rate": round(success_rate, 2),
        "total_amount": round(total_amount, 2),
        "average_latency_ms": round(avg_latency, 2),
    }


@router.get("/psps")
def get_psp_analytics(db: Session = Depends(get_db)):
    """
    Per-PSP performance stats.

    NOTE on attribution: a PSP can be *attempted* on a transaction without
    being the one that finally handled it (e.g. it was tried first, failed,
    and the transaction retried onto a different PSP). `selected_psp` alone
    only tells us who handled a SUCCESS - it says nothing about PSPs that
    were tried and failed along the way, and it's empty for FAILED
    transactions entirely.

    Instead we walk `attempted_psps` (the ordered, comma-separated list of
    every PSP tried for that transaction - see payment_service):
      - SUCCESS transaction -> every PSP before the last one in the list
        failed; the last one succeeded.
      - FAILED transaction -> every PSP in the list failed (none of them
        pulled it off).
    This way a PSP that was tried and failed is correctly counted as a
    failure for that PSP, and a retry never gets double-counted as two
    separate successful transactions - only the PSP that actually finished
    the transaction gets a success credit, and only once.
    """
    psps = db.query(PSP).all()
    stats = {psp.name: {"total": 0, "successes": 0, "failures": 0} for psp in psps}

    transactions = (
        db.query(Transaction)
        .filter(Transaction.status.in_(["SUCCESS", "FAILED"]))
        .filter(Transaction.attempted_psps.isnot(None))
        .filter(Transaction.attempted_psps != "")
        .all()
    )

    for txn in transactions:
        attempted = [name for name in txn.attempted_psps.split(",") if name]
        if not attempted:
            continue

        if txn.status == "SUCCESS":
            failed_attempts, succeeded_psp = attempted[:-1], attempted[-1]
            for name in failed_attempts:
                if name in stats:
                    stats[name]["total"] += 1
                    stats[name]["failures"] += 1
            if succeeded_psp in stats:
                stats[succeeded_psp]["total"] += 1
                stats[succeeded_psp]["successes"] += 1
        else:  # FAILED - nothing in the chain worked
            for name in attempted:
                if name in stats:
                    stats[name]["total"] += 1
                    stats[name]["failures"] += 1

    result = []
    for psp in psps:
        s = stats[psp.name]
        total = s["total"]
        result.append(
            {
                "name": psp.name,
                "configured_success_rate": psp.success_rate,
                "configured_avg_latency_ms": psp.avg_latency_ms,
                "is_active": psp.is_active,
                "total_transactions_handled": total,
                "successes": s["successes"],
                "failures": s["failures"],
                "observed_success_rate": round(s["successes"] / total * 100, 2) if total > 0 else None,
            }
        )

    return result
