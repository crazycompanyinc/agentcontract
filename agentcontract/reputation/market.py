"""Multi-dimensional agent reputation market."""

from __future__ import annotations

from agentcontract.audit.trail import AuditTrail
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import ReputationRating


class ReputationMarket:
    """Allows agents to rate collaborators across quality, speed, communication, and reliability."""

    dimensions = ("quality", "speed", "communication", "reliability")

    def __init__(self, db: AgentContractDB, audit: AuditTrail | None = None) -> None:
        self.db = db
        self.audit = audit or AuditTrail(db)

    def rate(
        self,
        rater_id: str,
        subject_id: str,
        collaboration_id: str,
        quality: float,
        speed: float,
        communication: float,
        reliability: float,
        notes: str = "",
    ) -> ReputationRating:
        for agent_id in (rater_id, subject_id):
            if self.db.get_agent(agent_id) is None:
                raise KeyError(f"Unknown agent: {agent_id}")
        rating = ReputationRating(rater_id, subject_id, collaboration_id, quality, speed, communication, reliability, notes)
        self.db.save_reputation_rating(rating)
        self.audit.record("reputation.rated", rater_id, "agent", subject_id, rating.to_dict())
        return rating

    def scorecard(self, subject_id: str) -> dict[str, object]:
        ratings = self.db.list_reputation_ratings(subject_id)
        if not ratings:
            return {"agent_id": subject_id, "rating_count": 0, "overall": None, "dimensions": {}}
        dimensions = {
            name: round(sum(getattr(rating, name) for rating in ratings) / len(ratings), 3)
            for name in self.dimensions
        }
        overall = round(sum(dimensions.values()) / len(dimensions), 3)
        return {"agent_id": subject_id, "rating_count": len(ratings), "overall": overall, "dimensions": dimensions}
