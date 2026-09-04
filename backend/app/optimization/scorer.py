from app.agent.policies import RecoveryAction
from app.models import MLPrediction, Payment


ACTION_COST = {
    RecoveryAction.RETRY_PAYMENT: 0.20,
    RecoveryAction.SEND_PAYMENT_LINK: 0.08,
    RecoveryAction.SEND_REMINDER: 0.05,
    RecoveryAction.NO_ACTION: 0.00,
}


def fitness(action: RecoveryAction, payment: Payment, prediction: MLPrediction) -> float:
    probability = float(prediction.recovery_probability)
    attempts = min(float(payment.attempt_count or 0), 5.0) / 5.0
    retry_risk = attempts * 0.30 if action is RecoveryAction.RETRY_PAYMENT else 0.0
    suitability = 0.15 if action is RecoveryAction.RETRY_PAYMENT and payment.failure_code != "BAD_REQUEST_ERROR" else 0.0
    suitability += 0.10 if action is RecoveryAction.SEND_PAYMENT_LINK and probability >= 0.40 else 0.0
    return max(-1.0, min(1.0, probability - ACTION_COST[action] - retry_risk + suitability))
