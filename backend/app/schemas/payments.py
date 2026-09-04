from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    external_payment_id: str = Field(min_length=1, max_length=255)
    order_id: str | None = Field(default=None, max_length=255)
    customer_id: str | None = Field(default=None, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    status: str = Field(default="pending", pattern="^(failed|recovered|abandoned|pending)$")
    failure_reason: str | None = None
    failure_code: str | None = Field(default=None, max_length=100)
    attempt_count: int = Field(default=0, ge=0)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_payment_id: str
    order_id: str | None
    customer_id: str | None
    amount: Decimal
    currency: str
    status: str
    failure_reason: str | None
    failure_code: str | None
    attempt_count: int
    created_at: datetime
    updated_at: datetime


class PaymentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str