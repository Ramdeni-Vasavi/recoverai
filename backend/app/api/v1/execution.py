import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Payment, RecoveryOptimization
from app.recovery.schemas import ExecuteRecoveryRequest, ExecutionResult
from app.recovery.service import RecoveryExecutionService

router = APIRouter(prefix="/payments", tags=["recovery-execution"])


@router.post("/{payment_id}/execute-recovery", response_model=ExecutionResult, status_code=status.HTTP_200_OK)
def execute_recovery(payment_id: uuid.UUID, request: ExecuteRecoveryRequest | None = None, db: Session = Depends(get_db)) -> ExecutionResult:
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    optimization = db.scalar(select(RecoveryOptimization).where(RecoveryOptimization.payment_id == payment.id).order_by(RecoveryOptimization.created_at.desc(), RecoveryOptimization.id.desc()))
    if optimization is None:
        raise HTTPException(status_code=400, detail="Create an approved optimization before execution")
    requested_action = request.action if request is not None else None
    return RecoveryExecutionService().execute(db, payment.id, optimization, requested_action)
