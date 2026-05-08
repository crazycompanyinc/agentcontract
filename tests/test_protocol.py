def test_ledger_contains_all_sections(registered):
    registered.propose_intent("agent-a", "modify", "auth/config.py", "change")
    ledger = registered.ledger()
    assert set(ledger) == {"agents", "intents", "conflicts", "contracts", "witnesses"}


def test_create_agreement_approves_conflicting_intents(registered):
    registered.propose_intent("agent-a", "modify", "auth/", "change auth")
    result = registered.propose_intent("agent-c", "modify", "auth/tokens.py", "change tokens")
    agreement = registered.create_agreement(result.conflicts[0].conflict_id, {"agent-a": "auth/", "agent-c": "tokens"})
    statuses = {registered.registry.get(intent_id).status for intent_id in agreement.intent_ids}
    assert statuses == {"approved"}


def test_auto_arbitrate_resolves_conflict(registered):
    registered.propose_intent("agent-a", "modify", "checkout/payment.py", "change payment")
    result = registered.propose_intent("agent-b", "refactor", "checkout/", "redesign", auto_arbitrate=True)
    assert result.state == "ARBITRATE"
    assert registered.db.list_conflicts()[0].resolution == "arbitrated"


def test_arbitration_cancels_loser(registered):
    first = registered.propose_intent("agent-a", "modify", "checkout/payment.py", "change payment")
    second = registered.propose_intent("agent-b", "refactor", "checkout/", "redesign")
    registered.arbitrate(second.conflicts[0].conflict_id)
    assert registered.registry.get(first.intent.intent_id).status == "cancelled"
