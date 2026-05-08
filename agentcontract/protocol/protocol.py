"""Core AgentContract protocol state machine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentcontract.audit.trail import AuditTrail
from agentcontract.conflict.advanced_negotiation import AdvancedNegotiationEngine
from agentcontract.conflict.detector import ConflictDetector
from agentcontract.conflict.negotiation import NegotiationEngine
from agentcontract.conflict.resolution import ResolutionProtocol
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import AgentIdentity, ContractAgreement, ConflictRecord, IntentDeclaration, IntentType, WitnessRecord
from agentcontract.discovery.capabilities import CapabilityDirectory
from agentcontract.health.monitor import HealthMonitor
from agentcontract.intent.publisher import IntentPublisher
from agentcontract.intent.registry import IntentRegistry
from agentcontract.queue.sqlite_queue import MessageQueue
from agentcontract.reputation.market import ReputationMarket
from agentcontract.scheduling.dependencies import DependencyGraph
from agentcontract.scheduling.prediction import ConflictPredictor
from agentcontract.teams.manager import TeamManager
from agentcontract.templates.contracts import ContractTemplates
from agentcontract.templates.intents import IntentTemplates
from agentcontract.webhooks.manager import WebhookManager
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
        self.audit = AuditTrail(self.db)
        self.publisher = IntentPublisher(self.db)
        self.registry = IntentRegistry(self.db)
        self.detector = ConflictDetector(self.db)
        self.negotiation = NegotiationEngine(self.db)
        self.advanced_negotiation = AdvancedNegotiationEngine(self.db, self.audit)
        self.resolution = ResolutionProtocol(self.db)
        self.verifier = ActionVerifier(self.db)
        self.queue = MessageQueue(self.db, self.audit)
        self.discovery = CapabilityDirectory(self.db, self.audit)
        self.intent_templates = IntentTemplates()
        self.contract_templates = ContractTemplates()
        self.dependencies = DependencyGraph(self.db)
        self.conflict_predictor = ConflictPredictor(self.db)
        self.teams = TeamManager(self.db, self.audit)
        self.health = HealthMonitor(self.db, self.audit)
        self.webhooks = WebhookManager(self.db, self.audit)
        self.reputation = ReputationMarket(self.db, self.audit)

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
        saved = self.db.save_agent(agent)
        self.audit.record("agent.registered", agent_id, "agent", agent_id, {"agent_type": agent_type, "capabilities": capabilities or [], "scope": scope or []})
        for capability in capabilities or []:
            self.discovery.advertise(agent_id, capability, scope=scope or [], confidence=trust_score)
        return saved

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
        self.audit.record("intent.proposed", agent_id, "intent", intent.intent_id, intent.to_dict())
        conflicts = self.detector.detect_for(intent)
        if not conflicts:
            intent = self.registry.set_status(intent.intent_id, "approved")
            self.audit.record("intent.status_changed", "system", "intent", intent.intent_id, {"status": "approved"})
            return ProtocolResult("APPROVE", intent, [], message="No conflicts detected; intent approved.")
        for conflict in conflicts:
            self.audit.record("conflict.detected", "system", "conflict", conflict.conflict_id, conflict.to_dict())
            self.webhooks.emit("conflict.detected", conflict.to_dict())
            self.negotiation.open_session(conflict)
            if auto_arbitrate:
                self.resolution.arbitrate(conflict)
        state = "ARBITRATE" if auto_arbitrate else "NEGOTIATE"
        return ProtocolResult(state, self.registry.get(intent.intent_id), conflicts, message=f"{len(conflicts)} conflict(s) detected.")

    def negotiate(self, conflict_id: str, agent_id: str, offer_text: str) -> dict[str, Any]:
        session = self.negotiation.submit_offer(conflict_id, agent_id, offer_text)
        self.audit.record("negotiation.updated", agent_id, "conflict", conflict_id, {"offer_text": offer_text, "status": session.status})
        conflict = self.db.get_conflict(conflict_id)
        return {"session": session.to_dict(), "conflict": conflict.to_dict() if conflict else None}

    def create_agreement(self, conflict_id: str, terms: dict[str, object]) -> ContractAgreement:
        conflict = self._conflict(conflict_id)
        agreement = self.negotiation.create_agreement(conflict, terms)
        self.audit.record("contract.created", "system", "contract", agreement.agreement_id, agreement.to_dict())
        self.webhooks.emit("conflict.resolved", {"conflict_id": conflict_id, "agreement_id": agreement.agreement_id})
        return agreement

    def arbitrate(self, conflict_id: str) -> ConflictRecord:
        conflict = self.resolution.arbitrate(self._conflict(conflict_id))
        self.audit.record("conflict.resolved", "system", "conflict", conflict.conflict_id, conflict.to_dict())
        self.webhooks.emit("conflict.resolved", conflict.to_dict())
        return conflict

    def witness(self, intent_id: str, actual_action: str, compliance_score: float | None = None) -> WitnessRecord:
        record = self.verifier.witness(intent_id, actual_action, compliance_score)
        self.audit.record("witness.recorded", "system", "witness", record.witness_id, record.to_dict(), {"actual_action": actual_action})
        self.webhooks.emit("agent.status", {"intent_id": intent_id, "witness": record.to_dict()})
        return record

    def ledger(self) -> dict[str, Any]:
        return {
            "agents": [item.to_dict() for item in self.db.list_agents()],
            "intents": [item.to_dict() for item in self.db.list_intents()],
            "conflicts": [item.to_dict() for item in self.db.list_conflicts()],
            "contracts": [item.to_dict() for item in self.db.list_contracts()],
            "witnesses": [item.to_dict() for item in self.db.list_witnesses()],
        }

    def v2_ledger(self) -> dict[str, Any]:
        return {
            **self.ledger(),
            "messages": [item.to_dict() for item in self.db.list_messages()],
            "capabilities": [item.to_dict() for item in self.db.list_capabilities()],
            "teams": [item.to_dict() for item in self.db.list_teams()],
            "audit": [item.to_dict() for item in self.db.list_audit_events()],
            "reputation": [item.to_dict() for item in self.db.list_reputation_ratings()],
        }

    def _conflict(self, conflict_id: str) -> ConflictRecord:
        conflict = self.db.get_conflict(conflict_id)
        if conflict is None:
            raise KeyError(f"Unknown conflict: {conflict_id}")
        return conflict
