"""Advanced multi-round negotiation with counter-offers and escalation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from agentcontract.audit.trail import AuditTrail
from agentcontract.conflict.negotiation import NegotiationEngine
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import NegotiationSession, utc_now


class AdvancedNegotiationEngine:
    """Adds structured rounds, counter-offers, compromise suggestions, and timeout escalation."""

    def __init__(self, db: AgentContractDB, audit: AuditTrail | None = None) -> None:
        self.db = db
        self.audit = audit or AuditTrail(db)
        self.basic = NegotiationEngine(db)

    def start(self, conflict_id: str, timeout_seconds: int = 300, max_rounds: int = 3) -> NegotiationSession:
        conflict = self.db.get_conflict(conflict_id)
        if conflict is None:
            raise KeyError(f"Unknown conflict: {conflict_id}")
        session = self.basic.open_session(conflict)
        session.offers.append(
            {
                "type": "system",
                "round": 0,
                "message": "advanced negotiation opened",
                "deadline": _now_plus(timeout_seconds),
                "max_rounds": max_rounds,
                "timestamp": utc_now(),
            }
        )
        self.audit.record("negotiation.updated", "system", "conflict", conflict_id, {"event": "advanced_started"})
        return self.db.save_negotiation(session)

    def counter_offer(self, conflict_id: str, agent_id: str, terms: dict[str, Any]) -> NegotiationSession:
        session = self._session(conflict_id)
        round_number = 1 + max((offer.get("round", 0) for offer in session.offers if isinstance(offer.get("round"), int)), default=0)
        session.offers.append({"type": "counter_offer", "agent_id": agent_id, "round": round_number, "terms": terms, "timestamp": utc_now()})
        self.audit.record("negotiation.updated", agent_id, "conflict", conflict_id, {"event": "counter_offer", "round": round_number})
        return self.db.save_negotiation(session)

    def compromise(self, conflict_id: str) -> dict[str, Any]:
        conflict = self.db.get_conflict(conflict_id)
        if conflict is None:
            raise KeyError(f"Unknown conflict: {conflict_id}")
        suggestion = self.basic.suggest_compromise(conflict)
        suggestion["escalation"] = "arbitrate if no participant accepts before deadline"
        return suggestion

    def check_timeouts(self) -> list[NegotiationSession]:
        expired: list[NegotiationSession] = []
        now = utc_now()
        for conflict in self.db.list_conflicts(unresolved_only=True):
            session = self.db.get_negotiation_for_conflict(conflict.conflict_id)
            if session is None or session.status != "ongoing":
                continue
            deadlines = [offer.get("deadline") for offer in session.offers if offer.get("deadline")]
            max_rounds = max((offer.get("max_rounds", 3) for offer in session.offers if isinstance(offer.get("max_rounds"), int)), default=3)
            rounds = [offer.get("round", 0) for offer in session.offers if isinstance(offer.get("round"), int)]
            if (deadlines and min(deadlines) <= now) or (rounds and max(rounds) >= max_rounds):
                session.status = "expired"
                session.resolved_at = utc_now()
                conflict.resolution = "escalated"
                conflict.resolution_details = {"reason": "negotiation timeout or max rounds reached", "session_id": session.session_id}
                conflict.resolved_at = utc_now()
                self.db.save_conflict(conflict)
                expired.append(self.db.save_negotiation(session))
        return expired

    def _session(self, conflict_id: str) -> NegotiationSession:
        session = self.db.get_negotiation_for_conflict(conflict_id)
        if session is None:
            return self.start(conflict_id)
        return session


def _now_plus(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
