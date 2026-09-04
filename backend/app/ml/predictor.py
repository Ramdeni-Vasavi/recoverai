from dataclasses import dataclass
from datetime import datetime, timezone

from app.ml.features import FEATURE_NAMES, RecoveryFeatures, extract_features
from app.ml.model import MODEL_VERSION, get_trained_model
from app.models import Payment


@dataclass(frozen=True)
class PredictionResult:
    probability: float
    features: RecoveryFeatures
    key_factors: list[str]
    model_version: str = MODEL_VERSION


def _key_factors(features: RecoveryFeatures) -> list[str]:
    model = get_trained_model()
    contributions = [coefficient * value for coefficient, value in zip(model.coef_[0], features.vector())]
    ranked = sorted(zip(FEATURE_NAMES, contributions), key=lambda item: abs(item[1]), reverse=True)
    return [f"{name} {'increases' if contribution >= 0 else 'decreases'} recovery likelihood" for name, contribution in ranked[:3]]


def predict_recovery(payment: Payment, reference_time: datetime | None = None) -> PredictionResult:
    reference_time = reference_time or datetime.now(timezone.utc)
    features = extract_features(payment, reference_time=reference_time)
    probability = float(get_trained_model().predict_proba([features.vector()])[0, 1])
    return PredictionResult(
        probability=max(0.0, min(1.0, probability)),
        features=features,
        key_factors=_key_factors(features),
    )