"""Deterministic conflict detection for active intents."""

from __future__ import annotations

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import ConflictRecord, IntentDeclaration
from agentcontract.intent.registry import IntentRegistry


class ConflictDetector:
    """Detects resource contention, scope overlap, and dependency clashes."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db
        self.registry = IntentRegistry(db)

    def detect_for(self, intent: IntentDeclaration) -> list[ConflictRecord]:
        conflicts: list[ConflictRecord] = []
        for other in self.registry.active():
            if other.intent_id == intent.intent_id or other.agent_id == intent.agent_id:
                continue
            conflict_type = self._classify(intent, other)
            if conflict_type is None:
                continue
            existing = self._existing_pending(intent.intent_id, other.intent_id)
            if existing:
                conflicts.append(existing)
                continue
            conflict = ConflictRecord(
                conflict_type=conflict_type,
                involved_agents=sorted({intent.agent_id, other.agent_id}),
                involved_intents=sorted([intent.intent_id, other.intent_id]),
                description=f"{intent.agent_id} {intent.intent_type} on {intent.target} overlaps with {other.agent_id} {other.intent_type} on {other.target}.",
            )
            conflicts.append(self.db.save_conflict(conflict))
        return conflicts

    def _classify(self, left: IntentDeclaration, right: IntentDeclaration) -> str | None:
        if set(left.dependencies).intersection(right.dependencies):
            return "dependency_clash"
        for left_resource in left.resources():
            for right_resource in right.resources():
                if _same_or_nested(left_resource, right_resource):
                    if left_resource.rstrip("/") == right_resource.rstrip("/"):
                        return "resource_contention"
                    return "scope_overlap"
        return None

    def _existing_pending(self, left_id: str, right_id: str) -> ConflictRecord | None:
        target = sorted([left_id, right_id])
        for conflict in self.db.list_conflicts(unresolved_only=True):
            if sorted(conflict.involved_intents) == target:
                return conflict
        return None


def _same_or_nested(left: str, right: str) -> bool:
    a = left.rstrip("/")
    b = right.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")
