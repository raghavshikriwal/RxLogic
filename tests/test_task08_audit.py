from pathlib import Path
from services.task08_audit import build_task08_audit


def test_task08_audit_passes_structural_identity_and_governance_checks():
    root = Path(__file__).resolve().parent.parent / 'knowledge'
    report = build_task08_audit(root)
    assert report['passed'] is True
    assert report['checks']['acetaminophen_identity_is_registered'] is True
    assert report['checks']['paracetamol_alias_is_registered'] is True
    assert report['clinical_assertions_added_for_acetaminophen'] == 0
    assert report['coverage_summary']['drug_drug_interactions']['total'] == 276
    assert 'not clinical validation' in ' '.join(report['limitations']).lower()
