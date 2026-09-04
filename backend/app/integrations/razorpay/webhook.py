import json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.integrations.razorpay.client import RazorpayClient, get_razorpay_client
from app.integrations.razorpay.schemas import RazorpayWebhookPayload
from app.models import AuditLog, Payment

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
SUPPORTED_EVENTS = {"payment.failed", "payment.captured"}


def _internal_status(event: str) -> str:
    return "failed" if event == "payment.failed" else "recovered"


def _payment_values(event: str, entity: Any) -> dict[str, Any]:
    return {
        "external_payment_id": entity.id,
        "order_id": entity.order_id,
        "amount": Decimal(entity.amount) / Decimal("100"),
        "currency": entity.currency,
        "status": _internal_status(event),
        "failure_reason": entity.error_description,
        "failure_code": entity.error_code,
        "attempt_count": entity.attempts or 0,
    }


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
    client: RazorpayClient = Depends(get_razorpay_client),
) -> dict[str, str]:
    body = await request.body()
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing webhook signature")
    if not client.verify_webhook_signature(body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = RazorpayWebhookPayload.model_validate(json.loads(body))
    except (json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=400, detail="Malformed webhook payload") from None

    if payload.event not in SUPPORTED_EVENTS:
        return {"status": "ignored"}
    payment_payload = payload.payload.get("payment")
    if payment_payload is None:
        raise HTTPException(status_code=400, detail="Missing payment payload")

    values = _payment_values(payload.event, payment_payload.entity)
    try:
        payment = db.scalar(select(Payment).where(Payment.external_payment_id == values["external_payment_id"]))
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to persist webhook event") from None
    event_type = "payment_created_from_webhook" if payment is None else "payment_updated_from_webhook"
    if payment is None:
        payment = Payment(**values)
        db.add(payment)
    else:
        for field, value in values.items():
            setattr(payment, field, value)

    try:
        db.flush()
        db.add(
            AuditLog(
                payment=payment,
                event_type=event_type,
                actor="razorpay_webhook",
                event_data={"event": payload.event, "external_payment_id": payment.external_payment_id},
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to persist webhook event") from None

    return {"status": "processed"}