"""Webhook subscriptions and delivery for external integrations."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx

from agentcontract.audit.trail import AuditTrail
from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import new_id, utc_now


class WebhookManager:
    """Sends AgentContract events to systems like Slack, Discord, and GitHub."""

    def __init__(self, db: AgentContractDB, audit: AuditTrail | None = None) -> None:
        self.db = db
        self.audit = audit or AuditTrail(db)

    def subscribe(self, event_type: str, target_url: str, secret: str | None = None) -> dict[str, Any]:
        webhook = {
            "webhook_id": new_id("webhook"),
            "event_type": event_type,
            "target_url": target_url,
            "secret": secret,
            "active": True,
            "created_at": utc_now(),
        }
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_subscriptions(webhook_id, event_type, target_url, secret, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (webhook["webhook_id"], event_type, target_url, secret, 1, webhook["created_at"]),
            )
        return webhook

    def list_subscriptions(self, event_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT webhook_id, event_type, target_url, secret, active, created_at FROM webhook_subscriptions WHERE active = 1"
        params: tuple[str, ...] = ()
        if event_type is not None:
            sql += " AND event_type = ?"
            params = (event_type,)
        return [dict(row) for row in self.db._all(sql, params)]

    def emit(self, event_type: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        deliveries = []
        for webhook in self.list_subscriptions(event_type):
            deliveries.append(self._record_delivery(webhook["webhook_id"], event_type, "pending", 0, payload))
        return deliveries

    async def deliver_async(self, event_type: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        async with httpx.AsyncClient(timeout=5) as client:
            for webhook in self.list_subscriptions(event_type):
                body = json.dumps(payload, sort_keys=True).encode()
                headers = {"content-type": "application/json", "x-agentcontract-event": event_type}
                if webhook.get("secret"):
                    headers["x-agentcontract-signature"] = hmac.new(webhook["secret"].encode(), body, hashlib.sha256).hexdigest()
                try:
                    response = await client.post(webhook["target_url"], content=body, headers=headers)
                    status = "delivered" if 200 <= response.status_code < 300 else "failed"
                    delivery = self._record_delivery(webhook["webhook_id"], event_type, status, 1, payload | {"status_code": response.status_code})
                except httpx.HTTPError as exc:
                    delivery = self._record_delivery(webhook["webhook_id"], event_type, "failed", 1, payload | {"error": str(exc)})
                self.audit.record("webhook.delivered", "system", "webhook", webhook["webhook_id"], delivery)
                results.append(delivery)
        return results

    def _record_delivery(self, webhook_id: str, event_type: str, status: str, attempts: int, payload: dict[str, Any]) -> dict[str, Any]:
        delivery = {
            "delivery_id": new_id("delivery"),
            "webhook_id": webhook_id,
            "event_type": event_type,
            "status": status,
            "attempts": attempts,
            "payload": payload,
        }
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_deliveries(delivery_id, webhook_id, event_type, status, attempts, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (delivery["delivery_id"], webhook_id, event_type, status, attempts, json.dumps(payload, sort_keys=True)),
            )
        return delivery
