from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .execution_protocol import (
    AuthorityDecision,
    ExecutionAdapter,
    ExecutionEnvelope,
    ExecutionReceipt,
    ExecutionStatus,
)
from .runtime import GaiaRuntime


@dataclass(frozen=True)
class RuntimeCapability:
    name: str
    executor: Callable[[dict[str, Any]], dict[str, Any]]
    requires_review: bool = False


class AutonomousIntelligenceRuntime(ExecutionAdapter):
    """Stable execution seam between G.A.I.A cognition and external worlds/tools.

    G.A.I.A decides what intervention is useful. This runtime decides whether the
    requested capability is available and authorized, performs the external
    operation through a registered adapter, and returns normalized evidence,
    verification, and state-change records without altering G.A.I.A's causal
    reasoning machinery.
    """

    def __init__(self, gaia: GaiaRuntime, *, system_id: str = "gaia") -> None:
        self.gaia = gaia
        self.system_id = system_id
        self._capabilities: dict[str, RuntimeCapability] = {}

    def register_capability(self, capability: RuntimeCapability) -> None:
        if capability.name in self._capabilities:
            raise ValueError(f"capability already registered: {capability.name}")
        self._capabilities[capability.name] = capability

    def authorize(self, envelope: ExecutionEnvelope) -> AuthorityDecision:
        if envelope.system_id != self.system_id:
            return AuthorityDecision.DENY
        capability = self._capabilities.get(envelope.capability)
        if capability is None:
            return AuthorityDecision.DENY
        if capability.requires_review and not envelope.authority.get("reviewed", False):
            return AuthorityDecision.REQUIRE_REVIEW
        if envelope.authority.get("denied", False):
            return AuthorityDecision.DENY
        return AuthorityDecision.ALLOW

    def execute(self, envelope: ExecutionEnvelope) -> ExecutionReceipt:
        decision = self.authorize(envelope)
        if decision is not AuthorityDecision.ALLOW:
            self.gaia._record(
                "execution_not_authorized",
                {
                    "execution_id": envelope.execution_id,
                    "capability": envelope.capability,
                    "decision": decision.value,
                },
            )
            return ExecutionReceipt(
                execution_id=envelope.execution_id,
                system_id=self.system_id,
                status=(ExecutionStatus.DENIED if decision is AuthorityDecision.DENY else ExecutionStatus.REQUESTED),
                authority_decision=decision,
            )

        capability = self._capabilities[envelope.capability]
        self.gaia._record(
            "execution_started",
            {
                "execution_id": envelope.execution_id,
                "capability": envelope.capability,
                "intent": envelope.intent,
            },
        )

        try:
            result = capability.executor(dict(envelope.intent))
        except Exception as exc:  # boundary: preserve failure as evidence, do not hide it
            failure = {"type": exc.__class__.__name__, "message": str(exc)}
            self.gaia._record(
                "execution_failed",
                {"execution_id": envelope.execution_id, "failure": failure},
            )
            return ExecutionReceipt(
                execution_id=envelope.execution_id,
                system_id=self.system_id,
                status=ExecutionStatus.FAILED,
                authority_decision=decision,
                failure=failure,
            )

        evidence = tuple(result.get("evidence", ()))
        verification = tuple(result.get("verification", ()))
        state_changes = tuple(result.get("state_changes", ()))
        output = dict(result.get("output", result))

        self.gaia._record(
            "execution_completed",
            {
                "execution_id": envelope.execution_id,
                "capability": envelope.capability,
                "evidence": list(evidence),
                "verification": list(verification),
                "state_changes": list(state_changes),
            },
        )

        return ExecutionReceipt(
            execution_id=envelope.execution_id,
            system_id=self.system_id,
            status=ExecutionStatus.SUCCEEDED,
            authority_decision=decision,
            output=output,
            evidence=evidence,
            verification=verification,
            state_changes=state_changes,
        )
