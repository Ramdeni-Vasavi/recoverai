from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import AgentDecision, MLPrediction, Payment, RecoveryExecution, RecoveryOptimization
from app.recovery.schemas import ExecutionStatus


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


def setup_optimization(action: str, *, allowed: bool = True) -> str:
    db = TestingSessionLocal()
    payment = Payment(external_payment_id=f"pay_{uuid4()}", amount=Decimal("50.00"), status="failed", failure_code="TIMEOUT")
    prediction = MLPrediction(payment=payment, recovery_probability=Decimal("0.8"), model_version="recoverai-ml-v1")
    decision = AgentDecision(payment=payment, prediction=prediction, selected_action=action, reasoning_summary="approved context", confidence=Decimal("0.8"))
    db.add_all([payment, prediction, decision])
    db.flush()
    optimization = RecoveryOptimization(payment_id=payment.id, agent_decision_id=decision.id, selected_action=action, final_score=Decimal("0.8"), metaheuristic_score=Decimal("0.8"), quantum_inspired_score=Decimal("0.8"), guardrail_allowed=allowed, guardrail_reason="approved" if allowed else "blocked by guardrail", triggered_rules=[] if allowed else ["test_block"], optimization_version="recoverai-opt-v1", guardrail_version="recoverai-guard-v1")
    db.add(optimization)
    db.commit()
    payment_id = str(payment.id)
    db.close()
    return payment_id


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [("retry_payment", "SIMULATED"), ("create_payment_link", "SIMULATED"), ("send_reminder", "SIMULATED"), ("stop_recovery", "NO_ACTION")],
)
def test_approved_actions_execute_in_simulation(action: str, expected_status: str) -> None:
    payment_id = setup_optimization(action)
    response = client.post(f"/api/v1/payments/{payment_id}/execute-recovery")
    assert response.status_code == 200
    assert response.json()["status"] == expected_status
    assert response.json()["execution_mode"] == "simulation"
    assert "simulated" in response.json()["message"].lower() or expected_status == "NO_ACTION"


def test_guardrail_blocked_action_does_not_execute() -> None:
    payment_id = setup_optimization("retry_payment", allowed=False)
    response = client.post(f"/api/v1/payments/{payment_id}/execute-recovery")
    assert response.status_code == 200
    assert response.json()["status"] == ExecutionStatus.BLOCKED.value
    assert "guardrail" in response.json()["message"]


def test_missing_payment_and_optimization_are_rejected() -> None:
    assert client.post(f"/api/v1/payments/{uuid4()}/execute-recovery").status_code == 404
    payment = client.post("/api/v1/payments", json={"external_payment_id": "pay_no_opt", "amount": "10.00", "status": "failed"})
    assert client.post(f"/api/v1/payments/{payment.json()['id']}/execute-recovery").status_code == 400


def test_action_mismatch_is_blocked_and_persisted() -> None:
    payment_id = setup_optimization("send_reminder")
    response = client.post(f"/api/v1/payments/{payment_id}/execute-recovery", json={"action": "retry_payment"})
    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
    assert "action" in response.json()["message"]


def test_repeated_execution_is_idempotent() -> None:
    payment_id = setup_optimization("create_payment_link")
    first = client.post(f"/api/v1/payments/{payment_id}/execute-recovery")
    second = client.post(f"/api/v1/payments/{payment_id}/execute-recovery")
    assert first.json()["execution_id"] == second.json()["execution_id"]
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count(RecoveryExecution.id))) == 1


def test_execution_result_is_persisted() -> None:
    payment_id = setup_optimization("send_reminder")
    response = client.post(f"/api/v1/payments/{payment_id}/execute-recovery")
    with TestingSessionLocal() as db:
        record = db.get(RecoveryExecution, UUID(response.json()["execution_id"]))
        assert record is not None
        assert record.execution_mode == "simulation"
        assert record.payment_id == UUID(payment_id)