from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    blocked_action: str | None
    triggered_rules: list[str]
    reason: str
    guardrail_version: str
