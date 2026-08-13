from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStatus(str, Enum):
    REQUESTED = "requested"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"


class AuthorityDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_REVIEW = "require_review"


class FailureClass(str, Enum):
    VALIDATION = "validation"
    AUTHORIZATION = "authorization"
    CAPABILITY = "capability"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    EXTERNAL = "external"
    VERIFICATION = "verification"
    STATE = "state"
    INTERNAL = "internal"
    CANCELLED = "cancelled"


class ActorIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)
    actor_id: str
    actor_kind: str
    authority_domain: str | None = None


class CapabilityIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)
    capability_id: str
    version: str | None = None
    provider: str | None = None


class AuthorityGrant(BaseModel):
    model_config = ConfigDict(frozen=True)
    grant_id: str
    issuer_id: str
    scopes: tuple[str, ...] = ()
    issued_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_ref: str | None = None


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_id: str
    kind: str
    provenance: str
    content_hash: str | None = None
    produced_by: str | None = None
    observed_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class VerificationClaim(BaseModel):
    model_config = ConfigDict(frozen=True)
    claim_id: str
    verifier_id: str
    requirement: str
    passed: bool
    evidence_refs: tuple[str, ...] = ()
    method: str | None = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StateChange(BaseModel):
    model_config = ConfigDict(frozen=True)
    state_id: str
    kind: str
    before_ref: str | None = None
    after_ref: str | None = None
    delta: dict[str, Any] = Field(default_factory=dict)


class CheckpointRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    checkpoint_id: str
    state_refs: tuple[str, ...] = ()
    reversible: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecoveryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    recovery_id: str
    trigger_event_id: str
    strategy: str
    outcome: str
    checkpoint_ref: str | None = None


class ResourceUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    wall_time_ms: int | None = Field(default=None, ge=0)
    cpu_time_ms: int | None = Field(default=None, ge=0)
    memory_bytes_peak: int | None = Field(default=None, ge=0)
    network_bytes: int | None = Field(default=None, ge=0)
    cost_units: float | None = Field(default=None, ge=0.0)


class IntegrityRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    algorithm: str = "sha256"
    content_hash: str
    previous_hash: str | None = None


class FailureRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    failure_id: str = Field(default_factory=lambda: str(uuid4()))
    failure_class: FailureClass
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionEnvelope(BaseModel):
    """Protocol 1.1 contract: common execution semantics without shared cognition."""

    model_config = ConfigDict(frozen=True)

    protocol_version: str = "1.1"
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    causal_parent_ids: tuple[str, ...] = ()
    sequence: int | None = Field(default=None, ge=0)
    system_id: str
    system_kind: str
    mission_id: str | None = None
    actor: ActorIdentity | None = None
    capability: str
    capability_identity: CapabilityIdentity | None = None
    intent: dict[str, Any] = Field(default_factory=dict)
    authority: dict[str, Any] = Field(default_factory=dict)
    authority_grants: tuple[AuthorityGrant, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    state_refs: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    checkpoint_ref: str | None = None
    integrity: IntegrityRecord | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol_version: str = "1.1"
    execution_id: str
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    causal_parent_ids: tuple[str, ...] = ()
    sequence: int | None = Field(default=None, ge=0)
    system_id: str
    status: ExecutionStatus
    authority_decision: AuthorityDecision
    output: dict[str, Any] = Field(default_factory=dict)
    evidence: tuple[EvidenceRecord | dict[str, Any], ...] = ()
    verification: tuple[VerificationClaim | dict[str, Any], ...] = ()
    state_changes: tuple[StateChange | dict[str, Any], ...] = ()
    checkpoint: CheckpointRecord | None = None
    recovery: RecoveryRecord | None = None
    resource_usage: ResourceUsage | None = None
    failure: FailureRecord | dict[str, Any] | None = None
    integrity: IntegrityRecord | None = None
    started_at: datetime | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionAdapter:
    """Boundary implemented independently by each intelligence runtime."""

    def authorize(self, envelope: ExecutionEnvelope) -> AuthorityDecision:
        raise NotImplementedError

    def execute(self, envelope: ExecutionEnvelope) -> ExecutionReceipt:
        raise NotImplementedError
