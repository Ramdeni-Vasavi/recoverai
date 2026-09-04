import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Payment
from app.schemas.payments import PaymentCreate, PaymentResponse

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db)) -> Payment:
    payment = Payment(**payload.model_dump())
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="external_payment_id already exists") from exc
    db.refresh(payment)
    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: uuid.UUID, db: Session = Depends(get_db)) -> Payment:
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment