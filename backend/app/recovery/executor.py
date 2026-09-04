from app.agent.policies import RecoveryAction
from app.recovery.schemas import ExecutionStatus
from app.recovery.strategies import STRATEGIES, StrategyResult


class RecoveryExecutor:
    def __init__(self, mode: str = "simulation") -> None:
        if mode not in {"simulation", "sandbox"}:
            raise ValueError("Unsupported recovery execution mode")
        self.mode = mode

    def execute_approved(self, action: RecoveryAction) -> StrategyResult:
        strategy = STRATEGIES.get(action)
        if strategy is None:
            raise ValueError("Unsupported recovery action")
        if self.mode == "sandbox":
            return StrategyResult(ExecutionStatus.BLOCKED, "Sandbox execution is not configured; no external action was attempted.")
        return strategy.simulate()
