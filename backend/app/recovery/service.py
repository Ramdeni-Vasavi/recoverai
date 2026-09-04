import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.policies import RecoveryAction
from app.core.config import get_settings
from app.models import RecoveryExecution, RecoveryOptimization
from app.recovery.executor import RecoveryExecutor
from app.recovery.schemas import ExecutionResult, ExecutionStatus


class RecoveryExecutionService:
    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or get_settings().recovery_execution_mode

    def execute(
        self,
        db: Session,
        payment_id: uuid.UUID,
        optimization: RecoveryOptimization,
        requested_action: str | None = None,
    ) -> ExecutionResult:

        if optimization.payment_id != payment_id:
            return self._persist_blocked(
                db,
                payment_id,
                optimization,
                "Payment does not match the optimization result.",
                "payment_mismatch",
            )

        if (
            requested_action is not None
            and requested_action != optimization.selected_action
        ):
            return self._persist_blocked(
                db,
                payment_id,
                optimization,
                "Requested action does not match the approved optimized action.",
                "action_mismatch",
            )

        try:
            action = RecoveryAction(optimization.selected_action)
        except ValueError:
            return self._persist_blocked(
                db,
                payment_id,
                optimization,
                "Optimization contains an unsupported action.",
                "invalid_action",
            )

        if not optimization.guardrail_allowed:
            return self._persist_blocked(
                db,
                payment_id,
                optimization,
                optimization.guardrail_reason,
                "guardrail_blocked",
            )

        if (
            optimization.optimization_version != "recoverai-opt-v1"
            or not optimization.guardrail_version
        ):
            return self._persist_blocked(
                db,
                payment_id,
                optimization,
                "Optimization result is stale or invalid.",
                "invalid_optimization",
            )

        # Reuse only a previous successful/non-blocked execution.
        # A previous BLOCKED request must not prevent a later valid execution.
        existing = db.scalar(
            select(RecoveryExecution).where(
                RecoveryExecution.optimization_id == optimization.id,
                RecoveryExecution.status != ExecutionStatus.BLOCKED.value,
            )
        )

        if existing is not None:
            return self._result(existing)

        try:
            outcome = RecoveryExecutor(self.mode).execute_approved(action)
        except ValueError as exc:
            return self._persist_blocked(
                db,
                payment_id,
                optimization,
                str(exc),
                "invalid_execution",
            )

        record = RecoveryExecution(
            payment_id=payment_id,
            optimization_id=optimization.id,
            action=action.value,
            status=outcome.status.value,
            execution_mode=self.mode,
            message=outcome.message,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return self._result(record)

    def _persist_blocked(
        self,
        db: Session,
        payment_id: uuid.UUID,
        optimization: RecoveryOptimization,
        message: str,
        action: str,
    ) -> ExecutionResult:

        # Keep blocked attempts in the audit trail.
        record = RecoveryExecution(
            payment_id=payment_id,
            optimization_id=optimization.id,
            action=action,
            status=ExecutionStatus.BLOCKED.value,
            execution_mode=self.mode,
            message=message,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return self._result(record)

    @staticmethod
    def _result(record: RecoveryExecution) -> ExecutionResult:
        return ExecutionResult(
            execution_id=record.id,
            payment_id=record.payment_id,
            action=record.action,
            status=ExecutionStatus(record.status),
            execution_mode=record.execution_mode,
            message=record.message,
            optimization_id=record.optimization_id,
            created_at=record.created_at,
        )