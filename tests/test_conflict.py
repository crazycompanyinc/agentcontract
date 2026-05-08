def test_scope_overlap_conflict_detected(registered):
    registered.propose_intent("agent-a", "modify", "auth/", "change auth")
    result = registered.propose_intent("agent-c", "modify", "auth/tokens.py", "change tokens")
    assert result.state == "NEGOTIATE"
    assert result.conflicts[0].conflict_type == "scope_overlap"


def test_resource_contention_detected(registered):
    registered.propose_intent("agent-a", "modify", "auth/tokens.py", "change auth")
    result = registered.propose_intent("agent-c", "modify", "auth/tokens.py", "change tokens")
    assert result.conflicts[0].conflict_type == "resource_contention"


def test_negotiation_acceptance_creates_contract(registered):
    registered.propose_intent("agent-a", "modify", "auth/", "change auth")
    result = registered.propose_intent("agent-c", "modify", "auth/tokens.py", "change tokens")
    conflict_id = result.conflicts[0].conflict_id
    registered.negotiate(conflict_id, "agent-a", "accept system compromise")
    response = registered.negotiate(conflict_id, "agent-c", "agree to partition")
    assert response["session"]["status"] == "accepted"
    assert registered.db.list_contracts()[0].status == "agreed"


def test_scope_priority_wins_arbitration(registered):
    registered.propose_intent("agent-a", "modify", "checkout/payment.py", "change payment")
    result = registered.propose_intent("agent-b", "refactor", "checkout/", "redesign checkout")
    resolved = registered.arbitrate(result.conflicts[0].conflict_id)
    assert resolved.resolution_details["winner"] == "agent-b"
    assert resolved.resolution_details["reason"] == "scope priority"


def test_temporal_priority_applies_when_no_scope_or_trust_gap(protocol):
    protocol.register_agent("a", trust_score=0.5)
    protocol.register_agent("b", trust_score=0.55)
    first = protocol.propose_intent("a", "modify", "shared.py", "first")
    second = protocol.propose_intent("b", "modify", "shared.py", "second")
    resolved = protocol.arbitrate(second.conflicts[0].conflict_id)
    assert resolved.resolution_details["winner"] == first.intent.agent_id


def test_deadlock_expires_after_three_rounds(registered):
    registered.propose_intent("agent-a", "modify", "auth/", "change auth")
    result = registered.propose_intent("agent-c", "modify", "auth/tokens.py", "change tokens")
    conflict_id = result.conflicts[0].conflict_id
    for _ in range(3):
        registered.negotiate(conflict_id, "agent-a", "no")
        session = registered.negotiate(conflict_id, "agent-c", "no")
    assert session["session"]["status"] == "expired"
