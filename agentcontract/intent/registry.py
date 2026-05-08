"""Intent registry backed by persistent storage."""

from __future__ import annotations

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import IntentDeclaration, utc_now

ACTIVE_STATUSES = ("proposed", "approved", "in_progress")


class IntentRegistry:
    """Stores and retrieves intent declarations."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db

    def add(self, intent: IntentDeclaration) -> IntentDeclaration:
        return self.db.save_intent(intent)

    def get(self, intent_id: str) -> IntentDeclaration:
        intent = self.db.get_intent(intent_id)
        if intent is None:
            raise KeyError(f"Unknown intent: {intent_id}")
        return intent

    def active(self) -> list[IntentDeclaration]:
        return self.db.list_intents(ACTIVE_STATUSES)

    def list(self) -> list[IntentDeclaration]:
        return self.db.list_intents()

    def set_status(self, intent_id: str, status: str) -> IntentDeclaration:
        intent = self.get(intent_id)
        intent.status = status  # type: ignore[assignment]
        if status == "approved":
            intent.approved_at = utc_now()
        if status in {"completed", "failed", "cancelled"}:
            intent.completed_at = utc_now()
        return self.db.save_intent(intent)
