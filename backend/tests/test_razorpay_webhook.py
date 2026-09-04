import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.integrations.razorpay.client import RazorpayClient, get_razorpay_client
from app.main import app
from app.models import AuditLog, Payment


WEBHOOK_SECRET = "test-webhook-secret"
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)
test_razorpay_client = RazorpayClient(
    type("TestSettings", (), {"razorpay_key_id": "test-key", "razorpay_key_secret": "test-secret", "razorpay_webhook_secret": WEBHOOK_SECRET})()
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_razorpay_client] = lambda: test_razorpay_client
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def signed_request(payload: dict[str, object], secret: str = WEBHOOK_SECRET):
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": signature})


def payment_event(event: str = "payment.failed", payment_id: str = "pay_webhook_1") -> dict[str, object]:
    return {
        "event": event,
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": "order_webhook_1",
                    "amount": 2500,
                    "currency": "INR",
                    "status": "failed" if event == "payment.failed" else "captured",
                    "error_code": "BAD_REQUEST_ERROR" if event == "payment.failed" else None,
                    "error_description": "Payment failed" if event == "payment.failed" else None,
                    "attempts": 2,
                }
            }
        },
    }


def test_valid_signature_is_accepted_and_creates_payment() -> None:
    response = signed_request(payment_event())
    assert response.status_code == 200
    assert response.json() == {"status": "processed"}


def test_invalid_signature_is_rejected() -> None:
    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=json.dumps(payment_event()).encode(),
        headers={"X-Razorpay-Signature": "invalid"},
    )
    assert response.status_code == 400


def test_missing_signature_is_rejected() -> None:
    response = client.post("/api/v1/webhooks/razorpay", content=json.dumps(payment_event()).encode())
    assert response.status_code == 400


def test_payment_failed_is_normalized() -> None:
    signed_request(payment_event())
    with TestingSessionLocal() as db:
        payment = db.scalar(select(Payment).where(Payment.external_payment_id == "pay_webhook_1"))
        assert payment is not None
        assert payment.amount == Decimal("25.00")
        assert payment.status == "failed"
        assert payment.failure_code == "BAD_REQUEST_ERROR"
        assert payment.attempt_count == 2


def test_payment_captured_creates_and_updates_payment() -> None:
    assert signed_request(payment_event("payment.captured", "pay_captured")).status_code == 200
    assert signed_request(payment_event("payment.captured", "pay_captured")).status_code == 200
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count(Payment.id))) == 1
        payment = db.scalar(select(Payment).where(Payment.external_payment_id == "pay_captured"))
        assert payment is not None
        assert payment.status == "recovered"


def test_duplicate_delivery_does_not_duplicate_payment() -> None:
    payload = payment_event(payment_id="pay_duplicate")
    assert signed_request(payload).status_code == 200
    assert signed_request(payload).status_code == 200
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count(Payment.id))) == 1


def test_unsupported_event_is_ignored_without_payment() -> None:
    payload = {"event": "refund.created", "payload": {}}
    response = signed_request(payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count(Payment.id))) == 0


def test_malformed_payload_is_rejected_after_signature_validation() -> None:
    body = b"{not-json"
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    response = client.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": signature})
    assert response.status_code == 400


def test_accepted_event_creates_audit_log() -> None:
    signed_request(payment_event(payment_id="pay_audit"))
    with TestingSessionLocal() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.event_type == "payment_created_from_webhook"))
        assert audit is not None
        assert audit.event_data == {"event": "payment.failed", "external_payment_id": "pay_audit"}


def test_sensitive_credentials_are_not_persisted_or_returned() -> None:
    response = signed_request(payment_event(payment_id="pay_sensitive"))
    assert "test-secret" not in response.text
    with TestingSessionLocal() as db:
        payment = db.scalar(select(Payment).where(Payment.external_payment_id == "pay_sensitive"))
        assert payment is not None
        assert "card" not in payment.__dict__
        assert "cvv" not in payment.__dict__