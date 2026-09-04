from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import AuditLog, MLPrediction, Payment, RecoveryAttempt


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


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


def payment_payload(external_id: str = "pay_test_1") -> dict[str, object]:
    return {"external_payment_id": external_id, "order_id": "order_1", "customer_id": "customer_1", "amount": "125.50"}


def test_payment_can_be_created_and_retrieved() -> None:
    response = client.post("/api/v1/payments", json=payment_payload())
    assert response.status_code == 201
    payment_id = response.json()["id"]

    retrieved = client.get(f"/api/v1/payments/{payment_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["external_payment_id"] == "pay_test_1"
    assert retrieved.json()["amount"] == "125.50"


def test_external_payment_id_is_unique() -> None:
    assert client.post("/api/v1/payments", json=payment_payload()).status_code == 201
    duplicate = client.post("/api/v1/payments", json=payment_payload())
    assert duplicate.status_code == 409


def test_payment_relationships_work() -> None:
    db = TestingSessionLocal()
    payment = Payment(external_payment_id="pay_rel", amount=Decimal("10.00"))
    payment.recovery_attempts.append(RecoveryAttempt(attempt_number=1, channel="email", action="send_reminder"))
    payment.predictions.append(MLPrediction(recovery_probability=Decimal("0.75"), model_version="v1", features_snapshot={"attempts": 1}))
    payment.audit_logs.append(AuditLog(event_type="payment_created", actor="test", event_data={"source": "pytest"}))
    db.add(payment)
    db.commit()
    db.refresh(payment)

    assert payment.recovery_attempts[0].payment is payment
    assert payment.predictions[0].payment is payment
    assert payment.audit_logs[0].payment is payment
    db.close()


def test_recovery_probability_is_between_zero_and_one() -> None:
    db = TestingSessionLocal()
    payment = Payment(external_payment_id="pay_probability", amount=Decimal("10.00"))
    db.add(payment)
    db.commit()
    db.add(MLPrediction(payment_id=payment.id, recovery_probability=Decimal("1.01"), model_version="v1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()