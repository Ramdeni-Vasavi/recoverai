from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.ml.features import FEATURE_NAMES, extract_features
from app.ml.model import MODEL_VERSION, get_trained_model
from app.ml.predictor import predict_recovery
from app.ml.training import DEMO_DATASET_LABEL, synthetic_training_data
from app.models import MLPrediction, Payment


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


def test_feature_extraction_is_deterministic() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    payment = Payment(
        external_payment_id="pay_feature",
        amount=Decimal("125.50"),
        currency="INR",
        status="failed",
        attempt_count=1,
        failure_code="TIMEOUT",
        created_at=created_at,
    )
    reference_time = datetime(2026, 1, 2, tzinfo=timezone.utc)
    first = extract_features(payment, reference_time)
    second = extract_features(payment, reference_time)
    assert first == second
    assert tuple(first.snapshot()) == FEATURE_NAMES


def test_missing_optional_payment_fields_are_safe() -> None:
    payment = Payment(external_payment_id="pay_missing", amount=Decimal("10.00"), created_at=None)
    features = extract_features(payment, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert features.failure_code_present == 0
    assert features.failure_reason_present == 0
    assert all(isinstance(value, float) for value in features.vector())


def test_synthetic_model_trains_successfully() -> None:
    features, labels = synthetic_training_data()
    model = get_trained_model()
    assert DEMO_DATASET_LABEL.startswith("synthetic/demo")
    assert features.shape[1] == len(FEATURE_NAMES)
    assert len(labels) == len(features)
    assert model.classes_.tolist() == [0, 1]


def test_model_prediction_is_deterministic() -> None:
    payment = Payment(external_payment_id="pay_deterministic", amount=Decimal("20.00"), status="failed")
    reference_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = predict_recovery(payment, reference_time)
    second = predict_recovery(payment, reference_time)
    assert first.probability == second.probability
    assert first.key_factors == second.key_factors


def test_prediction_probability_is_between_zero_and_one() -> None:
    payment = Payment(external_payment_id="pay_bounds", amount=Decimal("20.00"), status="failed")
    result = predict_recovery(payment, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert 0 <= result.probability <= 1


def test_prediction_endpoint_persists_prediction_and_returns_factors() -> None:
    payment_response = client.post(
        "/api/v1/payments",
        json={"external_payment_id": "pay_api", "amount": "25.00", "status": "failed"},
    )
    assert payment_response.status_code == 201
    payment_id = payment_response.json()["id"]

    response = client.post(f"/api/v1/payments/{payment_id}/predict-recovery")
    assert response.status_code == 201
    body = response.json()
    assert body["payment_id"] == payment_id
    assert 0 <= body["recovery_probability"] <= 1
    assert body["key_factors"]
    assert body["model_version"] == MODEL_VERSION

    with TestingSessionLocal() as db:
        prediction = db.scalar(select(MLPrediction).where(MLPrediction.payment_id == UUID(payment_id)))
        assert prediction is not None
        assert isinstance(prediction.features_snapshot, dict)
        assert prediction.model_version == MODEL_VERSION
        assert db.scalar(select(func.count(MLPrediction.id))) == 1


def test_prediction_endpoint_returns_404_for_unknown_payment() -> None:
    response = client.post("/api/v1/payments/00000000-0000-0000-0000-000000000000/predict-recovery")
    assert response.status_code == 404