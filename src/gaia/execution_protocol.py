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


class ExecutionEnvelope(BaseModel):
    """System-neutral contract for exposing execution without prescribing cognition."""

    model_config = ConfigDict(frozen=True)

    protocol_version: str = "1.0"
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    system_id: str
    system_kind: str
    mission_id: str | None = None
    capability: str
    intent: dict[str, Any] = Field(default_factory=dict)
    authority: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    state_refs: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol_version: str = "1.0"
    execution_id: str
    system_id: str
    status: ExecutionStatus
    authority_decision: AuthorityDecision
    output: dict[str, Any] = Field(default_factory=dict)
    evidence: tuple[dict[str, Any], ...] = ()
    verification: tuple[dict[str, Any], ...] = ()
    state_changes: tuple[dict[str, Any], ...] = ()
    failure: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionAdapter:
    """Boundary implemented by each autonomous intelligence runtime."""

    def authorize(self, envelope: ExecutionEnvelope) -> AuthorityDecision:
        raise NotImplementedError

    def execute(self, envelope: ExecutionEnvelope) -> ExecutionReceipt:
        raise NotImplementedError
