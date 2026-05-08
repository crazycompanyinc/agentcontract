"""Action witness recording and trust updates."""

from __future__ import annotations

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import WitnessRecord
from agentcontract.intent.registry import IntentRegistry
from agentcontract.witness.compliance import ComplianceChecker


class ActionVerifier:
    """Records observed actions and updates agent trust scores."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db
        self.registry = IntentRegistry(db)
        self.checker = ComplianceChecker()

    def witness(self, intent_id: str, actual_action: str, compliance_score: float | None = None) -> WitnessRecord:
        intent = self.registry.get(intent_id)
        if compliance_score is None:
            compliance_score, deviation = self.checker.score(intent, actual_action)
        else:
            compliance_score = max(0.0, min(1.0, compliance_score))
            deviation = None if compliance_score >= 0.8 else "manual compliance score below preferred threshold"
        witness = WitnessRecord(
            intent_id=intent_id,
            actual_action=actual_action,
            compliance_score=compliance_score,
            deviation_details=deviation,
        )
        self.db.save_witness(witness)
        self.registry.set_status(intent_id, "completed" if compliance_score >= 0.5 else "failed")
        self._update_trust(intent.agent_id, compliance_score)
        return witness

    def _update_trust(self, agent_id: str, compliance_score: float) -> None:
        agent = self.db.get_agent(agent_id)
        if agent is None:
            return
        # Exponential moving average: history matters, recent witnessed behavior still moves the score.
        agent.trust_score = round((agent.trust_score * 0.8) + (compliance_score * 0.2), 3)
        self.db.save_agent(agent)
