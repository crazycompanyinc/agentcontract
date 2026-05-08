"""Subscription matching for intent notifications."""

from __future__ import annotations

from fnmatch import fnmatch

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import IntentDeclaration, new_id


class SubscriptionManager:
    """Allows agents to subscribe to targets or glob patterns."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db

    def subscribe(self, agent_id: str, pattern: str) -> str:
        subscription_id = new_id("sub")
        self.db.add_subscription(subscription_id, agent_id, pattern)
        return subscription_id

    def subscribers_for(self, intent: IntentDeclaration) -> list[str]:
        subscribers: set[str] = set()
        for sub in self.db.list_subscriptions():
            pattern = sub["pattern"]
            if any(_matches(pattern, resource) for resource in intent.resources()):
                subscribers.add(sub["agent_id"])
        return sorted(subscribers)


def _matches(pattern: str, resource: str) -> bool:
    normalized_pattern = pattern.rstrip("/")
    normalized_resource = resource.rstrip("/")
    return (
        fnmatch(normalized_resource, pattern)
        or normalized_resource == normalized_pattern
        or normalized_resource.startswith(normalized_pattern + "/")
    )
