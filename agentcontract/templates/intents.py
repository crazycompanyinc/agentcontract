"""Pre-defined intent templates and validation."""

from __future__ import annotations

from typing import Any

from agentcontract.core.models import IntentDeclaration


class IntentTemplates:
    """Builds common validated intent declarations."""

    templates: dict[str, dict[str, Any]] = {
        "deploy": {"intent_type": "deploy", "required": ["environment", "artifact", "rollback_plan"]},
        "refactor": {"intent_type": "refactor", "required": ["module", "risk_level"]},
        "hotfix": {"intent_type": "modify", "required": ["incident_id", "severity", "rollback_plan"]},
        "feature-add": {"intent_type": "create", "required": ["feature_name", "acceptance_criteria"]},
        "bug-fix": {"intent_type": "modify", "required": ["bug_id", "reproduction_steps", "expected_behavior"]},
    }

    def names(self) -> list[str]:
        return sorted(self.templates)

    def validate(self, template_name: str, fields: dict[str, Any]) -> None:
        template = self._template(template_name)
        missing = [name for name in template["required"] if not fields.get(name)]
        if missing:
            raise ValueError(f"{template_name} intent missing required field(s): {', '.join(missing)}")

    def create(
        self,
        template_name: str,
        agent_id: str,
        target: str,
        description: str,
        fields: dict[str, Any],
        impact_scope: list[str] | None = None,
        dependencies: list[str] | None = None,
    ) -> IntentDeclaration:
        self.validate(template_name, fields)
        template = self._template(template_name)
        return IntentDeclaration(
            agent_id=agent_id,
            intent_type=template["intent_type"],
            target=target,
            description=description,
            impact_scope=impact_scope or [],
            dependencies=dependencies or [],
        )

    def _template(self, template_name: str) -> dict[str, Any]:
        try:
            return self.templates[template_name]
        except KeyError as exc:
            raise KeyError(f"Unknown intent template: {template_name}") from exc
