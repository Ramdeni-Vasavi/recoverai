from decimal import Decimal

from app.guardrails.rules import ALLOWED_ACTIONS, GUARDRAIL_VERSION, MAX_AUTOMATIC_RETRIES
from app.guardrails.schemas import GuardrailResult


def evaluate_guardrails(action: str, *, payment_status: str | None, failure_code: str | None, attempt_count: int | None, probability: Decimal | float | None) -> GuardrailResult:
    rules: list[str] = []
    if action not in ALLOWED_ACTIONS:
        rules.append("unknown_action")
    if payment_status is None or attempt_count is None or probability is None:
        rules.append("missing_context")
    elif not 0 <= float(probability) <= 1:
        rules.append("invalid_probability")
    if action == "retry_payment" and failure_code == "BAD_REQUEST_ERROR":
        rules.append("non_retryable_failure")
    if action == "retry_payment" and attempt_count is not None and attempt_count >= MAX_AUTOMATIC_RETRIES:
        rules.append("maximum_retry_attempts")
    if rules:
        return GuardrailResult(False, action, rules, "Recovery action blocked by: " + ", ".join(rules) + ".", GUARDRAIL_VERSION)
    return GuardrailResult(True, None, [], "Selected recovery action passed all deterministic guardrails.", GUARDRAIL_VERSION)
