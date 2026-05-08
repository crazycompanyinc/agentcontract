"""Transparent compliance scoring for declared intents."""

from __future__ import annotations

from agentcontract.core.models import IntentDeclaration


class ComplianceChecker:
    """Scores how closely an actual action matches a declared intent."""

    def score(self, intent: IntentDeclaration, actual_action: str) -> tuple[float, str | None]:
        action = actual_action.lower()
        target = intent.target.lower().rstrip("/")
        description_words = {word.strip(".,:;()[]{}").lower() for word in intent.description.split() if len(word) > 3}
        score = 0.25
        reasons: list[str] = []

        if target and target in action:
            score += 0.45
        else:
            reasons.append("target not mentioned in actual action")

        if intent.intent_type in action:
            score += 0.15
        else:
            reasons.append("intent type not reflected in actual action")

        overlap = description_words.intersection(set(action.split()))
        if description_words and len(overlap) / len(description_words) >= 0.25:
            score += 0.15
        elif description_words:
            reasons.append("description overlap below threshold")

        final = round(min(1.0, score), 2)
        return final, "; ".join(reasons) if reasons else None
