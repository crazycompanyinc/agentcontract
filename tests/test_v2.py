import pytest

from agentcontract.core.models import ConflictRecord, IntentDeclaration


def test_message_queue_retries_and_dead_letters(registered):
    message = registered.queue.send("agent-a", "agent-b", "work", {"x": 1}, max_attempts=2)

    received = registered.queue.receive("agent-b", "work")[0]
    assert received.message_id == message.message_id
    failed = registered.queue.fail(received.message_id, "boom", retry_delay_seconds=0)
    assert failed.status == "queued"

    received = registered.queue.receive("agent-b", "work")[0]
    dead = registered.queue.fail(received.message_id, "boom again")
    assert dead.status == "dead_lettered"
    assert registered.queue.dead_letters("agent-b")[0].message_id == message.message_id


def test_message_queue_ack(registered):
    message = registered.queue.send("agent-a", "agent-b", "work", {"x": 1})
    received = registered.queue.receive("agent-b")[0]
    acked = registered.queue.ack(received.message_id)
    assert acked.status == "acked"


def test_capability_discovery(registered):
    matches = registered.discovery.find("modify auth", scope="auth/")
    assert matches
    assert {match.agent_id for match in matches} >= {"agent-a", "agent-c"}


def test_intent_templates_validate_required_fields():
    templates = __import__("agentcontract.templates", fromlist=["IntentTemplates"]).IntentTemplates()
    with pytest.raises(ValueError):
        templates.create("deploy", "agent-a", "prod", "deploy", {"artifact": "app"})
    intent = templates.create(
        "deploy",
        "agent-a",
        "prod",
        "deploy",
        {"environment": "prod", "artifact": "app", "rollback_plan": "revert"},
    )
    assert intent.intent_type == "deploy"


def test_dependency_graph_blocks_and_autoschedules(registered):
    first = registered.propose_intent("agent-a", "modify", "auth/a.py", "first").intent
    second = IntentDeclaration("agent-b", "modify", "billing/b.py", "second", dependencies=[first.intent_id])
    registered.db.save_intent(second)

    assert registered.dependencies.blocked()[second.intent_id] == [first.intent_id]
    registered.registry.set_status(first.intent_id, "completed")
    runnable = registered.dependencies.autoschedule()
    assert second.intent_id in {intent.intent_id for intent in runnable}
    assert registered.registry.get(second.intent_id).status == "approved"


def test_dependency_graph_detects_cycles(registered):
    first = IntentDeclaration("agent-a", "modify", "a.py", "a")
    second = IntentDeclaration("agent-b", "modify", "b.py", "b", dependencies=[first.intent_id])
    first.dependencies = [second.intent_id]
    registered.db.save_intent(first)
    registered.db.save_intent(second)
    with pytest.raises(ValueError):
        registered.dependencies.assert_acyclic()


def test_conflict_prediction_uses_history(registered):
    left = registered.propose_intent("agent-a", "modify", "auth/a.py", "a").intent
    right = registered.propose_intent("agent-b", "modify", "auth/a.py", "b").intent
    assert registered.conflict_predictor.predict(left, right)["probability"] == 1.0


def test_teams_and_contract_templates(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/a.py", "a")
    team = registered.teams.create("auth", ["agent-a", "agent-b"], ["auth/"])
    registered.teams.add_shared_intent(team.team_id, result.intent.intent_id)
    contract = registered.contract_templates.create(
        "code-review",
        ["agent-a", "agent-b"],
        [result.intent.intent_id],
        {"author": "agent-a", "reviewer": "agent-b", "approval_rule": "approve"},
    )
    saved = registered.db.save_contract(contract)
    updated = registered.teams.add_contract(team.team_id, saved.agreement_id)
    assert updated.shared_intents == [result.intent.intent_id]
    assert updated.contracts == [saved.agreement_id]


def test_audit_trail_records_core_actions(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/a.py", "a")
    events = registered.audit.query("intent", result.intent.intent_id)
    assert {event.action for event in events} >= {"intent.proposed", "intent.status_changed"}


def test_health_monitor_and_reputation(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/a.py", "a")
    registered.witness(result.intent.intent_id, "modify completed for auth/a.py: a", 1.0)
    registered.reputation.rate("agent-b", "agent-a", result.intent.intent_id, 0.8, 0.9, 0.7, 0.8)

    health = registered.health.report("agent-a")
    scorecard = registered.reputation.scorecard("agent-a")
    assert health["health_score"] > 0.5
    assert scorecard["overall"] == 0.8


def test_webhook_emit_records_pending_delivery(registered):
    registered.webhooks.subscribe("conflict.detected", "https://example.invalid/hook", "secret")
    deliveries = registered.webhooks.emit("conflict.detected", {"conflict_id": "c"})
    assert deliveries[0]["status"] == "pending"


def test_advanced_negotiation_escalates_after_round_limit(registered):
    conflict = ConflictRecord("scope_overlap", ["agent-a", "agent-b"], ["i1", "i2"], "conflict")
    registered.db.save_conflict(conflict)
    session = registered.advanced_negotiation.start(conflict.conflict_id, max_rounds=1)
    assert session.status == "ongoing"
    registered.advanced_negotiation.counter_offer(conflict.conflict_id, "agent-a", {"agent-a": "first"})
    expired = registered.advanced_negotiation.check_timeouts()
    assert expired[0].status == "expired"
    assert registered.db.get_conflict(conflict.conflict_id).resolution == "escalated"


def test_v2_ledger_keeps_expanded_sections(registered):
    ledger = registered.v2_ledger()
    assert {"messages", "capabilities", "teams", "audit", "reputation"} <= set(ledger)
