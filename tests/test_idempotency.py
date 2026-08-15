import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///./test_idempotency.db"

from app.main import app  # noqa: E402
from app.database import engine, Base  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.main import seed_psps
    seed_psps()
    yield


client = TestClient(app)


def make_payload(**overrides):
    payload = {
        "order_id": "ORD2001",
        "amount": 500,
        "currency": "INR",
        "payment_method": "UPI",
        "customer_id": "CUST202",
        "idempotency_key": "PAY-IDEMP-001",
    }
    payload.update(overrides)
    return payload


def test_duplicate_idempotency_key_returns_same_transaction():
    first = client.post("/api/payments", json=make_payload())
    second = client.post("/api/payments", json=make_payload(order_id="ORD9999"))

    assert first.status_code == 200
    assert second.status_code == 200

    # same idempotency key -> same transaction id, even though order_id differs
    # in the second request (it should be ignored since the txn already exists)
    assert first.json()["transaction_id"] == second.json()["transaction_id"]
    assert second.json()["order_id"] == "ORD2001"


def test_only_one_row_created_for_duplicate_key():
    client.post("/api/payments", json=make_payload())
    client.post("/api/payments", json=make_payload())
    client.post("/api/payments", json=make_payload())

    response = client.get("/api/payments")
    matching = [
        t for t in response.json() if t["order_id"] == "ORD2001"
    ]
    assert len(matching) == 1


def test_different_idempotency_keys_create_different_transactions():
    first = client.post("/api/payments", json=make_payload(idempotency_key="PAY-IDEMP-A"))
    second = client.post("/api/payments", json=make_payload(idempotency_key="PAY-IDEMP-B"))

    assert first.json()["transaction_id"] != second.json()["transaction_id"]
