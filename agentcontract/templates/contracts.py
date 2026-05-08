"""Pre-defined contract templates."""

from __future__ import annotations

from typing import Any

from agentcontract.core.models import ContractAgreement


class ContractTemplates:
    """Creates common team and collaboration contracts."""

    templates: dict[str, dict[str, Any]] = {
        "pair-programming": {"required": ["driver", "navigator", "handoff_cadence"], "terms": {"mode": "pair-programming"}},
        "code-review": {"required": ["author", "reviewer", "approval_rule"], "terms": {"mode": "code-review"}},
        "deploy-pipeline": {"required": ["builder", "deployer", "rollback_owner"], "terms": {"mode": "deploy-pipeline"}},
    }

    def names(self) -> list[str]:
        return sorted(self.templates)

    def create(self, template_name: str, participants: list[str], intent_ids: list[str], fields: dict[str, Any]) -> ContractAgreement:
        template = self._template(template_name)
        missing = [name for name in template["required"] if not fields.get(name)]
        if missing:
            raise ValueError(f"{template_name} contract missing required field(s): {', '.join(missing)}")
        return ContractAgreement(participants=participants, intent_ids=intent_ids, terms=template["terms"] | fields, status="agreed")

    def _template(self, template_name: str) -> dict[str, Any]:
        try:
            return self.templates[template_name]
        except KeyError as exc:
            raise KeyError(f"Unknown contract template: {template_name}") from exc
