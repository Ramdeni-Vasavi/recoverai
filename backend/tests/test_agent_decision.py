from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.policies import DECISION_VERSION, RecoveryAction, decide_recovery
from app.core.database import Base, get_db
from app.main import app
from app.models import AgentDecision, AuditLog, MLPrediction, Payment


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
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


def make_context(probability: str, *, code: str | None = "TIMEOUT", attempts: int = 0):
    payment = Payment(external_payment_id=f"pay_{uuid4()}", amount=Decimal("100.00"), status="failed", failure_code=code, attempt_count=attempts)
    prediction = MLPrediction(payment=payment, recovery_probability=Decimal(probability), model_version="recoverai-ml-v1")
    return payment, prediction


def test_high_probability_retryable_failure_retries() -> None:
    payment, prediction = make_context("0.90")
    result = decide_recovery(payment, prediction)
    assert result.action is RecoveryAction.RETRY_PAYMENT
    assert result.confidence <= 1


def test_medium_probability_uses_softer_action() -> None:
    payment, prediction = make_context("0.55")
    result = decide_recovery(payment, prediction)
    assert result.action is RecoveryAction.SEND_PAYMENT_LINK


def test_low_probability_avoids_aggressive_retry() -> None:
    payment, prediction = make_context("0.15")
    result = decide_recovery(payment, prediction)
    assert result.action is RecoveryAction.NO_ACTION


def test_non_retryable_failure_never_retries() -> None:
    payment, prediction = make_context("0.95", code="BAD_REQUEST_ERROR")
    assert decide_recovery(payment, prediction).action is not RecoveryAction.RETRY_PAYMENT


def test_decision_is_deterministic_and_explained() -> None:
    payment, prediction = make_context("0.65")
    first = decide_recovery(payment, prediction)
    second = decide_recovery(payment, prediction)
    assert first == second
    assert first.reason
    assert str(first.action.value) in {"retry_payment", "create_payment_link", "send_reminder", "stop_recovery"}
    assert 0 <= first.confidence <= 1


def test_decision_endpoint_persists_and_reuses_decision() -> None:
    payment_response = client.post("/api/v1/payments", json={"external_payment_id": "pay_agent_api", "amount": "100.00", "status": "failed", "failure_code": "TIMEOUT"})
    payment_id = payment_response.json()["id"]
    prediction_response = client.post(f"/api/v1/payments/{payment_id}/predict-recovery")
    assert prediction_response.status_code == 201

    first = client.post(f"/api/v1/payments/{payment_id}/decide-recovery")
    second = client.post(f"/api/v1/payments/{payment_id}/decide-recovery")
    assert first.status_code == second.status_code == 201
    assert first.json()["decision_id"] == second.json()["decision_id"]
    assert first.json()["decision_version"] == DECISION_VERSION
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count(AgentDecision.id))) == 1
        audit = db.scalar(select(AuditLog).where(AuditLog.event_type == "agent_decision"))
        assert audit is not None
        assert audit.event_data["decision_version"] == DECISION_VERSION


def test_decision_requires_existing_payment_and_prediction() -> None:
    missing = client.post(f"/api/v1/payments/{uuid4()}/decide-recovery")
    assert missing.status_code == 404
    payment_response = client.post("/api/v1/payments", json={"external_payment_id": "pay_no_prediction", "amount": "100.00", "status": "failed"})
    response = client.post(f"/api/v1/payments/{payment_response.json()['id']}/decide-recovery")
    assert response.status_code == 400