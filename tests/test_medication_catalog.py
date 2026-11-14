from __future__ import annotations
import json
from pathlib import Path
import pytest
from services.medication_catalog import (
    DEFAULT_CATALOG_PATH, MedicationCatalogError, audit_catalog_against_runtime,
    catalog_maps, load_medication_catalog, validate_medication_catalog,
)
from services.name_normalizer import NameNormalizer
from services.rule_engine import RuleEngine
from models.schemas import Medication

ROOT = Path(__file__).resolve().parent.parent


def test_catalog_validates_and_matches_runtime_medication_map():
    catalog = load_medication_catalog()
    report = audit_catalog_against_runtime(DEFAULT_CATALOG_PATH, ROOT / 'knowledge' / 'interaction_rules.json')
    assert report['passed'] is True
    assert report['catalog_medication_count'] == 24
    assert validate_medication_catalog(catalog) == []


def test_paracetamol_resolves_to_acetaminophen_and_is_known():
    engine = RuleEngine()
    normalizer = NameNormalizer.from_file(engine.medication_rxcuis)
    resolution = normalizer.resolve('Paracetamol')
    assert resolution is not None
    assert resolution.canonical_name == 'acetaminophen'
    assert resolution.match.value == 'alias'
    assert engine.assess_coverage([]).total == 0
    normalized, _ = normalizer.normalize([])
    assert normalized == []
    assert 'acetaminophen' in engine.known_medications
    coverage = engine.assess_coverage([Medication(name='acetaminophen')])
    assert coverage.identity_only == ('acetaminophen',)


def test_catalog_does_not_claim_clinical_assertions_for_new_identity():
    catalog = load_medication_catalog()
    row = next(x for x in catalog['medications'] if x['canonical_name'] == 'acetaminophen')
    assert row['identity_status'] == 'added_task08_identity_only'
    clinical = json.loads((ROOT / 'knowledge' / 'clinical_assertions.json').read_text())
    assert all(not any(a.get('medication') == 'acetaminophen' for a in clinical.get(domain, []))
               for domain in ('drug_food_interactions','contraindications','dosage_references','administration_instructions'))


def test_catalog_rejects_duplicate_rxcui():
    catalog = load_medication_catalog()
    catalog['medications'][1]['rxcui'] = catalog['medications'][0]['rxcui']
    assert any('duplicate RxCUI' in error for error in validate_medication_catalog(catalog))


def test_catalog_rejects_alias_collision():
    catalog = load_medication_catalog()
    catalog['medications'][0]['aliases'].append('acetaminophen')
    assert any('collides with canonical' in error for error in validate_medication_catalog(catalog))


def test_catalog_loader_fails_closed_for_invalid_file(tmp_path):
    path = tmp_path / 'catalog.json'
    path.write_text('{"schema_version":"wrong"}', encoding='utf-8')
    with pytest.raises(MedicationCatalogError):
        load_medication_catalog(path)
