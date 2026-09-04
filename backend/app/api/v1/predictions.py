import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml.predictor import predict_recovery
from app.models import MLPrediction, Payment
from app.schemas.predictions import RecoveryPredictionResponse

router = APIRouter(prefix="/payments", tags=["predictions"])


@router.post("/{payment_id}/predict-recovery", response_model=RecoveryPredictionResponse, status_code=status.HTTP_201_CREATED)
def predict_payment_recovery(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> RecoveryPredictionResponse:
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    try:
        result = predict_recovery(payment)
        prediction = MLPrediction(
            payment_id=payment.id,
            recovery_probability=Decimal(str(result.probability)),
            model_version=result.model_version,
            features_snapshot=result.features.snapshot(),
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
    except (SQLAlchemyError, ValueError):
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to generate recovery prediction") from None

    return RecoveryPredictionResponse(
        payment_id=payment.id,
        prediction_id=prediction.id,
        recovery_probability=prediction.recovery_probability,
        model_version=prediction.model_version,
        key_factors=result.key_factors,
    )