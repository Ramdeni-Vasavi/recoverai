from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.policies import RecoveryAction
from app.core.database import Base, get_db
from app.guardrails.engine import evaluate_guardrails
from app.guardrails.rules import GUARDRAIL_VERSION
from app.main import app
from app.models import AgentDecision, MLPrediction, Payment, RecoveryOptimization
from app.optimization.candidates import generate_candidates
from app.optimization.metaheuristic import OPTIMIZATION_VERSION, optimize_candidates
from app.optimization.quantum import initialize_state, quantum_score, update_state


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


def make_context(probability: str = "0.80", *, code: str | None = "TIMEOUT", attempts: int = 0):
    payment = Payment(external_payment_id=f"pay_{uuid4()}", amount=Decimal("100.00"), status="failed", failure_code=code, attempt_count=attempts)
    prediction = MLPrediction(payment=payment, recovery_probability=Decimal(probability), model_version="recoverai-ml-v1")
    return payment, prediction


def test_candidate_generation_is_deterministic_and_contextual() -> None:
    payment, prediction = make_context()
    first = generate_candidates(payment, prediction)
    second = generate_candidates(payment, prediction)
    assert first == second
    assert RecoveryAction.RETRY_PAYMENT in first

    non_retryable, prediction = make_context(code="BAD_REQUEST_ERROR")
    assert RecoveryAction.RETRY_PAYMENT not in generate_candidates(non_retryable, prediction)


def test_optimizer_evaluates_candidates_and_is_deterministic() -> None:
    payment, prediction = make_context()
    candidates = generate_candidates(payment, prediction)
    first = optimize_candidates(candidates, payment, prediction)
    second = optimize_candidates(candidates, payment, prediction)
    assert first == second
    assert first.selected_action in candidates
    assert set(first.scores) == {candidate.value for candidate in candidates}
    assert 0 <= first.final_score <= 1
    assert 0 <= first.metaheuristic_score <= 1
    assert 0 <= first.quantum_inspired_score <= 1
    assert first.selected_action.value == max(first.scores, key=lambda name: first.scores[name]["final"])


def test_quantum_state_is_normalized_and_updates_deterministically() -> None:
    states = initialize_state(3)
    assert len(states) == 3
    for state in states:
        assert sum(state.probabilities) == pytest.approx(1.0)
        assert all(0 <= value <= 1 for value in state.probabilities)
    first = update_state(states[0], 0.4)
    second = update_state(states[0], 0.4)
    assert first == second
    assert quantum_score(first) == pytest.approx(0.7)


def test_quantum_score_participates_in_final_score() -> None:
    payment, prediction = make_context()
    result = optimize_candidates([RecoveryAction.SEND_REMINDER, RecoveryAction.NO_ACTION], payment, prediction)
    selected_scores = result.scores[result.selected_action.value]
    assert result.final_score == pytest.approx(0.65 * max(0, selected_scores["metaheuristic"] * 2 - 1) + 0.35 * selected_scores["quantum"])


def test_guardrails_block_unsafe_contexts_and_allow_safe_action() -> None:
    blocked = evaluate_guardrails("retry_payment", payment_status="failed", failure_code="BAD_REQUEST_ERROR", attempt_count=0, probability=Decimal("0.9"))
    assert not blocked.allowed
    assert "non_retryable_failure" in blocked.triggered_rules

    excessive = evaluate_guardrails("retry_payment", payment_status="failed", failure_code="TIMEOUT", attempt_count=2, probability=0.9)
    assert not excessive.allowed
    assert "maximum_retry_attempts" in excessive.triggered_rules

    unknown = evaluate_guardrails("unknown", payment_status="failed", failure_code="TIMEOUT", attempt_count=0, probability=0.5)
    assert not unknown.allowed
    assert "unknown_action" in unknown.triggered_rules

    missing = evaluate_guardrails("send_reminder", payment_status=None, failure_code=None, attempt_count=None, probability=None)
    assert not missing.allowed
    assert "missing_context" in missing.triggered_rules

    invalid = evaluate_guardrails("send_reminder", payment_status="failed", failure_code="TIMEOUT", attempt_count=0, probability=1.1)
    assert not invalid.allowed
    assert "invalid_probability" in invalid.triggered_rules

    safe = evaluate_guardrails("send_reminder", payment_status="failed", failure_code="TIMEOUT", attempt_count=0, probability=0.5)
    assert safe.allowed
    assert safe.triggered_rules == []
    assert safe.guardrail_version == GUARDRAIL_VERSION


def test_optimization_endpoint_persists_and_reuses_result() -> None:
    payment_response = client.post("/api/v1/payments", json={"external_payment_id": "pay_opt_api", "amount": "100.00", "status": "failed", "failure_code": "TIMEOUT"})
    payment_id = payment_response.json()["id"]
    assert client.post(f"/api/v1/payments/{payment_id}/predict-recovery").status_code == 201
    assert client.post(f"/api/v1/payments/{payment_id}/decide-recovery").status_code == 201

    first = client.post(f"/api/v1/payments/{payment_id}/optimize-recovery")
    second = client.post(f"/api/v1/payments/{payment_id}/optimize-recovery")
    assert first.status_code == second.status_code == 201
    assert first.json()["optimization_id"] == second.json()["optimization_id"]
    assert first.json()["optimization_version"] == OPTIMIZATION_VERSION
    assert "guardrail_allowed" in first.json()
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count(RecoveryOptimization.id))) == 1


def test_optimization_endpoint_requires_payment_prediction_and_decision() -> None:
    assert client.post(f"/api/v1/payments/{uuid4()}/optimize-recovery").status_code == 404
    payment = client.post("/api/v1/payments", json={"external_payment_id": "pay_no_opt_prediction", "amount": "10.00", "status": "failed"})
    payment_id = payment.json()["id"]
    assert client.post(f"/api/v1/payments/{payment_id}/optimize-recovery").status_code == 400
    assert client.post(f"/api/v1/payments/{payment_id}/predict-recovery").status_code == 201
    assert client.post(f"/api/v1/payments/{payment_id}/optimize-recovery").status_code == 400