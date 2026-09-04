import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.guardrails.engine import evaluate_guardrails
from app.models import AgentDecision, MLPrediction, Payment, RecoveryOptimization
from app.optimization.candidates import generate_candidates
from app.optimization.metaheuristic import OPTIMIZATION_VERSION, optimize_candidates
from app.schemas.optimization import OptimizationResponse

router = APIRouter(prefix="/payments", tags=["optimization"])


@router.post("/{payment_id}/optimize-recovery", response_model=OptimizationResponse, status_code=status.HTTP_201_CREATED)
def optimize_payment_recovery(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> OptimizationResponse:
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    prediction = db.scalar(select(MLPrediction).where(MLPrediction.payment_id == payment.id).order_by(MLPrediction.predicted_at.desc(), MLPrediction.id.desc()))
    if prediction is None:
        raise HTTPException(status_code=400, detail="Generate a recovery prediction before optimization")
    agent_decision = db.scalar(select(AgentDecision).where(AgentDecision.payment_id == payment.id, AgentDecision.prediction_id == prediction.id).order_by(AgentDecision.created_at.desc(), AgentDecision.id.desc()))
    if agent_decision is None:
        raise HTTPException(status_code=400, detail="Create an agent decision before optimization")

    existing = db.scalar(select(RecoveryOptimization).where(RecoveryOptimization.payment_id == payment.id, RecoveryOptimization.agent_decision_id == agent_decision.id, RecoveryOptimization.optimization_version == OPTIMIZATION_VERSION))
    if existing is not None:
        return _response(existing)

    try:
        candidates = generate_candidates(payment, prediction)
        optimization = optimize_candidates(candidates, payment, prediction)
        guardrail = evaluate_guardrails(
            optimization.selected_action.value,
            payment_status=payment.status,
            failure_code=payment.failure_code,
            attempt_count=payment.attempt_count,
            probability=prediction.recovery_probability,
        )
        record = RecoveryOptimization(
            payment_id=payment.id,
            agent_decision_id=agent_decision.id,
            selected_action=optimization.selected_action.value,
            final_score=Decimal(str(optimization.final_score)),
            metaheuristic_score=Decimal(str(optimization.metaheuristic_score)),
            quantum_inspired_score=Decimal(str(optimization.quantum_inspired_score)),
            guardrail_allowed=guardrail.allowed,
            guardrail_reason=guardrail.reason,
            triggered_rules=guardrail.triggered_rules,
            optimization_version=OPTIMIZATION_VERSION,
            guardrail_version=guardrail.guardrail_version,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    except (SQLAlchemyError, ValueError):
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to persist recovery optimization") from None
    return _response(record)


def _response(record: RecoveryOptimization) -> OptimizationResponse:
    return OptimizationResponse(
        payment_id=record.payment_id,
        optimization_id=record.id,
        selected_action=record.selected_action,
        final_score=float(record.final_score),
        metaheuristic_score=float(record.metaheuristic_score),
        quantum_inspired_score=float(record.quantum_inspired_score),
        guardrail_allowed=record.guardrail_allowed,
        guardrail_reason=record.guardrail_reason,
        triggered_rules=record.triggered_rules,
        optimization_version=record.optimization_version,
        guardrail_version=record.guardrail_version,
    )
