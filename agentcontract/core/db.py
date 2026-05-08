"""SQLite storage for AgentContract."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from agentcontract.core.models import (
    AgentIdentity,
    ContractAgreement,
    ConflictRecord,
    IntentDeclaration,
    NegotiationSession,
    AuditEvent,
    CapabilityAdvertisement,
    AgentTeam,
    QueuedMessage,
    ReputationRating,
    WitnessRecord,
)


def default_db_path() -> Path:
    configured = os.getenv("AGENTCONTRACT_DB")
    if configured:
        return Path(configured)
    return Path.cwd() / ".agentcontract" / "agentcontract.db"


class AgentContractDB:
    """Small repository layer backed by SQLite with JSON encoded model payloads."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS intents (
                    intent_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_intents_status ON intents(status);
                CREATE TABLE IF NOT EXISTS conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    resolution TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conflicts_resolution ON conflicts(resolution);
                CREATE TABLE IF NOT EXISTS contracts (
                    agreement_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS witnesses (
                    witness_id TEXT PRIMARY KEY,
                    intent_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS negotiations (
                    session_id TEXT PRIMARY KEY,
                    conflict_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    pattern TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS message_queue (
                    message_id TEXT PRIMARY KEY,
                    recipient_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    visible_at TEXT NOT NULL,
                    leased_until TEXT,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_message_queue_delivery
                    ON message_queue(recipient_id, topic, status, visible_at);
                CREATE TABLE IF NOT EXISTS capabilities (
                    capability_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_capabilities_name ON capabilities(capability);
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_subject ON audit_events(subject_type, subject_id);
                CREATE TABLE IF NOT EXISTS reputation_ratings (
                    rating_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    rater_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_reputation_subject ON reputation_ratings(subject_id);
                CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                    webhook_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    secret TEXT,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    webhook_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def clear(self) -> None:
        with self.connect() as conn:
            for table in [
                "webhook_deliveries",
                "webhook_subscriptions",
                "reputation_ratings",
                "audit_events",
                "teams",
                "capabilities",
                "message_queue",
                "subscriptions",
                "negotiations",
                "witnesses",
                "contracts",
                "conflicts",
                "intents",
                "agents",
            ]:
                conn.execute(f"DELETE FROM {table}")

    def save_agent(self, agent: AgentIdentity) -> AgentIdentity:
        payload = _json(agent.to_dict())
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agents(agent_id, payload) VALUES (?, ?)",
                (agent.agent_id, payload),
            )
        return agent

    def get_agent(self, agent_id: str) -> AgentIdentity | None:
        row = self._one("SELECT payload FROM agents WHERE agent_id = ?", (agent_id,))
        return AgentIdentity.from_dict(json.loads(row["payload"])) if row else None

    def list_agents(self) -> list[AgentIdentity]:
        return [AgentIdentity.from_dict(json.loads(row["payload"])) for row in self._all("SELECT payload FROM agents ORDER BY agent_id")]

    def save_intent(self, intent: IntentDeclaration) -> IntentDeclaration:
        payload = _json(intent.to_dict())
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO intents(intent_id, agent_id, status, target, payload) VALUES (?, ?, ?, ?, ?)",
                (intent.intent_id, intent.agent_id, intent.status, intent.target, payload),
            )
        return intent

    def get_intent(self, intent_id: str) -> IntentDeclaration | None:
        row = self._one("SELECT payload FROM intents WHERE intent_id = ?", (intent_id,))
        return IntentDeclaration.from_dict(json.loads(row["payload"])) if row else None

    def list_intents(self, statuses: Iterable[str] | None = None) -> list[IntentDeclaration]:
        if statuses is None:
            rows = self._all("SELECT payload FROM intents ORDER BY rowid")
        else:
            status_list = list(statuses)
            if not status_list:
                return []
            placeholders = ",".join("?" for _ in status_list)
            rows = self._all(f"SELECT payload FROM intents WHERE status IN ({placeholders}) ORDER BY rowid", status_list)
        return [IntentDeclaration.from_dict(json.loads(row["payload"])) for row in rows]

    def save_conflict(self, conflict: ConflictRecord) -> ConflictRecord:
        payload = _json(conflict.to_dict())
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO conflicts(conflict_id, resolution, payload) VALUES (?, ?, ?)",
                (conflict.conflict_id, conflict.resolution, payload),
            )
        return conflict

    def get_conflict(self, conflict_id: str) -> ConflictRecord | None:
        row = self._one("SELECT payload FROM conflicts WHERE conflict_id = ?", (conflict_id,))
        return ConflictRecord.from_dict(json.loads(row["payload"])) if row else None

    def list_conflicts(self, unresolved_only: bool = False) -> list[ConflictRecord]:
        sql = "SELECT payload FROM conflicts"
        params: tuple[Any, ...] = ()
        if unresolved_only:
            sql += " WHERE resolution = ?"
            params = ("pending",)
        sql += " ORDER BY rowid"
        return [ConflictRecord.from_dict(json.loads(row["payload"])) for row in self._all(sql, params)]

    def save_contract(self, agreement: ContractAgreement) -> ContractAgreement:
        payload = _json(agreement.to_dict())
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO contracts(agreement_id, status, payload) VALUES (?, ?, ?)",
                (agreement.agreement_id, agreement.status, payload),
            )
        return agreement

    def list_contracts(self) -> list[ContractAgreement]:
        return [ContractAgreement.from_dict(json.loads(row["payload"])) for row in self._all("SELECT payload FROM contracts ORDER BY rowid")]

    def save_witness(self, witness: WitnessRecord) -> WitnessRecord:
        payload = _json(witness.to_dict())
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO witnesses(witness_id, intent_id, payload) VALUES (?, ?, ?)",
                (witness.witness_id, witness.intent_id, payload),
            )
        return witness

    def list_witnesses(self) -> list[WitnessRecord]:
        return [WitnessRecord.from_dict(json.loads(row["payload"])) for row in self._all("SELECT payload FROM witnesses ORDER BY rowid")]

    def save_negotiation(self, session: NegotiationSession) -> NegotiationSession:
        payload = _json(session.to_dict())
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO negotiations(session_id, conflict_id, status, payload) VALUES (?, ?, ?, ?)",
                (session.session_id, session.conflict_id, session.status, payload),
            )
        return session

    def save_message(self, message: QueuedMessage) -> QueuedMessage:
        payload = _json(message.to_dict())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO message_queue(
                    message_id, recipient_id, topic, status, visible_at, leased_until, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (message.message_id, message.recipient_id, message.topic, message.status, message.visible_at, message.leased_until, payload),
            )
        return message

    def get_message(self, message_id: str) -> QueuedMessage | None:
        row = self._one("SELECT payload FROM message_queue WHERE message_id = ?", (message_id,))
        return QueuedMessage.from_dict(json.loads(row["payload"])) if row else None

    def list_messages(self, status: str | None = None) -> list[QueuedMessage]:
        if status is None:
            rows = self._all("SELECT payload FROM message_queue ORDER BY rowid")
        else:
            rows = self._all("SELECT payload FROM message_queue WHERE status = ? ORDER BY rowid", (status,))
        return [QueuedMessage.from_dict(json.loads(row["payload"])) for row in rows]

    def save_capability(self, capability: CapabilityAdvertisement) -> CapabilityAdvertisement:
        payload = _json(capability.to_dict())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO capabilities(capability_id, agent_id, capability, scope, confidence, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (capability.capability_id, capability.agent_id, capability.capability, _json({"scope": capability.scope}), capability.confidence, payload),
            )
        return capability

    def list_capabilities(self) -> list[CapabilityAdvertisement]:
        rows = self._all("SELECT payload FROM capabilities ORDER BY confidence DESC, rowid")
        return [CapabilityAdvertisement.from_dict(json.loads(row["payload"])) for row in rows]

    def save_team(self, team: AgentTeam) -> AgentTeam:
        payload = _json(team.to_dict())
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO teams(team_id, name, payload) VALUES (?, ?, ?)", (team.team_id, team.name, payload))
        return team

    def get_team(self, team_id: str) -> AgentTeam | None:
        row = self._one("SELECT payload FROM teams WHERE team_id = ?", (team_id,))
        return AgentTeam.from_dict(json.loads(row["payload"])) if row else None

    def list_teams(self) -> list[AgentTeam]:
        return [AgentTeam.from_dict(json.loads(row["payload"])) for row in self._all("SELECT payload FROM teams ORDER BY name")]

    def save_audit_event(self, event: AuditEvent) -> AuditEvent:
        payload = _json(event.to_dict())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_events(
                    event_id, timestamp, actor_id, action, subject_type, subject_id, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event.event_id, event.timestamp, event.actor_id, event.action, event.subject_type, event.subject_id, payload),
            )
        return event

    def list_audit_events(self, subject_type: str | None = None, subject_id: str | None = None) -> list[AuditEvent]:
        sql = "SELECT payload FROM audit_events"
        params: list[Any] = []
        if subject_type and subject_id:
            sql += " WHERE subject_type = ? AND subject_id = ?"
            params.extend([subject_type, subject_id])
        sql += " ORDER BY timestamp, rowid"
        return [AuditEvent.from_dict(json.loads(row["payload"])) for row in self._all(sql, params)]

    def save_reputation_rating(self, rating: ReputationRating) -> ReputationRating:
        payload = _json(rating.to_dict())
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reputation_ratings(rating_id, subject_id, rater_id, payload) VALUES (?, ?, ?, ?)",
                (rating.rating_id, rating.subject_id, rating.rater_id, payload),
            )
        return rating

    def list_reputation_ratings(self, subject_id: str | None = None) -> list[ReputationRating]:
        if subject_id is None:
            rows = self._all("SELECT payload FROM reputation_ratings ORDER BY rowid")
        else:
            rows = self._all("SELECT payload FROM reputation_ratings WHERE subject_id = ? ORDER BY rowid", (subject_id,))
        return [ReputationRating.from_dict(json.loads(row["payload"])) for row in rows]

    def get_negotiation_for_conflict(self, conflict_id: str) -> NegotiationSession | None:
        row = self._one("SELECT payload FROM negotiations WHERE conflict_id = ? ORDER BY rowid DESC LIMIT 1", (conflict_id,))
        return NegotiationSession.from_dict(json.loads(row["payload"])) if row else None

    def add_subscription(self, subscription_id: str, agent_id: str, pattern: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO subscriptions(subscription_id, agent_id, pattern) VALUES (?, ?, ?)",
                (subscription_id, agent_id, pattern),
            )

    def list_subscriptions(self) -> list[dict[str, str]]:
        return [dict(row) for row in self._all("SELECT subscription_id, agent_id, pattern FROM subscriptions ORDER BY rowid")]

    def _one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, tuple(params)).fetchone()

    def _all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql, tuple(params)).fetchall())


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
