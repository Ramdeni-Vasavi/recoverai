from collections.abc import Generator

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create missing tables without dropping or recreating existing data."""
    from app.models import AgentDecision, AuditLog, GuardrailCheck, MLPrediction, Payment, RecoveryAttempt, RecoveryExecution, RecoveryOptimization, RecoveryOutcome

    Base.metadata.create_all(bind=engine)


DatabaseDependency = Depends(get_db)
