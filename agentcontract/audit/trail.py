"""Tamper-evident audit event recording."""

from __future__ import annotations

from typing import Any

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import AuditEvent


class AuditTrail:
    """Records every material protocol action with evidence."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db

    def record(
        self,
        action: str,
        actor_id: str,
        subject_type: str,
        subject_id: str,
        details: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            action=action,
            actor_id=actor_id,
            subject_type=subject_type,
            subject_id=subject_id,
            details=details or {},
            evidence=evidence or {},
        )
        return self.db.save_audit_event(event)

    def query(self, subject_type: str | None = None, subject_id: str | None = None) -> list[AuditEvent]:
        return self.db.list_audit_events(subject_type, subject_id)
