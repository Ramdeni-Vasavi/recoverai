from dataclasses import dataclass

from app.agent.policies import RecoveryAction
from app.models import MLPrediction, Payment
from app.optimization.quantum import initialize_state, quantum_score, update_state
from app.optimization.scorer import fitness


OPTIMIZATION_VERSION = "recoverai-opt-v1"


@dataclass(frozen=True)
class OptimizationResult:
    selected_action: RecoveryAction
    final_score: float
    metaheuristic_score: float
    quantum_inspired_score: float
    scores: dict[str, dict[str, float]]


def optimize_candidates(candidates: list[RecoveryAction], payment: Payment, prediction: MLPrediction) -> OptimizationResult:
    if not candidates:
        raise ValueError("No valid recovery candidates")
    states = initialize_state(len(candidates))
    scores: dict[str, dict[str, float]] = {}
    for index, action in enumerate(candidates):
        base = fitness(action, payment, prediction)
        state = update_state(states[index], base)
        quantum = quantum_score(state)
        combined = max(0.0, min(1.0, 0.65 * max(0.0, base) + 0.35 * quantum))
        scores[action.value] = {"metaheuristic": max(0.0, min(1.0, (base + 1) / 2)), "quantum": quantum, "final": combined}
    selected = max(candidates, key=lambda action: (scores[action.value]["final"], -candidates.index(action)))
    selected_scores = scores[selected.value]
    return OptimizationResult(selected, selected_scores["final"], selected_scores["metaheuristic"], selected_scores["quantum"], scores)