import pytest

from agentcontract.intent.subscriptions import SubscriptionManager


def test_unknown_agent_cannot_propose(protocol):
    with pytest.raises(KeyError):
        protocol.propose_intent("missing", "modify", "x.py", "change")


def test_non_conflicting_intent_is_approved(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/config.py", "change config")
    assert result.state == "APPROVE"
    assert result.intent.status == "approved"


def test_empty_target_rejected(registered):
    with pytest.raises(ValueError):
        registered.propose_intent("agent-a", "modify", "", "change")


def test_subscription_matches_nested_scope(registered):
    manager = SubscriptionManager(registered.db)
    manager.subscribe("agent-b", "auth/")
    result = registered.propose_intent("agent-a", "modify", "auth/tokens.py", "change tokens")
    assert manager.subscribers_for(result.intent) == ["agent-b"]


def test_registry_status_sets_approved_timestamp(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/config.py", "change config")
    assert result.intent.approved_at is not None
