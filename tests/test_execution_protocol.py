from datetime import datetime, timezone

import pytest

from gaia.autonomous_runtime import AutonomousIntelligenceRuntime, RuntimeCapability
from gaia.execution_protocol import (
    ActorIdentity,
    AuthorityDecision,
    AuthorityGrant,
    CapabilityIdentity,
    ExecutionEnvelope,
    ExecutionStatus,
    FailureClass,
    FailureRecord,
    ResourceUsage,
)
from gaia.runtime import GaiaRuntime, MissionSpec, Hypothesis


def make_gaia() -> GaiaRuntime:
    return GaiaRuntime(
        spec=MissionSpec(
            mission_id="protocol-test",
            budget=10.0,
            max_interventions=5,
            entropy_stop=0.0,
        ),
        hypotheses=[
            Hypothesis(
                name="baseline",
                probability=1.0,
                expected={"signal": 1.0},
            )
        ],
    )


def test_protocol_envelope_preserves_identity_and_causality():
    envelope = ExecutionEnvelope(
        execution_id="exec-1",
        event_id="event-1",
        causal_parent_ids=("parent-1",),
        sequence=3,
        system_id="gaia",
        system_kind="causal-intelligence",
        mission_id="mission-1",
        actor=ActorIdentity(
            actor_id="charles",
            actor_kind="human",
            authority_domain="founder",
        ),
        capability="inspect",
        capability_identity=CapabilityIdentity(
            capability_id="inspect",
            version="1.0",
            provider="gaia",
        ),
        authority_grants=(
            AuthorityGrant(
                grant_id="grant-1",
                issuer_id="charles",
                scopes=("inspect",),
                issued_at=datetime.now(timezone.utc),
            ),
        ),
    )

    assert envelope.protocol_version == "1.1"
    assert envelope.execution_id == "exec-1"
    assert envelope.event_id == "event-1"
    assert envelope.causal_parent_ids == ("parent-1",)
    assert envelope.sequence == 3
    assert envelope.capability_identity is not None
    assert envelope.capability_identity.capability_id == "inspect"


def test_protocol_rejects_negative_sequence_and_resource_usage():
    with pytest.raises(ValueError):
        ExecutionEnvelope(
            sequence=-1,
            system_id="gaia",
            system_kind="causal-intelligence",
            capability="inspect",
        )

    with pytest.raises(ValueError):
        ResourceUsage(memory_bytes_peak=-1)


def test_failure_record_is_structured():
    failure = FailureRecord(
        failure_class=FailureClass.CAPABILITY,
        code="NO_CAPABILITY",
        message="Capability is unavailable",
        retryable=False,
    )

    assert failure.failure_id
    assert failure.failure_class is FailureClass.CAPABILITY
    assert failure.code == "NO_CAPABILITY"


def test_runtime_denies_unknown_capability():
    runtime = AutonomousIntelligenceRuntime(make_gaia(), system_id="gaia")

    envelope = ExecutionEnvelope(
        system_id="gaia",
        system_kind="causal-intelligence",
        capability="missing",
    )

    receipt = runtime.execute(envelope)

    assert receipt.execution_id == envelope.execution_id
    assert receipt.system_id == "gaia"
    assert receipt.status is ExecutionStatus.DENIED
    assert receipt.authority_decision is AuthorityDecision.DENY


def test_runtime_requires_review_when_capability_is_review_gated():
    runtime = AutonomousIntelligenceRuntime(make_gaia(), system_id="gaia")
    runtime.register_capability(
        RuntimeCapability(
            name="deploy",
            executor=lambda intent: {"output": {"ok": True}},
            requires_review=True,
        )
    )

    envelope = ExecutionEnvelope(
        system_id="gaia",
        system_kind="causal-intelligence",
        capability="deploy",
    )

    receipt = runtime.execute(envelope)

    assert receipt.status is ExecutionStatus.REQUESTED
    assert receipt.authority_decision is AuthorityDecision.REQUIRE_REVIEW


def test_runtime_executes_authorized_capability_and_preserves_evidence():
    runtime = AutonomousIntelligenceRuntime(make_gaia(), system_id="gaia")
    runtime.register_capability(
        RuntimeCapability(
            name="inspect",
            executor=lambda intent: {
                "output": {"value": intent["value"]},
                "evidence": [{"evidence_id": "e1", "kind": "observation", "provenance": "test"}],
                "verification": [
                    {
                        "claim_id": "v1",
                        "verifier_id": "test",
                        "requirement": "output-produced",
                        "passed": True,
                    }
                ],
                "state_changes": [
                    {
                        "state_id": "s1",
                        "kind": "observed",
                        "delta": {"value": intent["value"]},
                    }
                ],
            },
        )
    )

    envelope = ExecutionEnvelope(
        system_id="gaia",
        system_kind="causal-intelligence",
        capability="inspect",
        intent={"value": 42},
    )

    receipt = runtime.execute(envelope)

    assert receipt.status is ExecutionStatus.SUCCEEDED
    assert receipt.authority_decision is AuthorityDecision.ALLOW
    assert receipt.output["value"] == 42
    assert len(receipt.evidence) == 1
    assert len(receipt.verification) == 1
    assert len(receipt.state_changes) == 1


def test_runtime_normalizes_capability_failure():
    runtime = AutonomousIntelligenceRuntime(make_gaia(), system_id="gaia")

    def explode(_intent):
        raise RuntimeError("boom")

    runtime.register_capability(
        RuntimeCapability(
            name="explode",
            executor=explode,
        )
    )

    envelope = ExecutionEnvelope(
        system_id="gaia",
        system_kind="causal-intelligence",
        capability="explode",
    )

    receipt = runtime.execute(envelope)

    assert receipt.status is ExecutionStatus.FAILED
    assert receipt.authority_decision is AuthorityDecision.ALLOW
    assert receipt.failure is not None


def test_duplicate_capability_registration_is_rejected():
    runtime = AutonomousIntelligenceRuntime(make_gaia(), system_id="gaia")

    capability = RuntimeCapability(
        name="inspect",
        executor=lambda intent: {"output": intent},
    )

    runtime.register_capability(capability)

    with pytest.raises(ValueError, match="already registered"):
        runtime.register_capability(capability)
