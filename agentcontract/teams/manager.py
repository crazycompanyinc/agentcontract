"""Team-level scope, intents, and contracts."""

from __future__ import annotations

from agentcontract.audit.trail import AuditTrail
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import AgentTeam, new_id


class TeamManager:
    """Groups agents into teams with shared operating context."""

    def __init__(self, db: AgentContractDB, audit: AuditTrail | None = None) -> None:
        self.db = db
        self.audit = audit or AuditTrail(db)

    def create(self, name: str, members: list[str], scope: list[str] | None = None) -> AgentTeam:
        for agent_id in members:
            if self.db.get_agent(agent_id) is None:
                raise KeyError(f"Unknown agent: {agent_id}")
        team = AgentTeam(new_id("team"), name, members, scope or [])
        self.db.save_team(team)
        self.audit.record("team.created", "system", "team", team.team_id, {"members": members, "scope": scope or []})
        return team

    def add_shared_intent(self, team_id: str, intent_id: str) -> AgentTeam:
        team = self._team(team_id)
        if self.db.get_intent(intent_id) is None:
            raise KeyError(f"Unknown intent: {intent_id}")
        if intent_id not in team.shared_intents:
            team.shared_intents.append(intent_id)
        return self.db.save_team(team)

    def add_contract(self, team_id: str, agreement_id: str) -> AgentTeam:
        team = self._team(team_id)
        if agreement_id not in team.contracts:
            team.contracts.append(agreement_id)
        return self.db.save_team(team)

    def list(self) -> list[AgentTeam]:
        return self.db.list_teams()

    def _team(self, team_id: str) -> AgentTeam:
        team = self.db.get_team(team_id)
        if team is None:
            raise KeyError(f"Unknown team: {team_id}")
        return team
