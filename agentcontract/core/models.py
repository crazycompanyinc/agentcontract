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
MessageStatus = Literal["queued", "leased", "acked", "dead_lettered"]
AuditAction = Literal[
    "agent.registered",
    "intent.proposed",
    "intent.status_changed",
    "conflict.detected",
    "negotiation.updated",
    "contract.created",
    "witness.recorded",
    "queue.message_sent",
    "queue.message_acked",
    "queue.message_dead_lettered",
    "capability.advertised",
    "team.created",
    "reputation.rated",
    "health.checked",
    "webhook.delivered",
]


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


@dataclass(slots=True)
class QueuedMessage:
    sender_id: str
    recipient_id: str
    topic: str
    payload: dict[str, Any]
    message_id: str = field(default_factory=lambda: new_id("msg"))
    status: MessageStatus = "queued"
    attempt_count: int = 0
    max_attempts: int = 3
    visible_at: str = field(default_factory=utc_now)
    created_at: str = field(default_factory=utc_now)
    leased_until: str | None = None
    acked_at: str | None = None
    dead_lettered_at: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueuedMessage":
        return cls(**data)


@dataclass(slots=True)
class CapabilityAdvertisement:
    agent_id: str
    capability: str
    description: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    scope: list[str] = field(default_factory=list)
    confidence: float = 1.0
    advertised_at: str = field(default_factory=utc_now)
    capability_id: str = field(default_factory=lambda: new_id("cap"))

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityAdvertisement":
        return cls(**data)


@dataclass(slots=True)
class AgentTeam:
    team_id: str
    name: str
    members: list[str]
    scope: list[str] = field(default_factory=list)
    shared_intents: list[str] = field(default_factory=list)
    contracts: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTeam":
        return cls(**data)


@dataclass(slots=True)
class AuditEvent:
    action: str
    actor_id: str
    subject_type: str
    subject_id: str
    details: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("audit"))
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        return cls(**data)


@dataclass(slots=True)
class ReputationRating:
    rater_id: str
    subject_id: str
    collaboration_id: str
    quality: float
    speed: float
    communication: float
    reliability: float
    notes: str = ""
    rating_id: str = field(default_factory=lambda: new_id("rating"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for field_name in ("quality", "speed", "communication", "reliability"):
            setattr(self, field_name, max(0.0, min(1.0, float(getattr(self, field_name)))))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReputationRating":
        return cls(**data)
