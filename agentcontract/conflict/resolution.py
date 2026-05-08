"""Deterministic conflict resolution rules."""

from __future__ import annotations

from dataclasses import dataclass

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import AgentIdentity, ConflictRecord, IntentDeclaration, utc_now


@dataclass(slots=True)
class ResolutionDecision:
    winner: str | None
    reason: str
    details: dict[str, object]


class ResolutionProtocol:
    """Applies scope, trust, temporal, and impact minimization rules."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db

    def arbitrate(self, conflict: ConflictRecord) -> ConflictRecord:
        intents = [self._intent(intent_id) for intent_id in conflict.involved_intents]
        agents = {intent.agent_id: self._agent(intent.agent_id) for intent in intents}
        decision = self.decide(conflict, intents, agents)
        conflict.resolution = "arbitrated" if decision.winner else "escalated"
        conflict.resolution_details = decision.details | {"reason": decision.reason, "winner": decision.winner}
        conflict.resolved_at = utc_now()
        self.db.save_conflict(conflict)

        if decision.winner:
            for intent in intents:
                if intent.agent_id == decision.winner:
                    intent.status = "approved"
                    intent.approved_at = utc_now()
                else:
                    intent.status = "cancelled"
                    intent.completed_at = utc_now()
                self.db.save_intent(intent)
        return conflict

    def decide(
        self,
        conflict: ConflictRecord,
        intents: list[IntentDeclaration],
        agents: dict[str, AgentIdentity],
    ) -> ResolutionDecision:
        resource = _common_resource(intents)
        scoped = [intent for intent in intents if _agent_owns(agents[intent.agent_id], resource)]
        if len(scoped) == 1:
            winner = scoped[0].agent_id
            return ResolutionDecision(winner, "scope priority", {"resource": resource})

        ranked = sorted(intents, key=lambda intent: agents[intent.agent_id].trust_score, reverse=True)
        if len(ranked) >= 2:
            top = agents[ranked[0].agent_id].trust_score
            second = agents[ranked[1].agent_id].trust_score
            if top - second >= 0.2:
                return ResolutionDecision(ranked[0].agent_id, "trust priority", {"trust_scores": _trusts(agents)})

        earliest = sorted(intents, key=lambda intent: intent.proposed_at)[0]
        if len({intent.proposed_at for intent in intents}) > 1:
            return ResolutionDecision(earliest.agent_id, "temporal priority", {"proposed_at": {i.agent_id: i.proposed_at for i in intents}})

        smallest = sorted(intents, key=lambda intent: len(intent.impact_scope))[0]
        if len({len(intent.impact_scope) for intent in intents}) > 1:
            return ResolutionDecision(smallest.agent_id, "impact minimization", {"impact_sizes": {i.agent_id: len(i.impact_scope) for i in intents}})

        return ResolutionDecision(None, "no deterministic winner", {"resource": resource, "conflict_type": conflict.conflict_type})

    def _agent(self, agent_id: str) -> AgentIdentity:
        agent = self.db.get_agent(agent_id)
        if agent is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        return agent

    def _intent(self, intent_id: str) -> IntentDeclaration:
        intent = self.db.get_intent(intent_id)
        if intent is None:
            raise KeyError(f"Unknown intent: {intent_id}")
        return intent


def _common_resource(intents: list[IntentDeclaration]) -> str:
    resources = [resource.rstrip("/") for intent in intents for resource in intent.resources()]
    shortest = sorted(resources, key=len)[0]
    return shortest


def _agent_owns(agent: AgentIdentity, resource: str) -> bool:
    normalized = resource.rstrip("/")
    for scope in agent.scope:
        owned = scope.rstrip("/")
        if normalized == owned or normalized.startswith(owned + "/"):
            return True
    return False


def _trusts(agents: dict[str, AgentIdentity]) -> dict[str, float]:
    return {agent_id: agent.trust_score for agent_id, agent in agents.items()}
