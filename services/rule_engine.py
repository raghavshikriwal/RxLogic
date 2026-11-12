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

from models.schemas import Coverage, DoseOrdering, EvidenceStrength, Interaction, Medication, Severity

RULES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "interaction_rules.json"


def _parse_separation(entry: dict, rule_id: str) -> int | None:
    """Reads an optional per-pair separation time (minutes) from a rule entry.

    Absent means "no pair-specific guidance". A present value must be a
    positive integer: a malformed one raises rather than being silently
    ignored, because a dropped separation would weaken the schedule.
    """
    value = entry.get("separation_minutes")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(
            f"{rule_id}: separation_minutes must be a positive integer, got {value!r}"
        )
    return value


def _parse_ordering(entry: dict, rule_id: str) -> DoseOrdering | None:
    """Reads an optional order-aware spacing rule from a rule entry.

    Expected shape: {"anchor": <one of the rule's drugs>, "after_minutes": N,
    "before_minutes": M}. Malformed input raises rather than being dropped,
    and so does combining it with `separation_minutes`: two spacing rules on
    one entry would be ambiguous.
    """
    raw = entry.get("ordering")
    if raw is None:
        return None
    if entry.get("separation_minutes") is not None:
        raise ValueError(f"{rule_id}: use either separation_minutes or ordering, not both")

    anchor = str(raw.get("anchor", "")).lower()
    if anchor not in (entry["medication_a"].lower(), entry["medication_b"].lower()):
        raise ValueError(f"{rule_id}: ordering anchor {anchor!r} must be one of the rule's two drugs")

    gaps = {}
    for key in ("after_minutes", "before_minutes"):
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{rule_id}: ordering {key} must be a positive integer, got {value!r}")
        gaps[key] = value
    return DoseOrdering(anchor=anchor, **gaps)


@dataclass(frozen=True)
class InteractionRule:
    """A single curated interaction rule loaded from the knowledge base."""
    rule_id: str
    medication_a: str
    medication_b: str
    severity: Severity
    description: str
    source: str
    evidence: EvidenceStrength = EvidenceStrength.UNKNOWN
    separation_minutes: int | None = None
    ordering: DoseOrdering | None = None
    evidence_source_ids: tuple[str, ...] = ()
    review_status: str = "needs_clinical_review"
    jurisdiction: str = "unspecified"


class RuleEngine:
    """Forward-chaining engine: given a set of medications, fires all matching rules."""

    @classmethod
    def from_active_release(cls, knowledge_root: Path | None = None) -> "RuleEngine":
        """Load interaction rules only from the explicitly active approved release.

        This loader fails closed when no release is active; it never falls back
        to the legacy development dataset.
        """
        from services.knowledge_release import DEFAULT_KNOWLEDGE_ROOT, load_active_release

        bundle = load_active_release(knowledge_root or DEFAULT_KNOWLEDGE_ROOT)
        # Keep parsing logic centralized while avoiding a temporary dataset file.
        instance = cls.__new__(cls)
        raw = bundle["interaction_rules"]
        instance.rules = instance._parse_rules(raw)
        instance.medication_rxcuis = {
            name.lower(): str(rxcui) for name, rxcui in raw.get("medications", {}).items()
        }
        instance.known_medications = frozenset(instance.medication_rxcuis)
        instance.knowledge_release = bundle["manifest"]["knowledge_release"]
        return instance

    def __init__(self, rules_path: Path = RULES_PATH):
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
        self.rules: list[InteractionRule] = self._parse_rules(raw)
        # generic name -> RxCUI for every medication the knowledge base can
        # reason about. A drug outside this mapping has *no coverage*, which
        # is different from "no interactions" -- callers must not conflate
        # the two.
        self.medication_rxcuis: dict[str, str] = {
            name.lower(): str(rxcui) for name, rxcui in raw.get("medications", {}).items()
        }
        self.known_medications: frozenset[str] = frozenset(self.medication_rxcuis)

    @staticmethod
    def _parse_rules(raw: dict) -> list[InteractionRule]:
        rules = []
        for i, entry in enumerate(raw.get("interaction_rules", [])):
            rules.append(
                InteractionRule(
                    rule_id=entry.get("rule_id", f"RULE_{i:03d}"),
                    medication_a=entry["medication_a"].lower(),
                    medication_b=entry["medication_b"].lower(),
                    severity=Severity(entry.get("severity", "unknown")),
                    description=entry["description"],
                    source=entry.get("source", "unknown"),
                    evidence=EvidenceStrength(entry.get("evidence", "unknown")),
                    separation_minutes=_parse_separation(entry, rule_id=entry.get("rule_id", f"RULE_{i:03d}")),
                    ordering=_parse_ordering(entry, rule_id=entry.get("rule_id", f"RULE_{i:03d}")),
                    evidence_source_ids=tuple(entry.get("evidence_source_ids", ())),
                    review_status=entry.get("review_status", "needs_clinical_review"),
                    jurisdiction=entry.get("jurisdiction", "unspecified"),
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
                            evidence=rule.evidence,
                            separation_minutes=rule.separation_minutes,
                            ordering=rule.ordering,
                            evidence_source_ids=rule.evidence_source_ids,
                            review_status=rule.review_status,
                            jurisdiction=rule.jurisdiction,
                        )
                    )
        return flagged