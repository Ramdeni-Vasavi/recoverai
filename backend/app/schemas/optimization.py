from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class OptimizationResponse(BaseModel):
    payment_id: UUID
    optimization_id: UUID
    selected_action: str
    final_score: float = Field(ge=0, le=1)
    metaheuristic_score: float = Field(ge=0, le=1)
    quantum_inspired_score: float = Field(ge=0, le=1)
    guardrail_allowed: bool
    guardrail_reason: str
    triggered_rules: list[str]
    optimization_version: str
    guardrail_version: str
