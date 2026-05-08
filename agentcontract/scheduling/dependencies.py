"""Dependency graph management for intents."""

from __future__ import annotations

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import IntentDeclaration
from agentcontract.intent.registry import IntentRegistry


class DependencyGraph:
    """Tracks intent dependencies and calculates runnable work."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db
        self.registry = IntentRegistry(db)

    def dependencies_for(self, intent_id: str) -> list[str]:
        return self.registry.get(intent_id).dependencies

    def dependents_of(self, intent_id: str) -> list[IntentDeclaration]:
        return [intent for intent in self.db.list_intents() if intent_id in intent.dependencies]

    def runnable(self) -> list[IntentDeclaration]:
        completed = {intent.intent_id for intent in self.db.list_intents() if intent.status == "completed"}
        runnable: list[IntentDeclaration] = []
        for intent in self.db.list_intents(["approved", "proposed"]):
            if all(dep in completed for dep in intent.dependencies):
                runnable.append(intent)
        return runnable

    def blocked(self) -> dict[str, list[str]]:
        completed = {intent.intent_id for intent in self.db.list_intents() if intent.status == "completed"}
        blocked: dict[str, list[str]] = {}
        for intent in self.db.list_intents(["approved", "proposed", "in_progress"]):
            missing = [dep for dep in intent.dependencies if dep not in completed]
            if missing:
                blocked[intent.intent_id] = missing
        return blocked

    def autoschedule(self) -> list[IntentDeclaration]:
        for intent in self.runnable():
            if intent.status == "proposed":
                self.registry.set_status(intent.intent_id, "approved")
        return self.runnable()

    def assert_acyclic(self) -> None:
        graph = {intent.intent_id: intent.dependencies for intent in self.db.list_intents()}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(intent_id: str) -> None:
            if intent_id in visiting:
                raise ValueError(f"Dependency cycle detected at {intent_id}")
            if intent_id in visited:
                return
            visiting.add(intent_id)
            for dep in graph.get(intent_id, []):
                visit(dep)
            visiting.remove(intent_id)
            visited.add(intent_id)

        for intent_id in graph:
            visit(intent_id)
