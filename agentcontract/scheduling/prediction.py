"""Historical conflict prediction."""

from __future__ import annotations

from agentcontract.core.db import AgentContractDB
from agentcontract.core.models import IntentDeclaration


class ConflictPredictor:
    """Predicts likely conflicts from prior conflict records."""

    def __init__(self, db: AgentContractDB) -> None:
        self.db = db

    def predict(self, left: IntentDeclaration, right: IntentDeclaration) -> dict[str, object]:
        pair = set([left.agent_id, right.agent_id])
        resource = _common_prefix(left.resources() + right.resources())
        total_pair = 0
        matching_resource = 0
        for conflict in self.db.list_conflicts():
            if set(conflict.involved_agents) != pair:
                continue
            total_pair += 1
            intents = [self.db.get_intent(intent_id) for intent_id in conflict.involved_intents]
            resources = [res for intent in intents if intent for res in intent.resources()]
            if any(_same_or_nested(resource, res) for res in resources):
                matching_resource += 1
        probability = matching_resource / total_pair if total_pair else 0.0
        return {
            "agents": sorted(pair),
            "resource": resource,
            "probability": round(probability, 2),
            "confidence": min(1.0, total_pair / 10),
            "sample_size": total_pair,
            "message": f"{left.agent_id} and {right.agent_id} conflict {round(probability * 100)}% of observed times near {resource}.",
        }

    def predict_for_new_intent(self, intent: IntentDeclaration) -> list[dict[str, object]]:
        predictions = []
        for other in self.db.list_intents(["proposed", "approved", "in_progress"]):
            if other.intent_id != intent.intent_id and other.agent_id != intent.agent_id:
                prediction = self.predict(intent, other)
                if prediction["probability"]:
                    predictions.append(prediction)
        return sorted(predictions, key=lambda item: item["probability"], reverse=True)


def _common_prefix(resources: list[str]) -> str:
    if not resources:
        return ""
    shortest = min(resources, key=len).rstrip("/")
    parts = shortest.split("/")
    if len(parts) <= 1:
        return shortest
    return "/".join(parts[:-1]) + "/"


def _same_or_nested(left: str, right: str) -> bool:
    a = left.rstrip("/")
    b = right.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")
