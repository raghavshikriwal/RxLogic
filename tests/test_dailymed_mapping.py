from services.dailymed_mapping import preview_dailymed_section_candidates


def test_maps_known_spl_sections_to_existing_canonical_domains_without_asserting():
    payload = {
        "set_id": "example-set",
        "spl_version": "3",
        "label_title": "Example label",
        "sections": [
            {"section_code": "34067-9", "section_title": "INDICATIONS AND USAGE", "original_text": "Verbatim indication text."},
            {"section_code": "34070-3", "section_title": "CONTRAINDICATIONS", "original_text": "Verbatim contraindication text."},
        ],
    }
    result = preview_dailymed_section_candidates(payload, "example medicine")
    assert result["mapped_count"] == 2
    assert result["previews"][0]["canonical_domain"] == "approved_indications"
    assert result["previews"][1]["canonical_domain"] == "contraindications"
    assert result["previews"][0]["source_excerpt"] == "Verbatim indication text."
    assert result["previews"][0]["source_locator"]["set_id"] == "example-set"
    assert result["governance"]["is_clinical_assertion"] is False
    assert result["previews"][0]["curation_record_created"] is False


def test_unknown_or_ambiguous_sections_remain_unmapped():
    result = preview_dailymed_section_candidates(
        {"sections": [{"section_title": "CLINICAL PHARMACOLOGY", "original_text": "Source text."}]},
        "example medicine",
    )
    item = result["previews"][0]
    assert item["mapping_status"] == "unmapped_human_classification_required"
    assert item["canonical_domain"] is None
    assert item["candidate_type"] is None


def test_rejects_missing_medication_or_invalid_sections():
    import pytest
    with pytest.raises(ValueError):
        preview_dailymed_section_candidates({"sections": []}, " ")
    with pytest.raises(ValueError):
        preview_dailymed_section_candidates({"sections": None}, "example")


def test_staged_evidence_preview_verifies_provenance_and_does_not_change_review_state(tmp_path):
    import json
    from pathlib import Path
    from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
    from services.evidence_review import list_review_queue
    from services.dailymed_mapping import preview_staged_dailymed_evidence

    payload = {
        "schema": "rxlogic.dailymed_spl_candidate.v1",
        "set_id": "123e4567-e89b-12d3-a456-426614174000",
        "spl_version": "1",
        "label_title": "Example",
        "sections": [{"section_code": "34067-9", "section_title": "INDICATIONS AND USAGE", "original_text": "Source excerpt."}],
    }
    doc = tmp_path / "candidate.json"
    doc.write_text(json.dumps(payload), encoding="utf-8")
    metadata = EvidenceMetadata(
        publisher="U.S. National Library of Medicine DailyMed",
        source_type="dailymed_spl", document_title="Example label",
        canonical_url="https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/123e4567-e89b-12d3-a456-426614174000.xml",
        jurisdiction="US",
    )
    staged = ingest_json_document(doc, metadata, staging_root=tmp_path / "staging")
    result = preview_staged_dailymed_evidence(staged.record_id, "example medicine", tmp_path / "staging")
    assert result["evidence"]["metadata_integrity"] == "verified"
    assert result["evidence"]["review_status"] == "pending_clinical_review"
    assert result["previews"][0]["canonical_domain"] == "approved_indications"
    assert list_review_queue(tmp_path / "staging", "pending_clinical_review")[0]["record_id"] == staged.record_id
