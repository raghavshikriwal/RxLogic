"""
Per-drug food rules.

Some drugs are meant to be taken with food (metformin) and some on an
empty stomach (levothyroxine). This module loads those rules from
knowledge/food_rules.json and uses them to fill in a medication's
`with_food` when the user left it open, which the CSP scheduler then
enforces as a meal-window constraint.

Precedence: the user's own `with_food` is never overridden. If it
contradicts the drug's rule, their choice is kept and the conflict is
reported in the returned guidance, so nothing is changed or ignored
silently (Section 6.1).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from models.schemas import FoodGuidance, FoodRequirement, FoodStatus, Medication

FOOD_RULES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "food_rules.json"

# The `with_food` value a requirement implies; NO_RESTRICTION implies none.
_IMPLIED_WITH_FOOD: dict[FoodRequirement, bool | None] = {
    FoodRequirement.WITH_FOOD: True,
    FoodRequirement.EMPTY_STOMACH: False,
    FoodRequirement.NO_RESTRICTION: None,
}


@dataclass(frozen=True)
class FoodRule:
    """A single curated meal rule for one drug."""
    medication: str
    requirement: FoodRequirement
    note: str = ""
    source: str = ""
    rule_id: str = ""
    evidence_source_ids: tuple[str, ...] = ()
    review_status: str = "needs_clinical_review"


class FoodRules:
    """Looks up each drug's food rule and applies it to a medication list."""

    @classmethod
    def from_active_release(cls, knowledge_root: Path | None = None) -> "FoodRules":
        """Load food rules only from the active approved release (fail closed)."""
        from services.knowledge_release import DEFAULT_KNOWLEDGE_ROOT, load_active_release

        bundle = load_active_release(knowledge_root or DEFAULT_KNOWLEDGE_ROOT)
        instance = cls.__new__(cls)
        instance.rules = instance._parse_rules(bundle["food_rules"])
        instance.knowledge_release = bundle["manifest"]["knowledge_release"]
        return instance

    def __init__(self, rules_path: Path = FOOD_RULES_PATH):
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
        self.rules: dict[str, FoodRule] = self._parse_rules(raw)

    @staticmethod
    def _parse_rules(raw: dict) -> dict[str, FoodRule]:
        rules: dict[str, FoodRule] = {}
        for entry in raw.get("food_rules", []):
            name = entry["medication"].lower()
            if name in rules:
                raise ValueError(f"duplicate food rule for {name!r}")
            rules[name] = FoodRule(
                medication=name,
                requirement=FoodRequirement(entry["requirement"]),
                note=entry.get("note", ""),
                source=entry.get("source", ""),
                rule_id=entry.get("rule_id", f"FOOD-{name.upper()}"),
                evidence_source_ids=tuple(entry.get("evidence_source_ids", ())),
                review_status=entry.get("review_status", "needs_clinical_review"),
            )
        return rules

    def apply(self, medications: list[Medication]) -> tuple[list[Medication], list[FoodGuidance]]:
        """
        Returns the medications with open `with_food` values filled in from
        their food rules, plus one FoodGuidance per drug that has a rule
        (in input order). Drugs without a rule pass through unchanged.
        """
        resolved: list[Medication] = []
        guidance: list[FoodGuidance] = []

        for medication in medications:
            rule = self.rules.get(medication.name.lower())
            if rule is None:
                resolved.append(medication)
                continue

            if rule.review_status.strip().lower() != "approved":
                resolved.append(medication)
                guidance.append(
                    FoodGuidance(
                        medication=medication.name.lower(),
                        requirement=rule.requirement,
                        status=FoodStatus.INFORMATIONAL,
                        note="Not applied: this rule requires clinical review.",
                        source="",
                        rule_id=rule.rule_id,
                        evidence_source_ids=rule.evidence_source_ids,
                        review_status=rule.review_status,
                    )
                )
                continue

            medication, status = self._apply_rule(medication, rule)
            resolved.append(medication)
            guidance.append(
                FoodGuidance(
                    medication=medication.name.lower(),
                    requirement=rule.requirement,
                    status=status,
                    note=rule.note,
                    source=rule.source,
                    rule_id=rule.rule_id,
                    evidence_source_ids=rule.evidence_source_ids,
                    review_status=rule.review_status,
                )
            )
        return resolved, guidance

    @staticmethod
    def _apply_rule(medication: Medication, rule: FoodRule) -> tuple[Medication, FoodStatus]:
        implied = _IMPLIED_WITH_FOOD[rule.requirement]
        if implied is None:
            return medication, FoodStatus.INFORMATIONAL
        if medication.with_food is None:
            return replace(medication, with_food=implied), FoodStatus.APPLIED
        if medication.with_food == implied:
            return medication, FoodStatus.MATCHES_INPUT
        return medication, FoodStatus.CONFLICTS_WITH_INPUT
