from typing import Final

import numpy as np

from app.ml.features import FEATURE_NAMES


DEMO_DATASET_LABEL: Final[str] = "synthetic/demo training data; not production Razorpay data"


def synthetic_training_data() -> tuple[np.ndarray, np.ndarray]:
    """Return a small deterministic demo dataset kept separate from application records."""
    rows = [
        [40, 0, 1, 1, 1, 0, 0, 1],
        [80, 1, 3, 1, 1, 1, 1, 1],
        [120, 0, 2, 1, 1, 0, 1, 1],
        [250, 1, 6, 1, 1, 1, 0, 1],
        [500, 2, 12, 1, 1, 1, 1, 1],
        [60, 3, 48, 1, 1, 0, 0, 1],
        [40, 0, 2, 0, 1, 0, 0, 1],
        [100, 2, 72, 1, 0, 1, 1, 1],
        [300, 4, 96, 1, 0, 1, 1, 1],
        [1000, 1, 4, 1, 0, 1, 0, 1],
        [200, 0, 1, 1, 1, 0, 0, 0],
        [150, 1, 4, 1, 1, 0, 0, 0],
    ]
    labels = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
    return np.asarray(rows, dtype=float), np.asarray(labels, dtype=int)


def training_feature_names() -> tuple[str, ...]:
    return FEATURE_NAMES