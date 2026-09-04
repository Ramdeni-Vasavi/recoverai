from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class QuantumState:
    amplitudes: tuple[float, float]

    @property
    def probabilities(self) -> tuple[float, float]:
        return tuple(value * value for value in self.amplitudes)


def initialize_state(candidate_count: int) -> list[QuantumState]:
    if candidate_count <= 0:
        raise ValueError("candidate_count must be positive")
    amplitude = 1 / sqrt(2)
    return [QuantumState((amplitude, amplitude)) for _ in range(candidate_count)]


def update_state(state: QuantumState, fitness: float) -> QuantumState:
    positive = max(0.0, min(1.0, (fitness + 1.0) / 2.0))
    first = sqrt(positive)
    second = sqrt(1.0 - positive)
    norm = sqrt(first * first + second * second)
    return QuantumState((first / norm, second / norm))


def quantum_score(state: QuantumState) -> float:
    return state.probabilities[0]