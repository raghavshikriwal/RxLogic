from __future__ import annotations

import json
import shutil
from pathlib import Path

from services.task11_audit import audit_task11

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY = PROJECT_ROOT / "knowledge" / "release_governance_policy.json"


def _knowledge_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    root.mkdir()
    shutil.copy2(POLICY, root / POLICY.name)
    return root


def test_task11_audit_passes_for_empty_fail_closed_development_root(tmp_path):
    root = _knowledge_root(tmp_path)
    report = audit_task11(root)
    assert report["passed"] is True
    assert report["active_release_status"] == "no_active_release_fail_closed"
    assert report["release_count"] == 0
    assert report["release_review_event_count"] == 0
    assert all(report["checks"].values())


def test_task11_audit_rejects_policy_with_missing_separation_control(tmp_path):
    root = _knowledge_root(tmp_path)
    path = root / POLICY.name
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["separation_of_duties"]["promoter_differs_from_creator_and_all_reviewers"] = False
    path.write_text(json.dumps(policy), encoding="utf-8")
    report = audit_task11(root)
    assert report["passed"] is False
    assert report["checks"]["versioned_dual_control_policy_valid"] is False


def test_task11_audit_rejects_tampered_release_review_log(tmp_path):
    root = _knowledge_root(tmp_path)
    (root / "release_review_events.jsonl").write_text('{"event":"release_review"}\n', encoding="utf-8")
    report = audit_task11(root)
    assert report["passed"] is False
    assert report["checks"]["release_review_log_hash_chain_valid"] is False
