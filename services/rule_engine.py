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

from models.schemas import Coverage, Interaction, Medication, Severity

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
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
        self.rules: list[InteractionRule] = self._parse_rules(raw)
        # Medications the knowledge base can reason about. A drug outside
        # this set has *no coverage*, which is different from "no
        # interactions" -- callers must not conflate the two.
        self.known_medications: frozenset[str] = frozenset(
            name.lower() for name in raw.get("medications", {})
        )

    @staticmethod
    def _parse_rules(raw: dict) -> list[InteractionRule]:
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

    def find_unknown_medications(self, medications: list[Medication]) -> list[str]:
        """
        Returns the names of medications the knowledge base does not
        cover, in input order, de-duplicated (case-insensitively), with
        the caller's original spelling preserved.

        Normalization is deliberately identical to `_matches` (plain
        `.lower()`): a name that would fail to match a rule must also be
        reported as unknown, otherwise it would slip through as a silent
        "no interactions" result.
        """
        unknown: list[str] = []
        seen: set[str] = set()
        for medication in medications:
            key = medication.name.lower()
            if key in self.known_medications or key in seen:
                continue
            seen.add(key)
            unknown.append(medication.name)
        return unknown

    def assess_coverage(self, medications: list[Medication]) -> Coverage:
        """
        Reports how many distinct medications the knowledge base covers.

        Shares `find_unknown_medications` for the coverage decision so
        "unknown" has exactly one definition across the engine.
        """
        distinct_count = len({medication.name.lower() for medication in medications})
        return Coverage(
            total=distinct_count,
            unchecked=tuple(self.find_unknown_medications(medications)),
        )

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
                            medication_a=med_a.name.lower(),
                            medication_b=med_b.name.lower(),
                            severity=rule.severity,
                            confidence=1.0,  # rule-based match = certain; uncertainty layer refines this later
                            rule_id=rule.rule_id,
                            description=rule.description,
                            source=rule.source,
                        )
                    )
        return flagged