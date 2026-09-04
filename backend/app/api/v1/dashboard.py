import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AgentDecision, MLPrediction, Payment, RecoveryExecution, RecoveryOptimization

router = APIRouter(tags=["dashboard"])


def _latest(db: Session, model, payment_id: uuid.UUID):
    return db.scalar(select(model).where(model.payment_id == payment_id).order_by(model.created_at.desc() if hasattr(model, "created_at") else model.predicted_at.desc(), model.id.desc()))


@router.get("/payments", response_model=None)
def list_payments(db: Session = Depends(get_db)) -> list[dict]:
    payments = list(db.scalars(select(Payment).order_by(Payment.created_at.desc())).all())
    return jsonable_encoder(payments)


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict[str, int]:
    failed = db.scalar(select(func.count(Payment.id)).where(Payment.status == "failed")) or 0
    high_probability = db.scalar(select(func.count(func.distinct(MLPrediction.payment_id))).where(MLPrediction.recovery_probability >= 0.7)) or 0
    recoveries = db.scalar(select(func.count(Payment.id)).where(Payment.status == "recovered")) or 0
    blocked = db.scalar(select(func.count(RecoveryOptimization.id)).where(RecoveryOptimization.guardrail_allowed.is_(False))) or 0
    return {"failed_payments": failed, "high_recovery_probability": high_probability, "recoveries": recoveries, "blocked_actions": blocked}


@router.get("/payments/{payment_id}/prediction", response_model=None)
def payment_prediction(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    record = db.scalar(select(MLPrediction).where(MLPrediction.payment_id == payment_id).order_by(MLPrediction.predicted_at.desc(), MLPrediction.id.desc()))
    if record is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return jsonable_encoder(record)


@router.get("/payments/{payment_id}/decision", response_model=None)
def payment_decision(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    record = db.scalar(select(AgentDecision).where(AgentDecision.payment_id == payment_id).order_by(AgentDecision.created_at.desc(), AgentDecision.id.desc()))
    if record is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return jsonable_encoder(record)


@router.get("/payments/{payment_id}/optimization", response_model=None)
def payment_optimization(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    record = db.scalar(select(RecoveryOptimization).where(RecoveryOptimization.payment_id == payment_id).order_by(RecoveryOptimization.created_at.desc(), RecoveryOptimization.id.desc()))
    if record is None:
        raise HTTPException(status_code=404, detail="Optimization not found")
    return jsonable_encoder(record)


@router.get("/payments/{payment_id}/execution", response_model=None)
def payment_execution(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    record = db.scalar(select(RecoveryExecution).where(RecoveryExecution.payment_id == payment_id).order_by(RecoveryExecution.created_at.desc(), RecoveryExecution.id.desc()))
    if record is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return jsonable_encoder(record)
