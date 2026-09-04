from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ExecutionStatus(str, Enum):
    SIMULATED = "SIMULATED"
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    NO_ACTION = "NO_ACTION"


class ExecuteRecoveryRequest(BaseModel):
    action: str | None = None


class ExecutionResult(BaseModel):
    execution_id: UUID
    payment_id: UUID
    action: str
    status: ExecutionStatus
    execution_mode: str
    message: str
    optimization_id: UUID
    created_at: datetime
