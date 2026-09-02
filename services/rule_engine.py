"""
Forward-chaining rule engine for drug-interaction detection.

Loads curated interaction rules from knowledge/interaction_rules.json
and fires whenever a user's medication set contains a known
interacting pair. Every firing is traceable back to its source rule
(Section 6.1: no black-box output).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from models.schemas import Interaction, Medication, Severity

RULES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "interaction_rules.json"


@dataclass(frozen=True)
class InteractionRule:
    """A single curated interaction rule loaded from the knowledge base."""
    rule_id: str
    medication_a: str
    medication_b: str
    severity: Severity
    description: str
    source: str


class RuleEngine:
    """Forward-chaining engine: given a set of medications, fires all matching rules."""

    def __init__(self, rules_path: Path = RULES_PATH):
        self.rules: list[InteractionRule] = self._load_rules(rules_path)

    def _load_rules(self, rules_path: Path) -> list[InteractionRule]:
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
        rules = []
        for i, entry in enumerate(raw.get("interaction_rules", [])):
            rules.append(
                InteractionRule(
                    rule_id=f"RULE_{i:03d}",
                    medication_a=entry["medication_a"].lower(),
                    medication_b=entry["medication_b"].lower(),
                    severity=Severity(entry.get("severity", "unknown")),
                    description=entry["description"],
                    source=entry.get("source", "unknown"),
                )
            )
        return rules

    def _matches(self, rule: InteractionRule, name_a: str, name_b: str) -> bool:
        pair = {name_a.lower(), name_b.lower()}
        return pair == {rule.medication_a, rule.medication_b}

    def check_interactions(self, medications: list[Medication]) -> list[Interaction]:
        """
        Forward-chains over every pair of medications in the given set,
        firing any rule whose pattern matches. Returns all flagged
        interactions with full traceability to the source rule.
        """
        flagged: list[Interaction] = []

        for med_a, med_b in combinations(medications, 2):
            for rule in self.rules:
                if self._matches(rule, med_a.name, med_b.name):
                    flagged.append(
                        Interaction(
                            medication_a=med_a.name,
                            medication_b=med_b.name,
                            severity=rule.severity,
                            confidence=1.0,  # rule-based match = certain; uncertainty layer refines this later
                            rule_id=rule.rule_id,
                            description=rule.description,
                            source=rule.source,
                        )
                    )
        return flagged