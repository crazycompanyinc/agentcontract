"""Intent declaration API."""

from __future__ import annotations

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import IntentDeclaration, IntentType
from agentcontract.intent.registry import IntentRegistry


class IntentPublisher:
    """Creates proposed intents before an agent acts."""

    def __init__(self, db: AgentContractDB) -> None:
        self.registry = IntentRegistry(db)

    def publish(
        self,
        agent_id: str,
        intent_type: IntentType,
        target: str,
        description: str,
        impact_scope: list[str] | None = None,
        estimated_duration: str | None = None,
        dependencies: list[str] | None = None,
    ) -> IntentDeclaration:
        if not target.strip():
            raise ValueError("Intent target cannot be empty")
        if not description.strip():
            raise ValueError("Intent description cannot be empty")
        intent = IntentDeclaration(
            agent_id=agent_id,
            intent_type=intent_type,
            target=target,
            description=description,
            impact_scope=impact_scope or [],
            estimated_duration=estimated_duration,
            dependencies=dependencies or [],
        )
        return self.registry.add(intent)
