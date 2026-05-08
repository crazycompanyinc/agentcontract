"""SQLite-backed persistent queue with retries and dead-lettering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from agentcontract.audit.trail import AuditTrail
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import QueuedMessage, utc_now


class MessageQueue:
    """Durable async message delivery for agent-to-agent communication."""

    def __init__(self, db: AgentContractDB, audit: AuditTrail | None = None) -> None:
        self.db = db
        self.audit = audit or AuditTrail(db)

    def send(
        self,
        sender_id: str,
        recipient_id: str,
        topic: str,
        payload: dict[str, Any],
        max_attempts: int = 3,
        delay_seconds: int = 0,
    ) -> QueuedMessage:
        visible_at = _now_plus(delay_seconds)
        message = QueuedMessage(sender_id, recipient_id, topic, payload, max_attempts=max_attempts, visible_at=visible_at)
        self.db.save_message(message)
        self.audit.record("queue.message_sent", sender_id, "message", message.message_id, {"recipient_id": recipient_id, "topic": topic}, {"payload": payload})
        return message

    def receive(self, recipient_id: str, topic: str | None = None, lease_seconds: int = 30, limit: int = 1) -> list[QueuedMessage]:
        now = utc_now()
        leased: list[QueuedMessage] = []
        for message in self.db.list_messages():
            if len(leased) >= limit:
                break
            if message.recipient_id != recipient_id or message.status not in {"queued", "leased"}:
                continue
            if topic is not None and message.topic != topic:
                continue
            if message.status == "leased" and message.leased_until and message.leased_until > now:
                continue
            if message.visible_at > now:
                continue
            message.status = "leased"
            message.attempt_count += 1
            message.leased_until = _now_plus(lease_seconds)
            self.db.save_message(message)
            leased.append(message)
        return leased

    def ack(self, message_id: str, actor_id: str | None = None) -> QueuedMessage:
        message = self._message(message_id)
        message.status = "acked"
        message.acked_at = utc_now()
        self.db.save_message(message)
        self.audit.record("queue.message_acked", actor_id or message.recipient_id, "message", message_id)
        return message

    def fail(self, message_id: str, error: str, retry_delay_seconds: int = 60) -> QueuedMessage:
        message = self._message(message_id)
        message.last_error = error
        message.leased_until = None
        if message.attempt_count >= message.max_attempts:
            message.status = "dead_lettered"
            message.dead_lettered_at = utc_now()
            self.audit.record("queue.message_dead_lettered", message.recipient_id, "message", message_id, {"error": error})
        else:
            message.status = "queued"
            message.visible_at = _now_plus(retry_delay_seconds)
        return self.db.save_message(message)

    def dead_letters(self, recipient_id: str | None = None) -> list[QueuedMessage]:
        messages = self.db.list_messages("dead_lettered")
        if recipient_id is None:
            return messages
        return [message for message in messages if message.recipient_id == recipient_id]

    def _message(self, message_id: str) -> QueuedMessage:
        message = self.db.get_message(message_id)
        if message is None:
            raise KeyError(f"Unknown message: {message_id}")
        return message


def _now_plus(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
