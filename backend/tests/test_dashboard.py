from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import Payment


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def test_dashboard_summary_and_payment_list_use_database_data() -> None:
    db = TestingSessionLocal()
    db.add(Payment(external_payment_id="pay_dashboard", amount=Decimal("25.00"), status="failed"))
    db.commit()
    db.close()

    summary = client.get("/api/v1/dashboard/summary")
    payments = client.get("/api/v1/payments")
    assert summary.status_code == 200
    assert summary.json()["failed_payments"] == 1
    assert payments.status_code == 200
    assert payments.json()[0]["external_payment_id"] == "pay_dashboard"