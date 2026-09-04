from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


json_type = JSON().with_variant(JSONB, "postgresql")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_customer_id", "customer_id"),
        CheckConstraint("status IN ('failed', 'recovered', 'abandoned', 'pending')", name="ck_payment_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_payment_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String(255))
    customer_id: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    recovery_attempts: Mapped[list["RecoveryAttempt"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    predictions: Mapped[list["MLPrediction"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    recovery_outcomes: Mapped[list["RecoveryOutcome"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    optimization_results: Mapped[list["RecoveryOptimization"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    execution_results: Mapped[list["RecoveryExecution"]] = relationship(back_populates="payment", cascade="all, delete-orphan")


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"
    __table_args__ = (
        CheckConstraint("channel IN ('payment_retry', 'email', 'sms', 'whatsapp', 'payment_link')", name="ck_attempt_channel"),
        CheckConstraint("status IN ('pending', 'executed', 'succeeded', 'failed', 'cancelled')", name="ck_attempt_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(30))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="recovery_attempts")
    recovery_outcomes: Mapped[list["RecoveryOutcome"]] = relationship(back_populates="recovery_attempt", cascade="all, delete-orphan")


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (CheckConstraint("recovery_probability >= 0 AND recovery_probability <= 1", name="ck_prediction_probability"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    recovery_probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    features_snapshot: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="predictions")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="prediction")


class AgentDecision(Base):
    __tablename__ = "agent_decisions"
    __table_args__ = (
        CheckConstraint("selected_action IN ('retry_payment', 'send_reminder', 'create_payment_link', 'stop_recovery')", name="ck_selected_action"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_decision_confidence"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_id: Mapped[UUID] = mapped_column(ForeignKey("ml_predictions.id", ondelete="CASCADE"), nullable=False)
    selected_action: Mapped[str] = mapped_column(String(40), nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="agent_decisions")
    prediction: Mapped[MLPrediction] = relationship(back_populates="agent_decisions")
    guardrail_checks: Mapped[list["GuardrailCheck"]] = relationship(back_populates="agent_decision", cascade="all, delete-orphan")


class GuardrailCheck(Base):
    __tablename__ = "guardrail_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_decision_id: Mapped[UUID] = mapped_column(ForeignKey("agent_decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    agent_decision: Mapped[AgentDecision] = relationship(back_populates="guardrail_checks")


class RecoveryOutcome(Base):
    __tablename__ = "recovery_outcomes"
    __table_args__ = (CheckConstraint("status IN ('success', 'failed', 'no_change')", name="ck_outcome_status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    recovery_attempt_id: Mapped[UUID] = mapped_column(ForeignKey("recovery_attempts.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="recovery_outcomes")
    recovery_attempt: Mapped[RecoveryAttempt] = relationship(back_populates="recovery_outcomes")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="audit_logs")


class RecoveryOptimization(Base):
    __tablename__ = "recovery_optimizations"
    __table_args__ = (
        CheckConstraint("final_score >= 0 AND final_score <= 1", name="ck_optimization_score"),
        CheckConstraint("guardrail_allowed IN (0, 1)", name="ck_optimization_guardrail"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_decision_id: Mapped[UUID] = mapped_column(ForeignKey("agent_decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_action: Mapped[str] = mapped_column(String(40), nullable=False)
    final_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    metaheuristic_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    quantum_inspired_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    guardrail_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guardrail_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    triggered_rules: Mapped[list[str]] = mapped_column(json_type, nullable=False, default=list)
    optimization_version: Mapped[str] = mapped_column(String(50), nullable=False)
    guardrail_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="optimization_results")


class RecoveryExecution(Base):
    __tablename__ = "recovery_executions"
    __table_args__ = (CheckConstraint("status IN ('SIMULATED', 'EXECUTED', 'BLOCKED', 'FAILED', 'NO_ACTION')", name="ck_execution_status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    optimization_id: Mapped[UUID] = mapped_column(ForeignKey("recovery_optimizations.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="execution_results")