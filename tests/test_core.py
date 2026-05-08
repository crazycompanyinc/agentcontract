from agentcontract.core.models import AgentIdentity, IntentDeclaration, WitnessRecord


def test_agent_trust_is_clamped():
    assert AgentIdentity("a", trust_score=2).trust_score == 1.0
    assert AgentIdentity("a", trust_score=-1).trust_score == 0.0


def test_witness_score_is_clamped():
    assert WitnessRecord("i", "x", 9).compliance_score == 1.0


def test_intent_resources_include_target_and_impact():
    intent = IntentDeclaration("a", "modify", "auth/a.py", "change", ["auth/b.py"])
    assert intent.resources() == ["auth/a.py", "auth/b.py"]


def test_db_round_trips_agent(protocol):
    agent = protocol.register_agent("agent-x", "tester", ["test"], ["tests/"], 0.6)
    loaded = protocol.db.get_agent(agent.agent_id)
    assert loaded == agent


def test_db_lists_saved_intents(registered):
    result = registered.propose_intent("agent-a", "modify", "auth/config.py", "change config")
    assert result.intent in registered.db.list_intents()
