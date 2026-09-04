import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent.policies import decide_recovery
from app.agent.schemas import RecoveryDecisionResponse
from app.core.database import get_db
from app.models import AgentDecision, AuditLog, MLPrediction, Payment

router = APIRouter(prefix="/payments", tags=["decisions"])


@router.post("/{payment_id}/decide-recovery", response_model=RecoveryDecisionResponse, status_code=status.HTTP_201_CREATED)
def decide_payment_recovery(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> RecoveryDecisionResponse:
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    prediction = db.scalar(
        select(MLPrediction).where(MLPrediction.payment_id == payment.id).order_by(MLPrediction.predicted_at.desc(), MLPrediction.id.desc())
    )
    if prediction is None:
        raise HTTPException(status_code=400, detail="Generate a recovery prediction before requesting a decision")

    existing = db.scalar(
        select(AgentDecision).where(
            AgentDecision.payment_id == payment.id,
            AgentDecision.prediction_id == prediction.id,
        )
    )
    if existing is not None:
        result = decide_recovery(payment, prediction)
        return _response(payment.id, existing, result)

    result = decide_recovery(payment, prediction)
    decision = AgentDecision(
        payment_id=payment.id,
        prediction_id=prediction.id,
        selected_action=result.action.value,
        reasoning_summary=result.reason,
        confidence=result.confidence,
    )
    db.add(decision)
    try:
        db.flush()
        db.add(
            AuditLog(
                payment_id=payment.id,
                event_type="agent_decision",
                actor="recoverai_agent",
                event_data={
                    "decision_version": result.decision_version,
                    "prediction_id": str(prediction.id),
                    "recovery_probability": str(prediction.recovery_probability),
                    "selected_action": result.action.value,
                    "relevant_factors": result.relevant_factors,
                },
            )
        )
        db.commit()
        db.refresh(decision)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to persist recovery decision") from None
    return _response(payment.id, decision, result)


def _response(payment_id: uuid.UUID, decision: AgentDecision, result) -> RecoveryDecisionResponse:
    return RecoveryDecisionResponse(
        payment_id=payment_id,
        decision_id=decision.id,
        selected_action=decision.selected_action,
        reason=decision.reasoning_summary,
        confidence=Decimal(decision.confidence),
        decision_version=result.decision_version,
        relevant_factors=result.relevant_factors,
    )