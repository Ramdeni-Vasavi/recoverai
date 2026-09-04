from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.models import MLPrediction, Payment


class RecoveryAction(str, Enum):
    RETRY_PAYMENT = "retry_payment"
    SEND_PAYMENT_LINK = "create_payment_link"
    SEND_REMINDER = "send_reminder"
    NO_ACTION = "stop_recovery"


DECISION_VERSION = "recoverai-agent-v1"
HIGH_PROBABILITY = Decimal("0.70")
MEDIUM_PROBABILITY = Decimal("0.40")
MAX_RETRY_ATTEMPTS = 2


@dataclass(frozen=True)
class DecisionResult:
    action: RecoveryAction
    reason: str
    confidence: Decimal
    relevant_factors: list[str]
    decision_version: str = DECISION_VERSION


def decide_recovery(payment: Payment, prediction: MLPrediction) -> DecisionResult:
    probability = Decimal(prediction.recovery_probability)
    retryable = payment.status == "failed" and payment.failure_code != "BAD_REQUEST_ERROR"
    attempts = payment.attempt_count or 0

    if not retryable:
        action = RecoveryAction.NO_ACTION
        reason = "The payment failure is not retryable, so recovery is stopped rather than retrying blindly."
        factors = ["non_retryable_failure", f"recovery_probability={probability:.2f}"]
    elif probability >= HIGH_PROBABILITY and attempts < MAX_RETRY_ATTEMPTS:
        action = RecoveryAction.RETRY_PAYMENT
        reason = "Recovery probability is high and the failure is retryable, so a payment retry is preferred."
        factors = ["high_recovery_probability", "retryable_failure", f"attempt_count={attempts}"]
    elif probability >= MEDIUM_PROBABILITY:
        action = RecoveryAction.SEND_PAYMENT_LINK
        reason = "Recovery probability is moderate, so a payment link is preferred over another immediate retry."
        factors = ["medium_recovery_probability", "retryable_failure", f"attempt_count={attempts}"]
    else:
        action = RecoveryAction.NO_ACTION
        reason = "Recovery probability is low, so aggressive recovery attempts are avoided."
        factors = ["low_recovery_probability", f"attempt_count={attempts}"]

    confidence = max(Decimal("0.01"), min(Decimal("0.99"), abs(probability - Decimal("0.5")) * 2))
    return DecisionResult(action, reason, confidence, factors)