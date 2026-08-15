import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///./test_routing.db"

from app.database import engine, Base, SessionLocal  # noqa: E402
from app.models.psp import PSP  # noqa: E402
from app.services import routing_service, payment_service  # noqa: E402
from app.schemas.payment import PaymentCreateRequest  # noqa: E402


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_calculate_score_prefers_high_success_low_latency():
    high_success_low_latency = routing_service.calculate_score(0.95, 200)
    low_success_high_latency = routing_service.calculate_score(0.70, 900)
    assert high_success_low_latency > low_success_high_latency


def test_select_psp_picks_best_score(db_session):
    db_session.add_all([
        PSP(name="Alpha", success_rate=0.92, avg_latency_ms=450, is_active=True),
        PSP(name="Beta", success_rate=0.86, avg_latency_ms=250, is_active=True),
        PSP(name="Gamma", success_rate=0.95, avg_latency_ms=600, is_active=True),
    ])
    db_session.commit()

    best = routing_service.select_psp(db_session)

    # manually confirm which one should actually win by score
    scores = {
        "Alpha": routing_service.calculate_score(0.92, 450),
        "Beta": routing_service.calculate_score(0.86, 250),
        "Gamma": routing_service.calculate_score(0.95, 600),
    }
    expected_winner = max(scores, key=scores.get)

    assert best.name == expected_winner


def test_select_psp_ignores_inactive_psps(db_session):
    db_session.add_all([
        PSP(name="Alpha", success_rate=0.99, avg_latency_ms=100, is_active=False),
        PSP(name="Beta", success_rate=0.50, avg_latency_ms=999, is_active=True),
    ])
    db_session.commit()

    best = routing_service.select_psp(db_session)
    assert best.name == "Beta"


def test_select_psp_returns_none_when_all_inactive(db_session):
    db_session.add_all([
        PSP(name="Alpha", success_rate=0.99, avg_latency_ms=100, is_active=False),
    ])
    db_session.commit()

    best = routing_service.select_psp(db_session)
    assert best is None


def test_retry_moves_to_another_psp_on_failure(db_session, monkeypatch):
    # Alpha has the better score so it's tried first, but we force it to
    # fail (via monkeypatching the simulated PSP call) so we can deterministically
    # verify the orchestrator retries with Beta instead of depending on randomness.
    db_session.add_all([
        PSP(name="Alpha", success_rate=0.95, avg_latency_ms=100, is_active=True),
        PSP(name="Beta", success_rate=0.80, avg_latency_ms=100, is_active=True),
    ])
    db_session.commit()

    def fake_call_psp(psp_name, success_rate, avg_latency_ms):
        # Alpha (tried first, since it has the better score) fails; anything
        # else succeeds.
        return {"success": psp_name != "Alpha", "latency_ms": 50}

    monkeypatch.setattr(payment_service.psp_service, "call_psp", fake_call_psp)

    payload = PaymentCreateRequest(
        order_id="ORD3001",
        amount=100,
        currency="INR",
        payment_method="UPI",
        customer_id="CUST303",
        idempotency_key="PAY-RETRY-001",
    )

    transaction = payment_service.create_payment(db_session, payload)

    assert transaction.status == "SUCCESS"
    assert transaction.selected_psp == "Beta"
    assert "Alpha" in transaction.attempted_psps
    assert transaction.retry_count >= 1


def test_psp_analytics_attributes_failed_attempts_correctly(db_session, monkeypatch):
    # Alpha is tried first (better score) and fails; Beta then succeeds.
    # A correct analytics view should count this as ONE failure for Alpha
    # and ONE success for Beta - not two separate successful transactions.
    from app.routes.analytics import get_psp_analytics

    db_session.add_all([
        PSP(name="Alpha", success_rate=0.95, avg_latency_ms=100, is_active=True),
        PSP(name="Beta", success_rate=0.80, avg_latency_ms=100, is_active=True),
    ])
    db_session.commit()

    def fake_call_psp(psp_name, success_rate, avg_latency_ms):
        return {"success": psp_name != "Alpha", "latency_ms": 50}

    monkeypatch.setattr(payment_service.psp_service, "call_psp", fake_call_psp)

    payload = PaymentCreateRequest(
        order_id="ORD3003",
        amount=100,
        currency="INR",
        payment_method="UPI",
        customer_id="CUST303",
        idempotency_key="PAY-ANALYTICS-001",
    )
    payment_service.create_payment(db_session, payload)

    stats = {row["name"]: row for row in get_psp_analytics(db_session)}

    assert stats["Alpha"]["total_transactions_handled"] == 1
    assert stats["Alpha"]["failures"] == 1
    assert stats["Alpha"]["successes"] == 0

    assert stats["Beta"]["total_transactions_handled"] == 1
    assert stats["Beta"]["successes"] == 1
    assert stats["Beta"]["failures"] == 0


def test_all_psps_failing_results_in_failed_status(db_session):
    db_session.add_all([
        PSP(name="Alpha", success_rate=0.0, avg_latency_ms=100, is_active=True),
        PSP(name="Beta", success_rate=0.0, avg_latency_ms=100, is_active=True),
    ])
    db_session.commit()

    payload = PaymentCreateRequest(
        order_id="ORD3002",
        amount=100,
        currency="INR",
        payment_method="UPI",
        customer_id="CUST303",
        idempotency_key="PAY-RETRY-002",
    )

    transaction = payment_service.create_payment(db_session, payload)
    assert transaction.status == "FAILED"
