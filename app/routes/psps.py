from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.psp import PSP
from app.schemas.psp import PSPResponse, PSPUpdateRequest

router = APIRouter(prefix="/api/psps", tags=["psps"])


@router.get("", response_model=list[PSPResponse])
def list_psps(db: Session = Depends(get_db)):
    return db.query(PSP).all()


@router.patch("/{psp_name}", response_model=PSPResponse)
def update_psp(psp_name: str, payload: PSPUpdateRequest, db: Session = Depends(get_db)):
    """
    Used by the demo panel on the dashboard so PSP behaviour (active/inactive,
    success rate) can be tweaked live to demonstrate routing/retry behaviour.
    """
    psp = db.query(PSP).filter(PSP.name == psp_name).first()
    if not psp:
        raise HTTPException(status_code=404, detail="PSP not found")

    if payload.success_rate is not None:
        psp.success_rate = payload.success_rate
    if payload.avg_latency_ms is not None:
        psp.avg_latency_ms = payload.avg_latency_ms
    if payload.is_active is not None:
        psp.is_active = payload.is_active

    db.commit()
    db.refresh(psp)
    return psp
