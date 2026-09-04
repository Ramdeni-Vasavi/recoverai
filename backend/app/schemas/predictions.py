from uuid import UUID

from pydantic import BaseModel, Field


class RecoveryPredictionResponse(BaseModel):
    payment_id: UUID
    prediction_id: UUID
    recovery_probability: float = Field(ge=0, le=1)
    model_version: str
    key_factors: list[str]