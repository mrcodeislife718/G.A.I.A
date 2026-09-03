from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Intervention:
    variable: str
    value: Any


@dataclass
class CausalHypothesis:
    name: str
    predict: Callable[[dict[str, Any], Intervention], dict[str, Any]]
    confirmations: int = 0
    contradictions: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        total = self.confirmations + self.contradictions
        if total == 0:
            return 0.5
        return self.confirmations / total


class CausalEngine:
    """Explicit intervention-based causal testing.

    Correlation is not accepted as causality. A hypothesis must make a
    prediction under an intervention and is updated only after the observed
    post-intervention state is compared with that prediction.
    """

    def __init__(self) -> None:
        self._hypotheses: dict[str, CausalHypothesis] = {}

    def register(self, hypothesis: CausalHypothesis) -> None:
        if not hypothesis.name:
            raise ValueError("hypothesis name is required")
        if hypothesis.name in self._hypotheses:
            raise ValueError(f"hypothesis already exists: {hypothesis.name}")
        self._hypotheses[hypothesis.name] = hypothesis

    def counterfactual(
        self,
        hypothesis_name: str,
        state: dict[str, Any],
        intervention: Intervention,
    ) -> dict[str, Any]:
        hypothesis = self._require(hypothesis_name)
        intervened = dict(state)
        intervened[intervention.variable] = intervention.value
        prediction = hypothesis.predict(intervened, intervention)
        if not isinstance(prediction, dict):
            raise TypeError("causal prediction must be a state dictionary")
        return prediction

    def reconcile(
        self,
        hypothesis_name: str,
        prior_state: dict[str, Any],
        intervention: Intervention,
        observed_state: dict[str, Any],
        *,
        keys: set[str] | None = None,
    ) -> dict[str, Any]:
        hypothesis = self._require(hypothesis_name)
        predicted = self.counterfactual(hypothesis_name, prior_state, intervention)
        compared_keys = keys or (set(predicted) | set(observed_state))
        differences = {
            key: {"predicted": predicted.get(key), "observed": observed_state.get(key)}
            for key in sorted(compared_keys)
            if predicted.get(key) != observed_state.get(key)
        }
        confirmed = len(differences) == 0
        if confirmed:
            hypothesis.confirmations += 1
        else:
            hypothesis.contradictions += 1
        result = {
            "hypothesis": hypothesis_name,
            "intervention": {"variable": intervention.variable, "value": intervention.value},
            "predicted": predicted,
            "observed": dict(observed_state),
            "confirmed": confirmed,
            "differences": differences,
            "confidence": hypothesis.confidence,
        }
        hypothesis.history.append(result)
        return result

    def rank(self) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    "name": h.name,
                    "confidence": h.confidence,
                    "confirmations": h.confirmations,
                    "contradictions": h.contradictions,
                }
                for h in self._hypotheses.values()
            ),
            key=lambda item: (-item["confidence"], item["name"]),
        )

    def _require(self, name: str) -> CausalHypothesis:
        try:
            return self._hypotheses[name]
        except KeyError as exc:
            raise KeyError(f"unknown causal hypothesis: {name}") from exc
