"""Negotiation sessions and compromise creation."""

from __future__ import annotations

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import ContractAgreement, ConflictRecord, NegotiationSession, utc_now


class NegotiationEngine:
    """Facilitates bounded deterministic negotiations."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db

    def open_session(self, conflict: ConflictRecord) -> NegotiationSession:
        existing = self.db.get_negotiation_for_conflict(conflict.conflict_id)
        if existing:
            return existing
        session = NegotiationSession(conflict_id=conflict.conflict_id, participants=conflict.involved_agents)
        return self.db.save_negotiation(session)

    def suggest_compromise(self, conflict: ConflictRecord) -> dict[str, object]:
        intents = [self.db.get_intent(intent_id) for intent_id in conflict.involved_intents]
        loaded = [intent for intent in intents if intent is not None]
        assignments: dict[str, str] = {}
        for intent in sorted(loaded, key=lambda item: len(item.target)):
            assignments[intent.agent_id] = intent.target
        return {
            "strategy": "sequential_or_partitioned",
            "message": "Partition nested resources where possible; otherwise run sequentially in declaration order.",
            "assignments": assignments,
        }

    def submit_offer(self, conflict_id: str, agent_id: str, offer_text: str) -> NegotiationSession:
        conflict = self.db.get_conflict(conflict_id)
        if conflict is None:
            raise KeyError(f"Unknown conflict: {conflict_id}")
        session = self.open_session(conflict)
        if agent_id not in session.participants:
            raise ValueError(f"{agent_id} is not a participant in {conflict_id}")
        session.offers.append({"agent_id": agent_id, "offer_text": offer_text, "timestamp": utc_now()})
        if len(session.offers) >= len(session.participants):
            latest_agents = {offer["agent_id"] for offer in session.offers[-len(session.participants):]}
            if latest_agents == set(session.participants) and all(_accepts(offer["offer_text"]) for offer in session.offers[-len(session.participants):]):
                session.status = "accepted"
                session.resolved_at = utc_now()
                self._complete_conflict(conflict, session)
            elif len(session.offers) >= 3 * len(session.participants):
                session.status = "expired"
                session.resolved_at = utc_now()
        return self.db.save_negotiation(session)

    def create_agreement(self, conflict: ConflictRecord, terms: dict[str, object]) -> ContractAgreement:
        agreement = ContractAgreement(
            participants=conflict.involved_agents,
            intent_ids=conflict.involved_intents,
            terms=terms,
            status="agreed",
            resolved_at=utc_now(),
        )
        conflict.resolution = "negotiated"
        conflict.resolution_details = {"agreement_id": agreement.agreement_id, "terms": terms}
        conflict.resolved_at = utc_now()
        for intent_id in conflict.involved_intents:
            intent = self.db.get_intent(intent_id)
            if intent:
                intent.status = "approved"
                intent.approved_at = utc_now()
                self.db.save_intent(intent)
        self.db.save_conflict(conflict)
        return self.db.save_contract(agreement)

    def _complete_conflict(self, conflict: ConflictRecord, session: NegotiationSession) -> None:
        terms = self.suggest_compromise(conflict)
        terms["accepted_offers"] = session.offers
        self.create_agreement(conflict, terms)


def _accepts(text: str) -> bool:
    lowered = text.lower()
    return "accept" in lowered or "agree" in lowered
