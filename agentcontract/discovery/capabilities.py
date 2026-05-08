"""Dynamic service discovery for agent capabilities."""

from __future__ import annotations

from agentcontract.audit.trail import AuditTrail
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import CapabilityAdvertisement


class CapabilityDirectory:
    """Lets agents advertise capabilities and query who can perform work."""

    def __init__(self, db: AgentContractDB, audit: AuditTrail | None = None) -> None:
        self.db = db
        self.audit = audit or AuditTrail(db)

    def advertise(
        self,
        agent_id: str,
        capability: str,
        description: str = "",
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        scope: list[str] | None = None,
        confidence: float = 1.0,
    ) -> CapabilityAdvertisement:
        if self.db.get_agent(agent_id) is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        ad = CapabilityAdvertisement(agent_id, capability, description, inputs or [], outputs or [], scope or [], confidence)
        self.db.save_capability(ad)
        self.audit.record("capability.advertised", agent_id, "capability", ad.capability_id, {"capability": capability, "scope": scope or []})
        return ad

    def find(self, query: str, scope: str | None = None, min_confidence: float = 0.0) -> list[CapabilityAdvertisement]:
        query_terms = _terms(query)
        matches: list[tuple[float, CapabilityAdvertisement]] = []
        for ad in self.db.list_capabilities():
            if ad.confidence < min_confidence:
                continue
            text = " ".join([ad.capability, ad.description, *ad.inputs, *ad.outputs]).lower()
            score = sum(1 for term in query_terms if term in text)
            if query.lower() in text:
                score += 2
            if scope and ad.scope and not any(_same_or_nested(scope, item) for item in ad.scope):
                continue
            if score > 0:
                agent = self.db.get_agent(ad.agent_id)
                trust = agent.trust_score if agent else 0.0
                matches.append((score + ad.confidence + trust, ad))
        return [ad for _, ad in sorted(matches, key=lambda item: item[0], reverse=True)]


def _terms(text: str) -> list[str]:
    return [term for term in text.lower().replace("/", " ").replace("-", " ").split() if term]


def _same_or_nested(left: str, right: str) -> bool:
    a = left.rstrip("/")
    b = right.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")
