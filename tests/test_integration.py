import asyncio

import httpx
from click.testing import CliRunner

from agentcontract.cli import cli
from agentcontract.server.app import create_app


def test_cli_demo_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCONTRACT_DB", str(tmp_path / "demo.db"))
    result = CliRunner().invoke(cli, ["demo"])
    assert result.exit_code == 0, result.output
    assert "Agent Contract Ledger" in result.output
    assert "Resolution: arbitrated winner=felix-jim" in result.output


def test_cli_register_and_propose(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCONTRACT_DB", str(tmp_path / "cli.db"))
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    assert runner.invoke(cli, ["register", "a", "--scope", "src/", "--trust", "0.6"]).exit_code == 0
    result = runner.invoke(cli, ["propose", "--agent", "a", "--type", "modify", "--target", "src/app.py", "--description", "change app"])
    assert result.exit_code == 0
    assert "APPROVE" in result.output


def test_api_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCONTRACT_DB", str(tmp_path / "api.db"))
    asyncio.run(_api_flow())


async def _api_flow():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
        response = await client.post("/agents", json={"agent_id": "api-a", "scope": ["src/"], "trust_score": 0.6})
        assert response.status_code == 200
        response = await client.post("/intents", json={"agent_id": "api-a", "intent_type": "modify", "target": "src/app.py", "description": "change app"})
        assert response.status_code == 200
        intent_id = response.json()["intent"]["intent_id"]
        response = await client.post(f"/witness/{intent_id}", json={"actual_action": "modify completed for src/app.py: change app"})
        assert response.status_code == 200
        trust = await client.get("/agents/api-a/trust")
        assert trust.json()["trust_score"] > 0.6
