"""Agent responsiveness and reliability monitoring."""

from __future__ import annotations

from agentcontract.audit.trail import AuditTrail
from agentcontract.core.db import AgentContractDB


class HealthMonitor:
    """Calculates agent health from messages, intents, witnesses, and trust."""

    def __init__(self, db: AgentContractDB, audit: AuditTrail | None = None) -> None:
        self.db = db
        self.audit = audit or AuditTrail(db)

    def report(self, agent_id: str) -> dict[str, object]:
        agent = self.db.get_agent(agent_id)
        if agent is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        intents = [intent for intent in self.db.list_intents() if intent.agent_id == agent_id]
        completed = [intent for intent in intents if intent.status == "completed"]
        terminal = [intent for intent in intents if intent.status in {"completed", "failed", "cancelled"}]
        witnesses = [w for w in self.db.list_witnesses() if self.db.get_intent(w.intent_id) and self.db.get_intent(w.intent_id).agent_id == agent_id]
        inbound = [m for m in self.db.list_messages() if m.recipient_id == agent_id]
        acked = [m for m in inbound if m.status == "acked"]
        dead = [m for m in inbound if m.status == "dead_lettered"]
        completion_rate = len(completed) / len(terminal) if terminal else 1.0
        compliance_rate = sum(w.compliance_score for w in witnesses) / len(witnesses) if witnesses else agent.trust_score
        responsiveness = len(acked) / len(inbound) if inbound else 1.0
        health_score = round((completion_rate + compliance_rate + responsiveness + agent.trust_score) / 4, 3)
        flags = []
        if health_score < 0.5:
            flags.append("unhealthy")
        if dead:
            flags.append("dead_letters")
        report = {
            "agent_id": agent_id,
            "health_score": health_score,
            "completion_rate": round(completion_rate, 3),
            "compliance_rate": round(compliance_rate, 3),
            "responsiveness": round(responsiveness, 3),
            "flags": flags,
        }
        self.audit.record("health.checked", "system", "agent", agent_id, report)
        return report

    def unhealthy(self, threshold: float = 0.5) -> list[dict[str, object]]:
        return [report for agent in self.db.list_agents() if (report := self.report(agent.agent_id))["health_score"] < threshold]
