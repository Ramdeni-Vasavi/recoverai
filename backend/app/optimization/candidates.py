from app.agent.policies import RecoveryAction
from app.models import MLPrediction, Payment


def generate_candidates(payment: Payment, prediction: MLPrediction) -> list[RecoveryAction]:
    probability = float(prediction.recovery_probability)
    retryable = payment.status == "failed" and payment.failure_code != "BAD_REQUEST_ERROR"
    candidates = [RecoveryAction.NO_ACTION]
    if retryable and payment.attempt_count < 2:
        candidates.insert(0, RecoveryAction.RETRY_PAYMENT)
    if retryable and probability >= 0.40:
        candidates.append(RecoveryAction.SEND_PAYMENT_LINK)
        candidates.append(RecoveryAction.SEND_REMINDER)
    return candidates