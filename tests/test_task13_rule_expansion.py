"""Task 13: label-cited interaction rule expansion.

These tests check structure, provenance and engine/scheduler behaviour. They
are NOT clinical validation: every rule remains ``needs_clinical_review``.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import Medication
from services.csp_scheduler import CSPScheduler
from services.knowledge_validation import ROOT
from services.name_normalizer import NameNormalizer
from services.rule_engine import RuleEngine

CITED_PREFIX = "SRC-CITED-"
MIN_NEW_RULES = 25
REQUIRED_SOURCE_FIELDS = (
    "publisher", "source_type", "document_title", "document_version", "retrieved_at",
    "jurisdiction", "locator", "canonical_url",
)
LEVOTHYROXINE_CALCIUM_GAP_MINUTES = 240


def _read(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _cited_rules() -> list[dict]:
    return [
        rule for rule in _read("interaction_rules.json")["interaction_rules"]
        if any(ref.startswith(CITED_PREFIX) for ref in rule["evidence_source_ids"])
    ]


def _cited_sources() -> dict[str, dict]:
    return {
        source["source_id"]: source for source in _read("evidence_sources.json")["sources"]
        if source["source_id"].startswith(CITED_PREFIX)
    }


def _med(name: str, **kwargs) -> Medication:
    return Medication(name=name, **kwargs)


def test_at_least_25_new_cited_rules_exist():
    assert len(_cited_rules()) >= MIN_NEW_RULES


def test_every_cited_rule_references_only_cited_sources_and_stays_unreviewed():
    sources = _cited_sources()
    for rule in _cited_rules():
        assert rule["review_status"] == "needs_clinical_review", rule["rule_id"]
        assert rule["evidence_source_ids"], rule["rule_id"]
        assert all(ref in sources for ref in rule["evidence_source_ids"]), rule["rule_id"]


def test_cited_sources_carry_complete_https_provenance():
    for source_id, source in _cited_sources().items():
        for field in REQUIRED_SOURCE_FIELDS:
            assert str(source.get(field) or "").strip(), f"{source_id}: {field} missing"
        parts = urlsplit(source["canonical_url"])
        assert parts.scheme == "https" and parts.hostname and not parts.fragment, source_id
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", source["retrieved_at"]), source_id
        date.fromisoformat(source["retrieved_at"])
        assert source["verification_status"] == "citation_recorded_pending_review", source_id
        assert source["source_quality_assessment"] == "not_assessed", source_id


def test_every_cited_source_is_used_by_at_least_one_rule():
    used = {ref for rule in _cited_rules() for ref in rule["evidence_source_ids"]}
    assert set(_cited_sources()) == used


def test_rule_ids_follow_the_alphabetical_pair_convention():
    for rule in _cited_rules():
        a, b = rule["medication_a"], rule["medication_b"]
        assert a < b, rule["rule_id"]
        expected = f"DDI-{a.upper().replace(' ', '-')}-{b.upper().replace(' ', '-')}"
        assert rule["rule_id"] == expected


def test_contraindicated_pairs_are_graded_severe_with_strong_evidence():
    rules = {rule["rule_id"]: rule for rule in _cited_rules()}
    for rule_id in ("DDI-NITROGLYCERIN-SILDENAFIL", "DDI-CLARITHROMYCIN-SIMVASTATIN", "DDI-ALPRAZOLAM-TRAMADOL"):
        assert rules[rule_id]["severity"] == "severe", rule_id
        assert rules[rule_id]["evidence"] == "strong", rule_id


def test_levothyroxine_calcium_rule_declares_a_four_hour_separation():
    rule = next(r for r in _cited_rules() if r["rule_id"] == "DDI-CALCIUM-CARBONATE-LEVOTHYROXINE")
    assert rule["separation_minutes"] == LEVOTHYROXINE_CALCIUM_GAP_MINUTES


def test_engine_fires_every_pair_in_a_polypharmacy_regimen():
    engine = RuleEngine()
    fired = {i.rule_id for i in engine.check_interactions([_med("warfarin"), _med("sertraline"), _med("tramadol")])}
    assert fired == {"DDI-SERTRALINE-WARFARIN", "DDI-SERTRALINE-TRAMADOL", "DDI-TRAMADOL-WARFARIN"}


def test_every_new_medication_is_known_to_the_engine():
    engine = RuleEngine()
    used = {m for rule in _cited_rules() for m in (rule["medication_a"], rule["medication_b"])}
    assert used <= engine.known_medications


def test_every_alias_resolves_to_its_catalog_medication():
    engine = RuleEngine()
    normalizer = NameNormalizer.from_file(engine.medication_rxcuis)
    for alias, canonical in _read("drug_aliases.json")["aliases"].items():
        resolution = normalizer.resolve(alias)
        assert resolution is not None and resolution.canonical_name == canonical, alias


def test_scheduler_honours_the_levothyroxine_calcium_separation():
    engine = RuleEngine()
    meds = [_med("levothyroxine"), _med("calcium carbonate")]
    interactions = engine.check_interactions(meds)
    assert [i.separation_minutes for i in interactions] == [LEVOTHYROXINE_CALCIUM_GAP_MINUTES]

    entries = CSPScheduler(meds, interactions).solve().entries
    minutes = {e.medication: e.scheduled_time.hour * 60 + e.scheduled_time.minute for e in entries}
    assert abs(minutes["levothyroxine"] - minutes["calcium carbonate"]) >= LEVOTHYROXINE_CALCIUM_GAP_MINUTES
