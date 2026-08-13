from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from math import exp, log
from typing import Callable, Iterable
import json

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_id: str
    kind: str
    value: float
    provenance: str


class Hypothesis(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    probability: float = Field(gt=0.0, le=1.0)
    expected: dict[str, float]


class MissionSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    mission_id: str
    budget: float = Field(ge=0.0)
    max_interventions: int = Field(ge=0)
    entropy_stop: float = Field(ge=0.0)


@dataclass
class TraceEvent:
    sequence: int
    kind: str
    payload: dict
    previous_hash: str

    def digest(self) -> str:
        encoded = json.dumps({"sequence": self.sequence, "kind": self.kind, "payload": self.payload, "previous_hash": self.previous_hash}, sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()


@dataclass
class GaiaRuntime:
    spec: MissionSpec
    hypotheses: list[Hypothesis]
    spent: float = 0.0
    interventions: int = 0
    trace: list[TraceEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        total = sum(h.probability for h in self.hypotheses)
        if not self.hypotheses or total <= 0:
            raise ValueError("mission requires hypotheses")
        self.hypotheses = [h.model_copy(update={"probability": h.probability / total}) for h in self.hypotheses]
        self._record("mission_started", {"mission_id": self.spec.mission_id})

    def _record(self, kind: str, payload: dict) -> TraceEvent:
        previous = self.trace[-1].digest() if self.trace else "GENESIS"
        event = TraceEvent(len(self.trace), kind, payload, previous)
        self.trace.append(event)
        return event

    def entropy(self) -> float:
        return -sum(h.probability * log(h.probability, 2) for h in self.hypotheses if h.probability > 0)

    def admit(self, evidence: Evidence, likelihood: Callable[[Hypothesis, Evidence], float]) -> list[Hypothesis]:
        weights = []
        for hypothesis in self.hypotheses:
            score = max(likelihood(hypothesis, evidence), 1e-12)
            weights.append(hypothesis.probability * score)
        total = sum(weights)
        self.hypotheses = [h.model_copy(update={"probability": w / total}) for h, w in zip(self.hypotheses, weights)]
        self._record("belief_revision", {"evidence_id": evidence.evidence_id, "posterior": {h.name: h.probability for h in self.hypotheses}})
        return self.hypotheses

    def choose_intervention(self, candidates: Iterable[tuple[str, float, float]]) -> str | None:
        if self.interventions >= self.spec.max_interventions:
            return None
        affordable = [(name, gain, cost) for name, gain, cost in candidates if cost >= 0 and self.spent + cost <= self.spec.budget]
        if not affordable:
            return None
        name, gain, cost = max(affordable, key=lambda x: (x[1] / max(x[2], 1e-9), x[1], -x[2]))
        self.spent += cost
        self.interventions += 1
        self._record("intervention_selected", {"name": name, "expected_information_gain": gain, "cost": cost})
        return name

    def resolved(self) -> bool:
        return self.entropy() <= self.spec.entropy_stop or self.spent >= self.spec.budget or self.interventions >= self.spec.max_interventions

    def verify_trace(self) -> bool:
        previous = "GENESIS"
        for event in self.trace:
            if event.previous_hash != previous:
                return False
            previous = event.digest()
        return True
