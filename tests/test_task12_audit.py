from __future__ import annotations

from app import create_app
from services.task12_audit import run_task12_audit


def test_task12_security_acceptance_audit_passes_for_development_app():
    app = create_app()
    app.config["TESTING"] = True
    report = run_task12_audit(app)

    assert report["passed"] is True
    assert report["audit_type"] == "task12_web_application_security_hardening_audit"
    assert all(report["checks"].values())
    assert report["runtime"]["clinical_use_permitted"] is False
    assert report["runtime"]["governance_admin_http_routes"] == []
    assert any("not a user login" in item for item in report["limitations"])
