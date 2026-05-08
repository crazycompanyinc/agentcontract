"""Core AgentContract protocol state machine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentcontract.conflict.detector import ConflictDetector
from agentcontract.conflict.negotiation import NegotiationEngine
from agentcontract.conflict.resolution import ResolutionProtocol
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import AgentIdentity, ContractAgreement, ConflictRecord, IntentDeclaration, IntentType, WitnessRecord
from agentcontract.intent.publisher import IntentPublisher
from agentcontract.intent.registry import IntentRegistry
from agentcontract.witness.verifier import ActionVerifier


@dataclass(slots=True)
class ProtocolResult:
    state: str
    intent: IntentDeclaration
    conflicts: list[ConflictRecord]
    agreement: ContractAgreement | None = None
    message: str = ""


class AgentContractProtocol:
    """Deterministic state machine for proposing, checking, resolving, and witnessing intent."""

    def __init__(self, db_path: str | Path | None = None, db: AgentContractDB | None = None) -> None:
        self.db = db or AgentContractDB(db_path)
        self.publisher = IntentPublisher(self.db)
        self.registry = IntentRegistry(self.db)
        self.detector = ConflictDetector(self.db)
        self.negotiation = NegotiationEngine(self.db)
        self.resolution = ResolutionProtocol(self.db)
        self.verifier = ActionVerifier(self.db)

    def register_agent(
        self,
        agent_id: str,
        agent_type: str = "general",
        capabilities: list[str] | None = None,
        scope: list[str] | None = None,
        trust_score: float = 0.5,
    ) -> AgentIdentity:
        if not agent_id.strip():
            raise ValueError("agent_id cannot be empty")
        agent = AgentIdentity(
            agent_id=agent_id,
            agent_type=agent_type,
            capabilities=capabilities or [],
            scope=scope or [],
            trust_score=trust_score,
        )
        return self.db.save_agent(agent)

    def propose_intent(
        self,
        agent_id: str,
        intent_type: IntentType,
        target: str,
        description: str,
        impact_scope: list[str] | None = None,
        estimated_duration: str | None = None,
        dependencies: list[str] | None = None,
        auto_arbitrate: bool = False,
    ) -> ProtocolResult:
        if self.db.get_agent(agent_id) is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        intent = self.publisher.publish(agent_id, intent_type, target, description, impact_scope, estimated_duration, dependencies)
        conflicts = self.detector.detect_for(intent)
        if not conflicts:
            intent = self.registry.set_status(intent.intent_id, "approved")
            return ProtocolResult("APPROVE", intent, [], message="No conflicts detected; intent approved.")
        for conflict in conflicts:
            self.negotiation.open_session(conflict)
            if auto_arbitrate:
                self.resolution.arbitrate(conflict)
        state = "ARBITRATE" if auto_arbitrate else "NEGOTIATE"
        return ProtocolResult(state, self.registry.get(intent.intent_id), conflicts, message=f"{len(conflicts)} conflict(s) detected.")

    def negotiate(self, conflict_id: str, agent_id: str, offer_text: str) -> dict[str, Any]:
        session = self.negotiation.submit_offer(conflict_id, agent_id, offer_text)
        conflict = self.db.get_conflict(conflict_id)
        return {"session": session.to_dict(), "conflict": conflict.to_dict() if conflict else None}

    def create_agreement(self, conflict_id: str, terms: dict[str, object]) -> ContractAgreement:
        conflict = self._conflict(conflict_id)
        return self.negotiation.create_agreement(conflict, terms)

    def arbitrate(self, conflict_id: str) -> ConflictRecord:
        return self.resolution.arbitrate(self._conflict(conflict_id))

    def witness(self, intent_id: str, actual_action: str, compliance_score: float | None = None) -> WitnessRecord:
        return self.verifier.witness(intent_id, actual_action, compliance_score)

    def ledger(self) -> dict[str, Any]:
        return {
            "agents": [item.to_dict() for item in self.db.list_agents()],
            "intents": [item.to_dict() for item in self.db.list_intents()],
            "conflicts": [item.to_dict() for item in self.db.list_conflicts()],
            "contracts": [item.to_dict() for item in self.db.list_contracts()],
            "witnesses": [item.to_dict() for item in self.db.list_witnesses()],
        }

    def _conflict(self, conflict_id: str) -> ConflictRecord:
        conflict = self.db.get_conflict(conflict_id)
        if conflict is None:
            raise KeyError(f"Unknown conflict: {conflict_id}")
        return conflict
