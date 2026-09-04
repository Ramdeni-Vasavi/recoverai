from pydantic import BaseModel, ConfigDict, Field


class RazorpayPaymentEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    order_id: str | None = None
    amount: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    status: str = Field(min_length=1)
    error_code: str | None = None
    error_description: str | None = None
    attempts: int | None = Field(default=None, ge=0)


class RazorpayPaymentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity: RazorpayPaymentEntity


class RazorpayWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event: str = Field(min_length=1)
    payload: dict[str, RazorpayPaymentPayload]