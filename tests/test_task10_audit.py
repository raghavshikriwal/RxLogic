from pathlib import Path
from services.task10_audit import build_task10_audit


def test_task10_audit_passes_software_safety_checks_without_claiming_clinical_validation():
    root = Path(__file__).resolve().parent.parent / "knowledge"
    report = build_task10_audit(root)
    assert report["passed"] is True
    assert report["clinical_validation_status"] == "not_performed"
    assert report["case_counts"]["adjudicated_clinical_reference"] == 0
    assert report["clinical_performance_metrics"] is None
    assert report["runtime_probe"]["clinical_use_permitted"] is False
    assert report["runtime_probe"]["finding_count"] == 0
