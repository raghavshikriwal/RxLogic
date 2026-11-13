"""
Medication-name normalization: user input -> knowledge-base generic name.

Real users type brand names ("Coumadin"), spelling variants
("amoxycillin") and typos ("asprin"). This module maps such input onto
the generic names the knowledge base is keyed on, so those drugs are
checked instead of being rejected as unknown.

Resolution order, first hit wins:
    1. exact   - the name is already a knowledge-base generic
    2. alias   - curated brand/variant in knowledge/drug_aliases.json
    3. fuzzy   - near-miss spelling, accepted only when unambiguous

Safety (Section 9): a wrong match is worse than no match, since look-alike
drug names are a well-known source of medication errors. Fuzzy matching is
therefore deliberately conservative, with a high similarity floor, a
minimum name length, and a rejection of any input that is nearly as close
to a *second* drug as to its best match. Anything not resolved is left
untouched, and the rule engine reports it as unknown (fail-safe).
Every non-exact resolution is returned to the caller so it can be shown
to the user rather than applied silently.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Mapping, Optional

from models.schemas import Medication, NameMatch, NameResolution

ALIASES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "drug_aliases.json"

FUZZY_MIN_SCORE = 0.85       # similarity floor for accepting a typo correction
FUZZY_MIN_LENGTH = 5         # shorter names are too ambiguous to correct
FUZZY_AMBIGUITY_MARGIN = 0.05  # best match must beat the runner-up drug by this much

_WHITESPACE = re.compile(r"\s+")


def _clean(name: str) -> str:
    """Case-fold and collapse whitespace; the single lookup key format."""
    return _WHITESPACE.sub(" ", name.strip()).lower()


class NameNormalizer:
    """Resolves free-form medication names to knowledge-base generics."""

    def __init__(
        self,
        rxcuis: Mapping[str, str],
        aliases: Mapping[str, str] | None = None,
    ):
        """
        Args:
            rxcuis: canonical generic name -> RxCUI. Its keys define which
                generics exist.
            aliases: alias -> canonical generic. Entries pointing at a
                generic missing from `rxcuis` are dropped, since they could
                only resolve to a drug the knowledge base cannot check.
        """
        self._rxcuis = {_clean(name): rxcui for name, rxcui in rxcuis.items()}
        self._aliases = {
            _clean(alias): _clean(target)
            for alias, target in (aliases or {}).items()
            if _clean(target) in self._rxcuis
        }
        # Every spelling the fuzzy matcher may compare against, with its drug.
        self._terms: dict[str, str] = {name: name for name in self._rxcuis}
        self._terms.update(self._aliases)

    @classmethod
    def from_file(
        cls, rxcuis: Mapping[str, str], aliases_path: Path = ALIASES_PATH
    ) -> "NameNormalizer":
        raw = json.loads(aliases_path.read_text(encoding="utf-8"))
        return cls(rxcuis, raw.get("aliases", {}))

    @classmethod
    def from_catalog(cls, catalog: Mapping[str, object], rxcuis: Mapping[str, str]) -> "NameNormalizer":
        """Construct from a validated medication catalog payload."""
        from services.medication_catalog import validate_medication_catalog
        errors = validate_medication_catalog(catalog)
        if errors:
            raise ValueError("invalid medication catalog: " + "; ".join(errors))
        aliases: dict[str, str] = {}
        for row in catalog.get("medications", []):
            if not isinstance(row, dict):
                continue
            canonical = str(row.get("canonical_name", "")).casefold()
            for alias in row.get("aliases", []):
                aliases[str(alias).casefold()] = canonical
        return cls(rxcuis, aliases)

    def resolve(self, name: str) -> Optional[NameResolution]:
        """Returns how `name` maps to a generic, or None if it does not."""
        key = _clean(name)
        if key in self._rxcuis:
            return NameResolution(name, key, NameMatch.EXACT)
        if key in self._aliases:
            return NameResolution(name, self._aliases[key], NameMatch.ALIAS)
        return self._fuzzy_resolve(name, key)

    def _fuzzy_resolve(self, name: str, key: str) -> Optional[NameResolution]:
        if len(key) < FUZZY_MIN_LENGTH:
            return None

        best_per_drug: dict[str, float] = {}
        for term, drug in self._terms.items():
            score = SequenceMatcher(None, key, term).ratio()
            if score > best_per_drug.get(drug, 0.0):
                best_per_drug[drug] = score

        ranked = sorted(best_per_drug.items(), key=lambda item: item[1], reverse=True)
        if not ranked or ranked[0][1] < FUZZY_MIN_SCORE:
            return None
        if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < FUZZY_AMBIGUITY_MARGIN:
            return None  # near-tie between two different drugs: refuse to guess

        drug, score = ranked[0]
        return NameResolution(name, drug, NameMatch.FUZZY, round(score, 2))

    def normalize(
        self, medications: list[Medication]
    ) -> tuple[list[Medication], list[NameResolution]]:
        """
        Rewrites each resolvable medication to its generic name and RxCUI.

        Returns the normalized list (input order preserved; unresolved
        entries untouched) and the alias/fuzzy resolutions that changed a
        name, for surfacing to the user.
        """
        normalized: list[Medication] = []
        applied: list[NameResolution] = []
        for medication in medications:
            resolution = self.resolve(medication.name)
            if resolution is None:
                normalized.append(medication)
                continue
            normalized.append(
                replace(
                    medication,
                    name=resolution.canonical_name,
                    rxcui=self._rxcuis[resolution.canonical_name],
                )
            )
            if resolution.match is not NameMatch.EXACT:
                applied.append(resolution)
        return normalized, applied
