"""Domain models for AgentContract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

IntentType = Literal["modify", "create", "delete", "refactor", "review", "deploy", "test"]
IntentStatus = Literal["proposed", "approved", "in_progress", "completed", "failed", "cancelled"]
AgreementStatus = Literal["negotiating", "agreed", "violated", "completed"]
ConflictType = Literal["resource_contention", "dependency_clash", "scope_overlap", "timing_conflict"]
ConflictResolution = Literal["pending", "negotiated", "arbitrated", "escalated", "resolved"]
NegotiationStatus = Literal["ongoing", "accepted", "rejected", "expired"]


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    """Create a readable unique identifier."""
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass(slots=True)
class AgentIdentity:
    agent_id: str
    agent_type: str = "general"
    capabilities: list[str] = field(default_factory=list)
    scope: list[str] = field(default_factory=list)
    trust_score: float = 0.5
    registered_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.trust_score = max(0.0, min(1.0, float(self.trust_score)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentIdentity":
        return cls(**data)


@dataclass(slots=True)
class IntentDeclaration:
    agent_id: str
    intent_type: IntentType
    target: str
    description: str
    impact_scope: list[str] = field(default_factory=list)
    estimated_duration: str | None = None
    dependencies: list[str] = field(default_factory=list)
    status: IntentStatus = "proposed"
    intent_id: str = field(default_factory=lambda: new_id("intent"))
    proposed_at: str = field(default_factory=utc_now)
    approved_at: str | None = None
    completed_at: str | None = None

    def resources(self) -> list[str]:
        return [self.target, *self.impact_scope]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentDeclaration":
        return cls(**data)


@dataclass(slots=True)
class ContractAgreement:
    participants: list[str]
    intent_ids: list[str]
    terms: dict[str, Any]
    status: AgreementStatus = "negotiating"
    agreement_id: str = field(default_factory=lambda: new_id("agreement"))
    created_at: str = field(default_factory=utc_now)
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContractAgreement":
        return cls(**data)


@dataclass(slots=True)
class ConflictRecord:
    conflict_type: ConflictType
    involved_agents: list[str]
    involved_intents: list[str]
    description: str
    resolution: ConflictResolution = "pending"
    resolution_details: dict[str, Any] = field(default_factory=dict)
    conflict_id: str = field(default_factory=lambda: new_id("conflict"))
    detected_at: str = field(default_factory=utc_now)
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConflictRecord":
        return cls(**data)


@dataclass(slots=True)
class WitnessRecord:
    intent_id: str
    actual_action: str
    compliance_score: float
    deviation_details: str | None = None
    witness_id: str = field(default_factory=lambda: new_id("witness"))
    witnessed_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.compliance_score = max(0.0, min(1.0, float(self.compliance_score)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WitnessRecord":
        return cls(**data)


@dataclass(slots=True)
class NegotiationSession:
    conflict_id: str
    participants: list[str]
    offers: list[dict[str, Any]] = field(default_factory=list)
    status: NegotiationStatus = "ongoing"
    session_id: str = field(default_factory=lambda: new_id("session"))
    created_at: str = field(default_factory=utc_now)
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NegotiationSession":
        return cls(**data)
