import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# use a separate test db so we don't clobber the dev db
os.environ["DATABASE_URL"] = "sqlite:///./test_payments.db"

from app.main import app  # noqa: E402
from app.database import engine, Base  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # re-seed PSPs since main.py only seeds on import
    from app.main import seed_psps
    seed_psps()
    yield


client = TestClient(app)


def make_payload(**overrides):
    payload = {
        "order_id": "ORD1001",
        "amount": 1499,
        "currency": "INR",
        "payment_method": "UPI",
        "customer_id": "CUST101",
        "idempotency_key": "PAY-TEST-001",
    }
    payload.update(overrides)
    return payload


def test_create_payment_success():
    response = client.post("/api/payments", json=make_payload())
    assert response.status_code == 200

    data = response.json()
    assert data["order_id"] == "ORD1001"
    assert data["status"] in ["SUCCESS", "FAILED"]
    assert data["transaction_id"].startswith("TXN")


def test_get_payment_by_id():
    create_res = client.post("/api/payments", json=make_payload(idempotency_key="PAY-TEST-002"))
    txn_id = create_res.json()["transaction_id"]

    get_res = client.get(f"/api/payments/{txn_id}")
    assert get_res.status_code == 200
    assert get_res.json()["transaction_id"] == txn_id


def test_get_nonexistent_payment_returns_404():
    response = client.get("/api/payments/TXNDOESNOTEXIST")
    assert response.status_code == 404


def test_list_payments():
    client.post("/api/payments", json=make_payload(idempotency_key="PAY-TEST-003"))
    response = client.get("/api/payments")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_list_payments_filter_by_status():
    client.post("/api/payments", json=make_payload(idempotency_key="PAY-TEST-004"))
    response = client.get("/api/payments", params={"status": "SUCCESS"})
    assert response.status_code == 200
    for txn in response.json():
        assert txn["status"] == "SUCCESS"
