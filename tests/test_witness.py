def test_compliance_scores_matching_action_high(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/config.py", "modify auth config")
    witness = registered.witness(result.intent.intent_id, "modify completed for auth/config.py: modify auth config")
    assert witness.compliance_score >= 0.8


def test_low_compliance_marks_intent_failed(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/config.py", "modify auth config")
    registered.witness(result.intent.intent_id, "unrelated work elsewhere", 0.1)
    assert registered.registry.get(result.intent.intent_id).status == "failed"


def test_trust_updates_from_witness(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/config.py", "modify auth config")
    before = registered.db.get_agent("agent-a").trust_score
    registered.witness(result.intent.intent_id, "modify completed for auth/config.py: modify auth config", 1.0)
    after = registered.db.get_agent("agent-a").trust_score
    assert after > before


def test_manual_compliance_records_deviation(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/config.py", "modify auth config")
    witness = registered.witness(result.intent.intent_id, "partial work", 0.4)
    assert witness.deviation_details
