from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.models import Payment


FEATURE_NAMES = (
    "amount_major",
    "attempt_count",
    "age_hours",
    "currency_is_inr",
    "retryable",
    "failure_code_present",
    "failure_reason_present",
    "status_failed",
)


@dataclass(frozen=True)
class RecoveryFeatures:
    amount_major: float
    attempt_count: float
    age_hours: float
    currency_is_inr: float
    retryable: float
    failure_code_present: float
    failure_reason_present: float
    status_failed: float

    def vector(self) -> list[float]:
        return [getattr(self, name) for name in FEATURE_NAMES]

    def snapshot(self) -> dict[str, float]:
        return asdict(self)


def extract_features(payment: Payment, reference_time: datetime | None = None) -> RecoveryFeatures:
    """Convert non-sensitive payment metadata into a stable model input."""
    now = reference_time or datetime.now(timezone.utc)
    created_at = payment.created_at or now
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - created_at).total_seconds() / 3600)
    amount = payment.amount if payment.amount is not None else Decimal("0")
    failure_code = (payment.failure_code or "").strip()

    return RecoveryFeatures(
        amount_major=float(amount),
        attempt_count=float(payment.attempt_count or 0),
        age_hours=age_hours,
        currency_is_inr=float((payment.currency or "").upper() == "INR"),
        retryable=float(payment.status == "failed" and failure_code != "BAD_REQUEST_ERROR"),
        failure_code_present=float(bool(failure_code)),
        failure_reason_present=float(bool((payment.failure_reason or "").strip())),
        status_failed=float(payment.status == "failed"),
    )