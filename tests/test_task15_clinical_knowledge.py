"""Task 15: clinical knowledge coverage, profile API, label drafting and governance.

All clinical text in this module is SYNTHETIC test data. It exists only inside
temporary directories and is never shipped as knowledge.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask import Flask

from extensions import limiter
from routes.knowledge_api import knowledge_api
from services.clinical_knowledge import (
    ALL_DOMAINS, CANDIDATE_TYPE_TO_DOMAIN, DOMAIN_TO_CANDIDATE_TYPE, EXTENDED_DOMAINS,
    validate_clinical_assertions,
)
from services.clinical_profile import (
    DOMAIN_ORDER, KnowledgeView, UnknownMedicationLookup, build_catalog_overview, build_medication_profile,
)
from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
from services.evidence_review import record_review_decision
from services.knowledge_coverage import build_coverage_report
from services.knowledge_curation import CurationError, create_candidate, record_clinical_decision
from services.knowledge_release import create_release, promote_release, record_release_review
from services.label_drafting import LabelDraftingError, draft_from_openfda_label, write_drafts

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
CATALOG = json.loads((KNOWLEDGE / "medication_catalog.json").read_text(encoding="utf-8"))
NAMES = [row["canonical_name"] for row in CATALOG["medications"]]


# -- helpers ------------------------------------------------------------------

def _statement_rule(**extra):
    return {"medication": "warfarin", "statement": "Synthetic statement only.", "evidence_strength": "moderate",
            "source": "Synthetic", "source_locator": "Synthetic section 1", "jurisdiction": "US",
            "conflict_status": "no_known_conflict", **extra}


RULES = {
    "medication_overview": _statement_rule(statement="Synthetic overview."),
    "drug_class": _statement_rule(statement="Synthetic class."),
    "therapeutic_category": _statement_rule(statement="Synthetic category."),
    "mechanism_of_action": _statement_rule(statement="Synthetic mechanism."),
    "approved_indication": _statement_rule(statement="Synthetic indication."),
    "precaution": _statement_rule(statement="Synthetic precaution."),
    "adverse_effect": _statement_rule(statement="Synthetic adverse effect."),
    "drug_supplement_interaction": {
        "medication": "warfarin", "supplement_or_component": "synthetic supplement", "clinical_effect": "Synthetic effect.",
        "severity": "moderate", "evidence_strength": "limited", "source": "Synthetic", "source_locator": "Synthetic section 2",
        "jurisdiction": "US", "conflict_status": "no_known_conflict"},
    "contraindication": {"medication": "warfarin", "condition_or_population": "synthetic condition", "clinical_action": "Synthetic action.",
                         "evidence_strength": "moderate", "source": "Synthetic", "jurisdiction": "US", "conflict_status": "no_known_conflict"},
    "dosage_reference": {"medication": "warfarin", "indication": "synthetic indication", "population": "synthetic population",
                         "dose_text": "Source-scoped text only.", "route": "oral", "frequency": "per source",
                         "evidence_strength": "unknown", "source": "Synthetic", "jurisdiction": "US", "conflict_status": "no_known_conflict"},
    "drug_food_interaction": {"medication": "warfarin", "food_or_component": "synthetic food", "clinical_effect": "Synthetic effect.",
                              "severity": "mild", "evidence_strength": "limited", "source": "Synthetic", "jurisdiction": "US",
                              "conflict_status": "no_known_conflict"},
    "administration_instruction": {"medication": "warfarin", "instruction": "Synthetic instruction.", "evidence_strength": "moderate",
                                   "source": "Synthetic", "jurisdiction": "US", "conflict_status": "no_known_conflict"},
}


def _evidence(tmp_path: Path):
    source = tmp_path / "label.json"
    source.write_text('{"label":"synthetic fixture only"}', encoding="utf-8")
    staging = tmp_path / "staging"
    result = ingest_json_document(source, EvidenceMetadata(
        publisher="Synthetic regulator fixture", source_type="fda_label", document_title="Synthetic label fixture",
        canonical_url="https://api.fda.gov/test/task15-label", jurisdiction="US"), staging)
    record_review_decision(result.record_id, "accepted_for_curation", "evidence-reviewer", "clinical_reviewer", "Synthetic accepted.", staging)
    return staging, result


def _active_release(tmp_path: Path, kinds=tuple(RULES)):
    staging, evidence = _evidence(tmp_path)
    curation = tmp_path / "curation"
    ids = []
    for kind in kinds:
        candidate = create_candidate(kind, RULES[kind], [evidence.record_id], f"author-{kind}", "Synthetic", staging, curation)
        record_clinical_decision(candidate["candidate_id"], "approved", "independent-pharmacist", "clinical_pharmacist", "Synthetic review", curation, staging)
        ids.append(candidate["candidate_id"])
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "release_governance_policy.json").write_bytes((KNOWLEDGE / "release_governance_policy.json").read_bytes())
    (knowledge / "medication_catalog.json").write_bytes((KNOWLEDGE / "medication_catalog.json").read_bytes())
    runtime_map = json.loads((KNOWLEDGE / "interaction_rules.json").read_text(encoding="utf-8"))["medications"]
    (knowledge / "interaction_rules.json").write_text(json.dumps({"medications": runtime_map, "interaction_rules": []}), encoding="utf-8")
    manifest = create_release(ids, "steward", "Synthetic release", curation, staging, knowledge)
    release_id = manifest["knowledge_release"]
    record_release_review(release_id, "rel-clinical", "clinical_pharmacist", "clinical_release", "approved", "Synthetic", knowledge)
    record_release_review(release_id, "rel-gov", "knowledge_steward", "governance_release", "approved", "Synthetic", knowledge)
    promote_release(release_id, "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    return knowledge, release_id


def _view(assertions=None, rules=None, *, authoritative=True, sources=None):
    return KnowledgeView(
        mode="active_release" if authoritative else "legacy_development", release="RXK-TEST", catalog=CATALOG,
        assertions=assertions or {}, interaction_rules=rules or [],
        sources=sources or {"SRC-1": {"source_id": "SRC-1", "publisher": "Synthetic", "canonical_url": "https://example.gov/x"}},
        authoritative=authoritative)


def _record(**extra):
    return {"assertion_id": "A-1", "medication": "warfarin", "statement": "Synthetic statement.", "review_status": "clinically_approved",
            "conflict_status": "no_known_conflict", "evidence_source_ids": ["SRC-1"], "evidence_strength": "moderate",
            "source_quality_tier": "not_assessed", "jurisdiction": "US", "source": "Synthetic", "source_locator": "Sec 1", **extra}


# -- all 24 medication identities -------------------------------------------------

def test_catalog_has_the_24_expected_identities():
    assert len(NAMES) == 24
    assert len(set(NAMES)) == 24


@pytest.mark.parametrize("name", NAMES)
def test_every_medication_resolves_and_is_not_assessed_without_approved_knowledge(name):
    profile = build_medication_profile(KnowledgeView.load(KNOWLEDGE, "legacy_development"), name)
    assert profile["medication"]["canonical_name"] == name
    assert profile["assessment_state"] == "not_assessed"
    assert profile["sections_with_approved_findings"] == 0
    assert set(profile["domains"]) == set(DOMAIN_ORDER)
    for section in [*profile["domains"].values(), profile["drug_drug_interactions"]]:
        assert section["findings"] == []
        assert section["status"] in {"not_assessed", "awaiting_approval"}
        assert section["missing_evidence"]
    assert profile["knowledge"]["clinical_use_permitted"] is False
    assert "Educational demonstrator" in profile["disclaimer"]


def test_aliases_resolve_to_canonical_names():
    view = KnowledgeView.load(KNOWLEDGE, "legacy_development")
    assert view.resolve("Paracetamol") == "acetaminophen"
    assert view.resolve("  WARFARIN ") == "warfarin"


@pytest.mark.parametrize("bad", ["", "   ", "notamedication", "x" * 500, None])
def test_unknown_medication_lookup_fails_closed(bad):
    with pytest.raises(UnknownMedicationLookup):
        build_medication_profile(KnowledgeView.load(KNOWLEDGE, "legacy_development"), bad)


def test_catalog_overview_lists_all_24_without_claiming_assessment():
    overview = build_catalog_overview(KnowledgeView.load(KNOWLEDGE, "legacy_development"))
    assert overview["medication_count"] == 24
    assert all(row["assessment_state"] == "not_assessed" for row in overview["medications"])


# -- approval boundary --------------------------------------------------------------

def test_development_data_is_never_presented_as_approved_even_if_it_claims_approval():
    view = _view({"precautions": [_record()]}, authoritative=False)
    section = build_medication_profile(view, "warfarin")["domains"]["precautions"]
    assert section["findings"] == []
    assert section["status"] == "awaiting_approval"
    assert "Synthetic statement" not in json.dumps(section)  # claim text withheld


def test_unapproved_and_rejected_assertions_are_excluded_and_text_withheld():
    records = [_record(assertion_id="P-1", review_status="needs_clinical_review"),
               _record(assertion_id="R-1", review_status="rejected"),
               _record(assertion_id="W-1", review_status="withdrawn"),
               _record(assertion_id="N-1", conflict_status="not_assessed")]
    section = build_medication_profile(_view({"precautions": records}), "warfarin")["domains"]["precautions"]
    assert section["counts"] == {"approved": 0, "awaiting_approval": 4, "conflicting": 0}
    assert section["findings"] == []
    assert "Synthetic statement" not in json.dumps(section)


def test_approved_finding_carries_full_traceability():
    sources = {"SRC-1": {"source_id": "SRC-1", "publisher": "Synthetic Publisher", "document_title": "Synthetic label",
                         "canonical_url": "https://example.gov/x", "retrieved_at": "2026-01-01", "jurisdiction": "US",
                         "verification_status": "integrity_verified_clinical_review_recorded"}}
    view = _view({"precautions": [_record(applicability_notes="adults only")]}, sources=sources)
    finding = build_medication_profile(view, "warfarin")["domains"]["precautions"]["findings"][0]
    assert finding["assertion_id"] == "A-1" and finding["medication"] == "warfarin" and finding["domain"] == "precautions"
    assert finding["statement"] == "Synthetic statement."
    assert finding["evidence_source_ids"] == ["SRC-1"]
    assert finding["sources"][0]["publisher"] == "Synthetic Publisher"
    assert finding["sources"][0]["canonical_url"] == "https://example.gov/x"
    assert finding["source_locator"] == "Sec 1"
    assert finding["evidence_strength"] == "moderate"
    assert finding["review_status"] == "clinically_approved"
    assert finding["conflict_status"] == "no_known_conflict"
    assert finding["applicability"] == {"jurisdiction": "US", "notes": "adults only"}
    assert finding["is_patient_specific_recommendation"] is False


def test_assessment_state_is_partial_when_only_some_sections_have_approved_findings():
    profile = build_medication_profile(_view({"precautions": [_record()]}), "warfarin")
    assert profile["assessment_state"] == "partial"
    assert profile["sections_with_approved_findings"] == 1
    assert profile["domains"]["adverse_effects"]["status"] == "not_assessed"


def test_other_medications_are_not_given_this_medications_findings():
    profile = build_medication_profile(_view({"precautions": [_record()]}), "metformin")
    assert profile["domains"]["precautions"]["findings"] == []


# -- conflicts and missing knowledge ------------------------------------------------

def test_conflicting_evidence_is_listed_by_id_and_excluded():
    record = _record(assertion_id="C-1", conflict_status="conflicting_evidence")
    section = build_medication_profile(_view({"precautions": [record]}), "warfarin")["domains"]["precautions"]
    assert section["status"] == "conflicting_evidence"
    assert section["findings"] == []
    assert section["conflicting_evidence"][0]["assertion_id"] == "C-1"
    assert section["counts"]["conflicting"] == 1
    assert "Synthetic statement" not in json.dumps(section)


def test_resolved_conflict_requires_a_resolution_to_be_usable():
    unresolved = _record(conflict_status="resolved")
    resolved = _record(conflict_status="resolved", conflict_resolution="Reviewer reconciled sources.")
    assert build_medication_profile(_view({"precautions": [unresolved]}), "warfarin")["domains"]["precautions"]["findings"] == []
    finding = build_medication_profile(_view({"precautions": [resolved]}), "warfarin")["domains"]["precautions"]["findings"][0]
    assert finding["conflict_resolution"] == "Reviewer reconciled sources."


def test_record_without_evidence_source_is_not_usable():
    section = build_medication_profile(_view({"precautions": [_record(evidence_source_ids=[])]}), "warfarin")["domains"]["precautions"]
    assert section["findings"] == []


def test_missing_domains_are_reported_as_missing_evidence_not_negative_findings():
    profile = build_medication_profile(_view({}), "warfarin")
    for section in profile["domains"].values():
        assert section["status"] == "not_assessed"
        assert section["missing_evidence"]
    assert "never absence of risk" in profile["interpretation"]


# -- dosage and drug-drug interaction assessment ----------------------------------------

def test_dosage_reference_is_source_scoped_and_never_patient_specific():
    record = _record(indication="synthetic indication", population="synthetic adults", dose_text="Source text", route="oral",
                     frequency="per source", patient_specific=False)
    finding = build_medication_profile(_view({"dosage_references": [record]}), "warfarin")["domains"]["dosage_references"]["findings"][0]
    assert finding["dosage_reference"]["patient_specific"] is False
    assert finding["dosage_reference"]["dose_text"] == "Source text"
    assert finding["is_patient_specific_recommendation"] is False


def test_drug_interaction_section_separates_approved_from_unreviewed_rules():
    rules = [
        {"rule_id": "R-A", "medication_a": "warfarin", "medication_b": "aspirin", "severity": "severe", "evidence": "strong",
         "description": "Synthetic approved interaction.", "source": "Synthetic", "evidence_source_ids": ["SRC-1"], "review_status": "clinically_approved"},
        {"rule_id": "R-B", "medication_a": "warfarin", "medication_b": "ibuprofen", "severity": "severe",
         "description": "Synthetic unreviewed interaction.", "evidence_source_ids": ["SRC-1"], "review_status": "needs_clinical_review"},
    ]
    ddi = build_medication_profile(_view(rules=rules), "warfarin")["drug_drug_interactions"]
    assert [r["partner"] for r in ddi["findings"]] == ["aspirin"]
    assert [r["partner"] for r in ddi["awaiting_approval"]] == ["ibuprofen"]
    assert "unreviewed interaction" not in json.dumps(ddi)
    # symmetric: the partner sees the same rule
    assert build_medication_profile(_view(rules=rules), "aspirin")["drug_drug_interactions"]["findings"][0]["partner"] == "warfarin"


def test_shipped_unreviewed_rules_appear_as_awaiting_approval_without_claim_text():
    ddi = build_medication_profile(KnowledgeView.load(KNOWLEDGE, "legacy_development"), "warfarin")["drug_drug_interactions"]
    assert ddi["counts"]["approved"] == 0 and ddi["counts"]["awaiting_approval"] > 0
    assert all("statement" not in row and "description" not in row for row in ddi["awaiting_approval"])


# -- governance pipeline ----------------------------------------------------------

def test_every_new_domain_has_a_candidate_type_and_validator():
    assert set(CANDIDATE_TYPE_TO_DOMAIN.values()) == set(ALL_DOMAINS)
    assert len(EXTENDED_DOMAINS) == 8


@pytest.mark.parametrize("kind", [k for k in RULES if k in {
    "medication_overview", "drug_class", "therapeutic_category", "mechanism_of_action", "approved_indication",
    "precaution", "adverse_effect", "drug_supplement_interaction"}])
def test_new_candidate_types_require_a_source_locator(tmp_path, kind):
    staging, evidence = _evidence(tmp_path)
    rule = {k: v for k, v in RULES[kind].items() if k != "source_locator"}
    with pytest.raises(CurationError, match="source_locator"):
        create_candidate(kind, rule, [evidence.record_id], "author", "Synthetic", staging, tmp_path / "curation")


def test_new_candidates_cannot_be_approved_without_explicit_conflict_assessment(tmp_path):
    staging, evidence = _evidence(tmp_path)
    curation = tmp_path / "curation"
    rule = _statement_rule(conflict_status="not_assessed")
    candidate = create_candidate("precaution", rule, [evidence.record_id], "author", "Synthetic", staging, curation)
    with pytest.raises(CurationError, match="conflict assessment"):
        record_clinical_decision(candidate["candidate_id"], "approved", "doctor", "physician", "Review", curation, staging)


def test_author_cannot_approve_their_own_new_candidate(tmp_path):
    staging, evidence = _evidence(tmp_path)
    curation = tmp_path / "curation"
    candidate = create_candidate("precaution", _statement_rule(), [evidence.record_id], "same-person", "Synthetic", staging, curation)
    with pytest.raises(CurationError, match="own candidate"):
        record_clinical_decision(candidate["candidate_id"], "approved", "same-person", "physician", "Review", curation, staging)


def test_released_validator_rejects_unapproved_and_unlocated_records():
    payload = {"schema_version": "1.0.0", **{d: [] for d in ALL_DOMAINS}}
    payload["precautions"] = [{"assertion_id": "X", "medication": "warfarin", "statement": "s", "review_status": "needs_clinical_review",
                               "evidence_strength": "moderate", "source_quality_tier": "not_assessed", "conflict_status": "no_known_conflict",
                               "source": "s", "evidence_source_ids": ["SRC"], "jurisdiction": "US"}]
    errors = validate_clinical_assertions(payload, {"warfarin"}, {"SRC"})
    assert any("clinically_approved" in e for e in errors)
    assert any("source_locator is required" in e for e in errors)


def test_older_datasets_without_extended_domains_remain_valid():
    legacy = {"schema_version": "1.0.0", "drug_food_interactions": [], "contraindications": [],
              "dosage_references": [], "administration_instructions": []}
    assert validate_clinical_assertions(legacy, {"warfarin"}, set()) == []


def test_full_pipeline_all_twelve_domains_reach_the_profile_only_through_an_active_release(tmp_path):
    knowledge, release_id = _active_release(tmp_path)
    view = KnowledgeView.load(knowledge, "active_release")
    assert view.authoritative and view.release == release_id
    profile = build_medication_profile(view, "warfarin")
    assert profile["assessment_state"] == "partial"  # no interaction rule was released
    for domain in DOMAIN_ORDER:
        section = profile["domains"][domain]
        assert section["status"] == "approved_findings", domain
        finding = section["findings"][0]
        assert finding["assertion_id"].startswith(DOMAIN_TO_CANDIDATE_TYPE[domain].upper() + "-KNC-")
        assert finding["sources"][0]["publisher"] == "Synthetic regulator fixture"
        assert finding["sources"][0]["canonical_url"] == "https://api.fda.gov/test/task15-label"
        assert finding["sources"][0]["source_id"].startswith("SRC-")
        assert finding["sources"][0]["resolved"] is True
        assert finding["review_status"] == "clinically_approved"
    assert profile["domains"]["precautions"]["findings"][0]["source_locator"] == "Synthetic section 1"
    # another medication in the same release has no approved knowledge
    assert build_medication_profile(view, "metformin")["assessment_state"] == "not_assessed"


def test_active_release_mode_fails_closed_without_an_active_release(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    from services.knowledge_release import KnowledgeReleaseError
    with pytest.raises(KnowledgeReleaseError):
        KnowledgeView.load(knowledge, "active_release")


def test_duplicate_new_assertions_cannot_enter_one_release(tmp_path):
    staging, evidence = _evidence(tmp_path)
    curation = tmp_path / "curation"
    ids = []
    for author in ("a1", "a2"):
        candidate = create_candidate("precaution", _statement_rule(), [evidence.record_id], author, "Synthetic", staging, curation)
        record_clinical_decision(candidate["candidate_id"], "approved", "pharmacist", "clinical_pharmacist", "Synthetic", curation, staging)
        ids.append(candidate["candidate_id"])
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "release_governance_policy.json").write_bytes((KNOWLEDGE / "release_governance_policy.json").read_bytes())
    (knowledge / "interaction_rules.json").write_text(json.dumps({"medications": {"warfarin": "11289"}, "interaction_rules": []}), encoding="utf-8")
    from services.knowledge_release import KnowledgeReleaseError
    with pytest.raises(KnowledgeReleaseError, match="duplicate"):
        create_release(ids, "steward", "Synthetic", curation, staging, knowledge)


# -- coverage report ------------------------------------------------------------------------

def test_coverage_report_covers_all_domains_and_never_claims_assessment():
    report = build_coverage_report(KNOWLEDGE)
    assert report["medication_count"] == 24
    assert set(report["monograph_domains"]) == set(EXTENDED_DOMAINS)
    for domain in report["monograph_domains"].values():
        assert domain["counts"]["not_evaluated"] == 24
        assert domain["counts"]["assertion_present_reviewed"] == 0


# -- label drafting (authoring aid) --------------------------------------------------------------

LABEL = {"results": [{
    "set_id": "synthetic-set", "version": "7", "effective_time": "20260101",
    "openfda": {"generic_name": ["WARFARIN SODIUM"], "pharm_class_epc": ["Synthetic Class [EPC]"]},
    "indications_and_usage": ["Synthetic   indication\ntext."],
    "contraindications": ["Synthetic contraindication text."],
    "adverse_reactions": ["x" * 2500],
    "drug_interactions": ["Synthetic interaction text."],
}]}
META = {"publisher": "Synthetic Publisher", "document_title": "Synthetic label", "jurisdiction": "US"}


def test_drafting_copies_text_verbatim_and_never_assesses_evidence():
    result = draft_from_openfda_label(LABEL, META, "warfarin")
    by_type = {d["candidate_type"]: d for d in result["drafts"]}
    indication = by_type["approved_indication"]["rule"]
    assert indication["statement"] == "Synthetic indication text."  # whitespace collapsed only
    assert indication["evidence_strength"] == "unknown"
    assert indication["conflict_status"] == "not_assessed" and indication["source_quality_tier"] == "not_assessed"
    assert "set_id=synthetic-set" in indication["source_locator"] and "field=indications_and_usage[0]" in indication["source_locator"]
    assert by_type["drug_class"]["rule"]["statement"] == "Synthetic Class [EPC]"
    assert result["manual_review_sections"] == ["drug_interactions"]
    assert any(s["field"] == "adverse_reactions" for s in result["skipped"])  # too long: author must excerpt


def test_structured_sections_are_incomplete_and_fail_candidate_validation(tmp_path):
    result = draft_from_openfda_label(LABEL, META, "warfarin")
    draft = next(d for d in result["drafts"] if d["candidate_type"] == "contraindication")
    assert draft["draft_status"] == "needs_author_completion"
    assert "condition_or_population" in draft["missing_required_fields"]
    staging, evidence = _evidence(tmp_path)
    with pytest.raises(CurationError):
        create_candidate("contraindication", draft["rule"], [evidence.record_id], "author", "Synthetic", staging, tmp_path / "curation")


def test_drafting_refuses_a_label_for_a_different_product():
    with pytest.raises(LabelDraftingError, match="different product"):
        draft_from_openfda_label(LABEL, META, "metformin")


def test_drafting_rejects_non_label_payloads():
    with pytest.raises(LabelDraftingError):
        draft_from_openfda_label({"data": []}, META, "warfarin")


def test_drafts_are_written_without_overwriting_and_touch_no_runtime_files(tmp_path):
    before = (KNOWLEDGE / "clinical_assertions.json").read_bytes()
    result = draft_from_openfda_label(LABEL, META, "warfarin")
    written = write_drafts(result, tmp_path / "drafts")
    assert any(p.name.endswith("-index.json") for p in written)
    with pytest.raises(LabelDraftingError, match="overwrite"):
        write_drafts(result, tmp_path / "drafts")
    assert (KNOWLEDGE / "clinical_assertions.json").read_bytes() == before


def test_a_complete_draft_can_become_a_candidate_but_stays_unapproved(tmp_path):
    result = draft_from_openfda_label(LABEL, META, "warfarin")
    draft = next(d for d in result["drafts"] if d["candidate_type"] == "approved_indication")
    staging, evidence = _evidence(tmp_path)
    candidate = create_candidate("approved_indication", draft["rule"], [evidence.record_id], "author", "Synthetic", staging, tmp_path / "curation")
    assert candidate["candidate_status"] == "pending_clinical_approval"
    assert candidate["promotion_status"] == "not_promoted"
    assert candidate["rule"]["evidence_strength"] == "unknown"


# -- HTTP API ---------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("RXLOGIC_KNOWLEDGE_MODE", raising=False)
    monkeypatch.delenv("RXLOGIC_KNOWLEDGE_ROOT", raising=False)
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)
    app.register_blueprint(knowledge_api)
    return app.test_client()


def test_api_lists_all_24_medications(client):
    body = client.get("/api/medications").get_json()
    assert body["medication_count"] == 24
    assert {m["canonical_name"] for m in body["medications"]} == set(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_api_returns_a_profile_for_each_medication(client, name):
    response = client.get(f"/api/medications/{name}/clinical")
    assert response.status_code == 200
    body = response.get_json()
    assert body["medication"]["canonical_name"] == name
    assert body["assessment_state"] == "not_assessed"
    assert body["knowledge"]["clinical_use_permitted"] is False


def test_api_resolves_aliases_and_rejects_unknown_names(client):
    assert client.get("/api/medications/paracetamol/clinical").get_json()["medication"]["canonical_name"] == "acetaminophen"
    missing = client.get("/api/medications/notadrug/clinical")
    assert missing.status_code == 404
    assert missing.get_json()["error"] == "unknown_medication"


def test_api_profile_matches_the_contract_the_frontend_consumes(client):
    body = client.get("/api/medications/warfarin/clinical").get_json()
    assert {"medication", "knowledge", "assessment_state", "sections_with_approved_findings", "section_count",
            "domains", "drug_drug_interactions", "interpretation", "disclaimer"} <= set(body)
    section = body["domains"]["contraindications"]
    assert {"domain", "label", "status", "counts", "findings", "awaiting_approval", "conflicting_evidence", "missing_evidence"} <= set(section)
    assert {"approved", "awaiting_approval", "conflicting"} == set(section["counts"])


def test_api_serves_approved_findings_from_an_active_release(tmp_path, monkeypatch):
    knowledge, release_id = _active_release(tmp_path)
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "active_release")
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_ROOT", str(knowledge))
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)
    app.register_blueprint(knowledge_api)
    body = app.test_client().get("/api/medications/warfarin/clinical").get_json()
    assert body["knowledge"]["release"] == release_id
    assert body["domains"]["mechanisms_of_action"]["findings"][0]["statement"] == "Synthetic mechanism."


def test_api_fails_closed_when_the_active_release_is_unavailable(tmp_path, monkeypatch):
    (tmp_path / "empty").mkdir()
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "active_release")
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_ROOT", str(tmp_path / "empty"))
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)
    app.register_blueprint(knowledge_api)
    response = app.test_client().get("/api/medications/warfarin/clinical")
    assert response.status_code == 503
    assert response.get_json()["error"] == "approved_knowledge_unavailable"


def test_api_rejects_invalid_knowledge_mode(client, monkeypatch):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "bogus")
    assert client.get("/api/medications/warfarin/clinical").status_code == 503



# -- audit additions: approval strictness, evidence linkage, error hygiene ------------------------

def _rule(**extra):
    return {"rule_id": "R-X", "medication_a": "warfarin", "medication_b": "aspirin", "severity": "severe", "evidence": "strong",
            "description": "Synthetic interaction text.", "source": "Synthetic", "evidence_source_ids": ["SRC-1"],
            "review_status": "clinically_approved", **extra}


def test_development_record_claiming_approval_is_labelled_unverified_not_approved():
    view = _view({"precautions": [_record()]}, authoritative=False)
    entry = build_medication_profile(view, "warfarin")["domains"]["precautions"]["awaiting_approval"][0]
    assert entry["review_status"] == "unverified_development_record"
    assert entry["recorded_review_status"] == "clinically_approved"
    assert entry["exclusion_reason"] == "development_record_not_an_approval_authority"


def test_exclusion_reasons_distinguish_unapproved_from_missing_conflict_assessment():
    records = [_record(assertion_id="P-1", review_status="needs_clinical_review"),
               _record(assertion_id="R-1", review_status="rejected"),
               _record(assertion_id="N-1", conflict_status="not_assessed"),
               _record(assertion_id="E-1", evidence_source_ids=[])]
    entries = {e["assertion_id"]: e["exclusion_reason"] for e in
               build_medication_profile(_view({"precautions": records}), "warfarin")["domains"]["precautions"]["awaiting_approval"]}
    assert entries == {"P-1": "awaiting_clinical_approval", "R-1": "review_rejected",
                       "N-1": "conflict_assessment_missing", "E-1": "no_evidence_source"}


def test_legacy_reviewed_state_is_not_clinical_approval_for_interactions():
    ddi = build_medication_profile(_view(rules=[_rule(review_status="reviewed")]), "warfarin")["drug_drug_interactions"]
    assert ddi["findings"] == [] and ddi["status"] == "awaiting_approval"
    assert "Synthetic interaction text" not in json.dumps(ddi)


def test_interaction_without_evidence_source_is_not_approved():
    ddi = build_medication_profile(_view(rules=[_rule(evidence_source_ids=[])]), "warfarin")["drug_drug_interactions"]
    assert ddi["findings"] == [] and ddi["counts"]["awaiting_approval"] == 1


def test_interaction_with_conflicting_evidence_is_reported_as_conflict_not_finding():
    ddi = build_medication_profile(_view(rules=[_rule(conflict_status="conflicting_evidence")]), "warfarin")["drug_drug_interactions"]
    assert ddi["findings"] == [] and ddi["status"] == "conflicting_evidence"
    assert ddi["counts"] == {"approved": 0, "awaiting_approval": 0, "conflicting": 1}
    assert "Synthetic interaction text" not in json.dumps(ddi)


def test_interaction_source_locator_is_preserved():
    ddi = build_medication_profile(_view(rules=[_rule(source_locator="Section 7.1")]), "warfarin")["drug_drug_interactions"]
    assert ddi["findings"][0]["source_locator"] == "Section 7.1"


def test_unresolved_source_reference_is_flagged_on_an_approved_finding():
    view = _view({"precautions": [_record(evidence_source_ids=["SRC-MISSING"])]})
    finding = build_medication_profile(view, "warfarin")["domains"]["precautions"]["findings"][0]
    assert finding["all_sources_resolved"] is False
    assert finding["sources"][0]["resolved"] is False
    resolved = build_medication_profile(_view({"precautions": [_record()]}), "warfarin")["domains"]["precautions"]["findings"][0]
    assert resolved["all_sources_resolved"] is True


def test_records_filed_under_an_alias_are_shown_under_the_canonical_medication():
    view = _view({"precautions": [_record(medication="Paracetamol", assertion_id="ALIAS-1")]})
    assert [f["assertion_id"] for f in build_medication_profile(view, "acetaminophen")["domains"]["precautions"]["findings"]] == ["ALIAS-1"]
    assert build_medication_profile(view, "warfarin")["domains"]["precautions"]["findings"] == []


@pytest.mark.parametrize("name", NAMES)
def test_every_medication_receives_only_its_own_findings(name):
    records = {domain: [_record(assertion_id=f"{domain}-{m}", medication=m, statement=f"Synthetic for {m}.") for m in NAMES]
               for domain in ("precautions", "adverse_effects")}
    profile = build_medication_profile(_view(records), name)
    for domain in ("precautions", "adverse_effects"):
        findings = profile["domains"][domain]["findings"]
        assert [f["assertion_id"] for f in findings] == [f"{domain}-{name}"]
        assert findings[0]["medication"] == name
    # domains with no records for anyone stay not assessed
    assert profile["domains"]["mechanisms_of_action"]["status"] == "not_assessed"
    assert profile["medication"]["rxcui"] == next(r["rxcui"] for r in CATALOG["medications"] if r["canonical_name"] == name)


def test_api_does_not_leak_filesystem_paths_when_knowledge_files_are_unreadable(tmp_path, monkeypatch):
    broken = tmp_path / "secret-dir-name"
    broken.mkdir()
    (broken / "medication_catalog.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "legacy_development")
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_ROOT", str(broken))
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)
    app.register_blueprint(knowledge_api)
    response = app.test_client().get("/api/medications/warfarin/clinical")
    assert response.status_code == 503
    assert "secret-dir-name" not in response.get_data(as_text=True)
    assert "{not json" not in response.get_data(as_text=True)
