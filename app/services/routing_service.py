"""
Routing logic that picks which PSP should handle a payment.

The idea: we don't want to just pick a random PSP, and we don't need ML for
this either. A simple weighted score based on success rate and latency is
enough to demonstrate "intelligent routing" and is easy to explain in an
interview.

score = (success_rate * 100) - (latency_penalty)

where latency_penalty scales the latency down so it doesn't completely
dominate the score. Higher score wins.
"""

from sqlalchemy.orm import Session
from app.models.psp import PSP

# how much 1ms of latency "costs" in score points.
# tuned so a few hundred ms of latency difference matters, but doesn't
# outweigh a large success rate gap
LATENCY_WEIGHT = 0.05


def calculate_score(success_rate: float, avg_latency_ms: int) -> float:
    latency_penalty = avg_latency_ms * LATENCY_WEIGHT
    return (success_rate * 100) - latency_penalty


def get_ranked_psps(db: Session, exclude_names=None):
    """
    Return active PSPs (excluding any already-attempted ones), sorted best
    score first.
    """
    exclude_names = exclude_names or []

    psps = (
        db.query(PSP)
        .filter(PSP.is_active == True)  # noqa: E712
        .filter(PSP.name.notin_(exclude_names))
        .all()
    )

    scored = [
        (psp, calculate_score(psp.success_rate, psp.avg_latency_ms))
        for psp in psps
    ]

    # best score first
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [psp for psp, score in scored]


def select_psp(db: Session, exclude_names=None):
    """Pick the single best available PSP, or None if nothing is available."""
    ranked = get_ranked_psps(db, exclude_names=exclude_names)
    return ranked[0] if ranked else None
