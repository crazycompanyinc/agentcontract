"""Click CLI for AgentContract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from agentcontract.core.db import AgentContractDB, default_db_path
from agentcontract.protocol.protocol import AgentContractProtocol


def get_protocol() -> AgentContractProtocol:
    return AgentContractProtocol(db=AgentContractDB())


@click.group()
def cli() -> None:
    """AgentContract coordination CLI."""


@cli.command("init")
def init_cmd() -> None:
    db = AgentContractDB()
    click.echo(f"Initialized AgentContract at {db.path}")


@cli.command()
@click.argument("agent_id")
@click.option("--type", "agent_type", default="general", show_default=True)
@click.option("--capability", "capabilities", multiple=True)
@click.option("--scope", "scope", multiple=True)
@click.option("--trust", "trust_score", default=0.5, show_default=True, type=float)
def register(agent_id: str, agent_type: str, capabilities: tuple[str, ...], scope: tuple[str, ...], trust_score: float) -> None:
    agent = get_protocol().register_agent(agent_id, agent_type, list(capabilities), list(scope), trust_score)
    click.echo(f"Registered {agent.agent_id} ({agent.agent_type}) trust={agent.trust_score:.2f}")


@cli.command()
@click.option("--agent", "agent_id", required=True)
@click.option("--type", "intent_type", required=True)
@click.option("--target", required=True)
@click.option("--description", required=True)
@click.option("--impact", "impact_scope", multiple=True)
@click.option("--duration", "estimated_duration")
@click.option("--depends-on", "dependencies", multiple=True)
def propose(
    agent_id: str,
    intent_type: str,
    target: str,
    description: str,
    impact_scope: tuple[str, ...],
    estimated_duration: str | None,
    dependencies: tuple[str, ...],
) -> None:
    result = get_protocol().propose_intent(
        agent_id=agent_id,
        intent_type=intent_type,  # type: ignore[arg-type]
        target=target,
        description=description,
        impact_scope=list(impact_scope),
        estimated_duration=estimated_duration,
        dependencies=list(dependencies),
    )
    click.echo(f"{result.state}: {result.message}")
    click.echo(f"Intent {result.intent.intent_id}: {result.intent.status} {result.intent.agent_id} -> {result.intent.target}")
    for conflict in result.conflicts:
        click.echo(f"Conflict {conflict.conflict_id}: {conflict.conflict_type} {conflict.description}")


@cli.command()
def intents() -> None:
    for intent in get_protocol().db.list_intents():
        click.echo(f"{intent.intent_id} {intent.status:11} {intent.agent_id:24} {intent.intent_type:8} {intent.target} :: {intent.description}")


@cli.command()
def conflicts() -> None:
    for conflict in get_protocol().db.list_conflicts():
        click.echo(f"{conflict.conflict_id} {conflict.resolution:10} {conflict.conflict_type:20} agents={','.join(conflict.involved_agents)}")
        click.echo(f"  {conflict.description}")


@cli.command()
@click.option("--conflict", "conflict_id", required=True)
@click.option("--agent", "agent_id", required=True)
@click.option("--offer", "offer_text", default="accept system compromise", show_default=True)
def negotiate(conflict_id: str, agent_id: str, offer_text: str) -> None:
    result = get_protocol().negotiate(conflict_id, agent_id, offer_text)
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.option("--intent", "intent_id", required=True)
@click.option("--actual", "actual_action", default=None)
@click.option("--score", "compliance_score", type=float)
def witness(intent_id: str, actual_action: str | None, compliance_score: float | None) -> None:
    if actual_action is None:
        intent = get_protocol().registry.get(intent_id)
        actual_action = f"{intent.intent_type} completed for {intent.target}: {intent.description}"
    record = get_protocol().witness(intent_id, actual_action, compliance_score)
    click.echo(f"Witness {record.witness_id}: compliance={record.compliance_score:.2f}")
    if record.deviation_details:
        click.echo(f"Deviation: {record.deviation_details}")


@cli.command()
def agents() -> None:
    for agent in get_protocol().db.list_agents():
        click.echo(f"{agent.agent_id:24} type={agent.agent_type:14} trust={agent.trust_score:.3f} scope={','.join(agent.scope)}")


@cli.command()
def contracts() -> None:
    for agreement in get_protocol().db.list_contracts():
        click.echo(f"{agreement.agreement_id} {agreement.status:10} participants={','.join(agreement.participants)}")
        click.echo(f"  terms={json.dumps(agreement.terms, sort_keys=True)}")


@cli.command()
@click.option("--agent", "agent_id", required=True)
def trust(agent_id: str) -> None:
    agent = get_protocol().db.get_agent(agent_id)
    if agent is None:
        raise click.ClickException(f"Unknown agent: {agent_id}")
    click.echo(f"{agent.agent_id}: trust={agent.trust_score:.3f}")
    click.echo("Formula: new_trust = old_trust * 0.8 + compliance_score * 0.2")


@cli.command()
@click.option("--port", default=8000, show_default=True, type=int)
def serve(port: int) -> None:
    import uvicorn

    uvicorn.run("agentcontract.server.app:app", host="127.0.0.1", port=port, reload=False)


@cli.command()
def demo() -> None:
    db_path = default_db_path()
    protocol = AgentContractProtocol(db_path=db_path)
    protocol.db.clear()

    _banner("AgentContract Demo")
    click.echo(f"Ledger database: {Path(db_path)}")

    _banner("1. Register agents")
    for args in [
        ("felix-cto", "architect", ["architecture", "refactor"], ["architecture", "auth/"], 0.9),
        ("felix-contact-center", "domain-agent", ["modify", "test"], ["contact/"], 0.7),
        ("felix-jim", "checkout-agent", ["modify", "review"], ["checkout/"], 0.8),
        ("agent-alpha", "implementation-agent", ["modify", "test"], ["auth/"], 0.75),
    ]:
        agent = protocol.register_agent(*args)
        click.echo(f"{agent.agent_id:24} scope={','.join(agent.scope):22} trust={agent.trust_score:.2f}")

    _banner("2. Auth conflict")
    cto_auth = protocol.propose_intent("felix-cto", "refactor", "auth/", "Refactor auth module", ["auth/tokens.py", "auth/session.py"])
    alpha_auth = protocol.propose_intent("agent-alpha", "modify", "auth/tokens.py", "Update auth tokens")
    _print_result(cto_auth)
    _print_result(alpha_auth)
    auth_conflict = alpha_auth.conflicts[0]

    _banner("3. Negotiation")
    suggestion = protocol.negotiation.suggest_compromise(auth_conflict)
    click.echo(f"System suggestion: {suggestion['message']}")
    terms = {
        "felix-cto": "Own auth/ refactor except auth/tokens.py until agent-alpha completes.",
        "agent-alpha": "Own auth/tokens.py token update first, then hand back to felix-cto.",
        "strategy": "partitioned auth ownership",
    }
    agreement = protocol.create_agreement(auth_conflict.conflict_id, terms)
    click.echo(f"Contract {agreement.agreement_id} created: {agreement.status}")

    _banner("4. Checkout parallel work")
    alpha_checkout = protocol.propose_intent("agent-alpha", "modify", "checkout/payment.py", "Update checkout flow")
    jim_checkout = protocol.propose_intent("felix-jim", "refactor", "checkout/", "Redesign checkout UI", ["checkout/payment.py"])
    _print_result(alpha_checkout)
    _print_result(jim_checkout)
    checkout_conflict = jim_checkout.conflicts[0]

    _banner("5. Arbitration")
    resolved = protocol.arbitrate(checkout_conflict.conflict_id)
    click.echo(f"Resolution: {resolved.resolution} winner={resolved.resolution_details.get('winner')} reason={resolved.resolution_details.get('reason')}")
    jim_intent = protocol.registry.get(jim_checkout.intent.intent_id)
    jim_witness = protocol.witness(jim_intent.intent_id, f"{jim_intent.intent_type} completed for {jim_intent.target}: {jim_intent.description}")
    click.echo(f"Winner witnessed before redirect: {jim_intent.agent_id} compliance={jim_witness.compliance_score:.2f}")
    redirected = protocol.propose_intent("agent-alpha", "modify", "checkout/orders.py", "Redirected to update checkout orders status")
    _print_result(redirected)

    _banner("6. Witness")
    for intent in protocol.db.list_intents():
        if intent.status in {"approved", "in_progress"}:
            actual = f"{intent.intent_type} completed for {intent.target}: {intent.description}"
            witness_record = protocol.witness(intent.intent_id, actual)
            click.echo(f"{intent.agent_id:24} {intent.target:24} compliance={witness_record.compliance_score:.2f}")
    for existing in protocol.db.list_witnesses():
        witnessed_intent = protocol.db.get_intent(existing.intent_id)
        if witnessed_intent and witnessed_intent.agent_id == "felix-jim":
            click.echo(f"{witnessed_intent.agent_id:24} {witnessed_intent.target:24} compliance={existing.compliance_score:.2f} (already witnessed)")

    _banner("7. Trust scores")
    for agent in protocol.db.list_agents():
        click.echo(f"{agent.agent_id:24} trust={agent.trust_score:.3f}")

    _banner("8. AgentContract v2.0 queue and discovery")
    message = protocol.queue.send("felix-cto", "agent-alpha", "handoff.auth", {"intent_id": cto_auth.intent.intent_id, "next": "finish token update"})
    received = protocol.queue.receive("agent-alpha", "handoff.auth")[0]
    protocol.queue.ack(received.message_id)
    click.echo(f"Queued {message.message_id}: delivered to {received.recipient_id} topic={received.topic}")
    matches = protocol.discovery.find("who can refactor auth", scope="auth/")
    click.echo("Capability match: " + ", ".join(f"{match.agent_id}:{match.capability}" for match in matches[:3]))

    _banner("9. Templates, dependencies, teams")
    blocker = protocol.intent_templates.create(
        "refactor",
        "felix-cto",
        "auth/session.py",
        "Prepare session internals for bug fix",
        {"module": "auth/session.py", "risk_level": "medium"},
    )
    protocol.db.save_intent(blocker)
    template_intent = protocol.intent_templates.create(
        "bug-fix",
        "agent-alpha",
        "auth/session.py",
        "Fix session expiry bug",
        {"bug_id": "BUG-17", "reproduction_steps": "expired session reuses token", "expected_behavior": "force reauth"},
        dependencies=[blocker.intent_id],
    )
    protocol.db.save_intent(template_intent)
    click.echo(f"Template intent {template_intent.intent_id}: blocked_by={protocol.dependencies.blocked()[template_intent.intent_id]}")
    team = protocol.teams.create("auth-strike-team", ["felix-cto", "agent-alpha"], ["auth/"])
    protocol.teams.add_shared_intent(team.team_id, template_intent.intent_id)
    contract = protocol.contract_templates.create(
        "code-review",
        ["felix-cto", "agent-alpha"],
        [template_intent.intent_id],
        {"author": "agent-alpha", "reviewer": "felix-cto", "approval_rule": "one approval required"},
    )
    saved_contract = protocol.db.save_contract(contract)
    protocol.teams.add_contract(team.team_id, saved_contract.agreement_id)
    click.echo(f"Team {team.name}: shared_intents=1 contract={saved_contract.agreement_id}")

    _banner("10. Prediction, health, reputation, webhooks")
    prediction = protocol.conflict_predictor.predict(cto_auth.intent, alpha_auth.intent)
    click.echo(f"Prediction: {prediction['message']} confidence={prediction['confidence']}")
    protocol.reputation.rate("felix-cto", "agent-alpha", saved_contract.agreement_id, 0.9, 0.8, 0.85, 0.9)
    click.echo(f"Reputation: {json.dumps(protocol.reputation.scorecard('agent-alpha'), sort_keys=True)}")
    click.echo(f"Health: {json.dumps(protocol.health.report('agent-alpha'), sort_keys=True)}")
    protocol.webhooks.subscribe("conflict.detected", "https://example.invalid/agentcontract")
    pending = protocol.webhooks.emit("conflict.detected", {"conflict_id": auth_conflict.conflict_id})
    click.echo(f"Webhook deliveries queued: {len(pending)}")

    _banner("11. Agent Contract Ledger v2.0")
    click.echo(json.dumps(protocol.v2_ledger(), indent=2, sort_keys=True))


def _banner(text: str) -> None:
    click.echo("")
    click.echo(f"=== {text} ===")


def _print_result(result: Any) -> None:
    click.echo(f"{result.state}: {result.intent.agent_id} {result.intent.intent_type} {result.intent.target} [{result.intent.status}]")
    for conflict in result.conflicts:
        click.echo(f"  conflict={conflict.conflict_id} type={conflict.conflict_type} resolution={conflict.resolution}")


if __name__ == "__main__":
    cli()
