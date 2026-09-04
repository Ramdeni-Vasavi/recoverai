from functools import lru_cache

from sklearn.linear_model import LogisticRegression

from app.ml.training import synthetic_training_data


MODEL_VERSION = "recoverai-ml-v1"


@lru_cache(maxsize=1)
def get_trained_model() -> LogisticRegression:
    features, labels = synthetic_training_data()
    model = LogisticRegression(random_state=42, solver="liblinear", max_iter=500)
    model.fit(features, labels)
    return model