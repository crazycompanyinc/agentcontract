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
                """
            )

    def clear(self) -> None:
        with self.connect() as conn:
            for table in ["subscriptions", "negotiations", "witnesses", "contracts", "conflicts", "intents", "agents"]:
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
