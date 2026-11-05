"""Tests for services/name_normalizer.py -- brand/typo -> generic resolution."""

from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.schemas import Medication, NameMatch
from services.name_normalizer import ALIASES_PATH, NameNormalizer
from services.rule_engine import RULES_PATH, RuleEngine

RXCUIS = {"warfarin": "11289", "aspirin": "1191", "metformin": "6809", "metoprolol": "6918"}
ALIASES = {
    "coumadin": "warfarin",
    "ecosprin": "aspirin",
    "acetylsalicylic acid": "aspirin",
    "ghost brand": "not-in-kb",
}


@pytest.fixture
def normalizer() -> NameNormalizer:
    return NameNormalizer(RXCUIS, ALIASES)


# -- exact / alias ----------------------------------------------------------

def test_exact_match_ignores_case_and_whitespace(normalizer):
    resolution = normalizer.resolve("  WarFarin ")

    assert (resolution.canonical_name, resolution.match) == ("warfarin", NameMatch.EXACT)


def test_brand_alias_resolves_to_generic(normalizer):
    resolution = normalizer.resolve("Coumadin")

    assert (resolution.canonical_name, resolution.match) == ("warfarin", NameMatch.ALIAS)


def test_multi_word_alias_with_irregular_spacing(normalizer):
    resolution = normalizer.resolve("Acetylsalicylic   Acid")

    assert (resolution.canonical_name, resolution.match) == ("aspirin", NameMatch.ALIAS)


def test_alias_to_drug_missing_from_knowledge_base_is_dropped(normalizer):
    assert normalizer.resolve("ghost brand") is None


# -- fuzzy ------------------------------------------------------------------

@pytest.mark.parametrize(
    ("typo", "expected"),
    [("asprin", "aspirin"), ("warfarine", "warfarin"), ("ecosprn", "aspirin")],
)
def test_close_typo_resolves_with_score(normalizer, typo, expected):
    resolution = normalizer.resolve(typo)

    assert resolution.canonical_name == expected
    assert resolution.match is NameMatch.FUZZY
    assert 0.85 <= resolution.score < 1.0


def test_unrelated_name_is_not_resolved(normalizer):
    assert normalizer.resolve("zolpidem") is None


def test_short_names_are_never_fuzzy_matched(normalizer):
    assert normalizer.resolve("asp") is None


def test_near_tie_between_two_drugs_is_rejected():
    # "abcdefgx" is equally close to two different drugs: refuse to guess.
    normalizer = NameNormalizer({"abcdefga": "1", "abcdefgb": "2"})

    assert normalizer.resolve("abcdefgx") is None


# -- normalize() --------------------------------------------------------------

def test_normalize_rewrites_name_and_attaches_rxcui(normalizer):
    meds = [Medication(name="Coumadin", dosage_mg=5, frequency_per_day=2)]

    normalized, resolutions = normalizer.normalize(meds)

    assert normalized[0].name == "warfarin"
    assert normalized[0].rxcui == "11289"
    assert (normalized[0].dosage_mg, normalized[0].frequency_per_day) == (5, 2)
    assert [r.input_name for r in resolutions] == ["Coumadin"]


def test_exact_matches_are_not_reported_as_resolutions(normalizer):
    normalized, resolutions = normalizer.normalize([Medication(name="Aspirin")])

    assert normalized[0].name == "aspirin"
    assert resolutions == []


def test_unresolved_medication_is_left_untouched(normalizer):
    med = Medication(name="Zolpidem")

    normalized, resolutions = normalizer.normalize([med])

    assert normalized == [med]
    assert resolutions == []


def test_normalize_preserves_input_order(normalizer):
    names = ["Metformin", "Zolpidem", "Coumadin"]

    normalized, _ = normalizer.normalize([Medication(name=n) for n in names])

    assert [m.name for m in normalized] == ["metformin", "Zolpidem", "warfarin"]


# -- real data integrity ------------------------------------------------------

def test_every_shipped_alias_targets_a_knowledge_base_medication():
    known = RuleEngine().known_medications
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))["aliases"]

    dangling = {a: t for a, t in aliases.items() if t.lower() not in known}

    assert dangling == {}


def test_no_shipped_alias_collides_with_a_generic_name():
    known = RuleEngine().known_medications
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))["aliases"]

    assert known.isdisjoint(a.lower() for a in aliases)


def test_real_generics_never_fuzzy_match_each_other():
    """Look-alike safety: no shipped drug may be 'corrected' into another."""
    engine = RuleEngine()
    normalizer = NameNormalizer.from_file(engine.medication_rxcuis)

    for name_a, name_b in combinations(sorted(engine.known_medications), 2):
        # Drop one letter, a realistic typo, and confirm it never lands on the other drug.
        for source, other in ((name_a, name_b), (name_b, name_a)):
            typo = source[:-1]
            resolution = normalizer.resolve(typo)
            assert resolution is None or resolution.canonical_name != other


def test_real_brand_names_resolve_end_to_end():
    normalizer = NameNormalizer.from_file(RuleEngine().medication_rxcuis)

    assert normalizer.resolve("Lipitor").canonical_name == "atorvastatin"
    assert normalizer.resolve("Brufen").canonical_name == "ibuprofen"
    assert normalizer.resolve("Thyronorm").canonical_name == "levothyroxine"
