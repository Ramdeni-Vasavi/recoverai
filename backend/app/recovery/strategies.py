from dataclasses import dataclass

from app.agent.policies import RecoveryAction
from app.recovery.schemas import ExecutionStatus


@dataclass(frozen=True)
class StrategyResult:
    status: ExecutionStatus
    message: str


class RecoveryStrategy:
    action: RecoveryAction

    def simulate(self) -> StrategyResult:
        raise NotImplementedError


class RetryPaymentStrategy(RecoveryStrategy):
    action = RecoveryAction.RETRY_PAYMENT

    def simulate(self) -> StrategyResult:
        return StrategyResult(ExecutionStatus.SIMULATED, "Simulated payment retry created; no payment was processed.")


class PaymentLinkStrategy(RecoveryStrategy):
    action = RecoveryAction.SEND_PAYMENT_LINK

    def simulate(self) -> StrategyResult:
        return StrategyResult(ExecutionStatus.SIMULATED, "Simulated payment-link action created; no link was sent.")


class ReminderStrategy(RecoveryStrategy):
    action = RecoveryAction.SEND_REMINDER

    def simulate(self) -> StrategyResult:
        return StrategyResult(ExecutionStatus.SIMULATED, "Simulated reminder action created; no message was sent.")


class NoActionStrategy(RecoveryStrategy):
    action = RecoveryAction.NO_ACTION

    def simulate(self) -> StrategyResult:
        return StrategyResult(ExecutionStatus.NO_ACTION, "No recovery action was executed.")


STRATEGIES: dict[RecoveryAction, RecoveryStrategy] = {
    RecoveryAction.RETRY_PAYMENT: RetryPaymentStrategy(),
    RecoveryAction.SEND_PAYMENT_LINK: PaymentLinkStrategy(),
    RecoveryAction.SEND_REMINDER: ReminderStrategy(),
    RecoveryAction.NO_ACTION: NoActionStrategy(),
}
