from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class RecoveryDecisionResponse(BaseModel):
    payment_id: UUID
    decision_id: UUID
    selected_action: str
    reason: str
    confidence: Decimal = Field(ge=0, le=1)
    decision_version: str
    relevant_factors: list[str]