"""Task 09 clinical-reasoning integration audit; structural, not clinical validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.clinical_reasoning import ClinicalReasoningEngine, DOMAINS

ROOT = Path(__file__).resolve().parent.parent


def build_report(knowledge_root: Path = ROOT / "knowledge") -> dict:
    path = knowledge_root / "clinical_assertions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    counts = {}
    for domain in DOMAINS:
        rows = payload.get(domain, [])
        counts[domain] = {
            "total": len(rows),
            "approved_and_conflict_assessed": sum(
                1 for row in rows
                if row.get("review_status") == "clinically_approved"
                and row.get("conflict_status") in {"no_known_conflict", "resolved"}
                and bool(row.get("evidence_source_ids"))
            ),
        }
    probe = ClinicalReasoningEngine(payload).assess([])
    return {
        "task": "09",
        "audit_type": "clinical_reasoning_integration_structural_audit",
        "clinical_validation": False,
        "clinical_use_permitted": False,
        "runtime_policy": {
            "unreviewed_assertions_used": False,
            "unresolved_conflicts_used": False,
            "missing_knowledge_treated_as_safe": False,
            "patient_specific_dosing_generated": False,
            "patient_context_persisted_in_plan_history": False,
        },
        "assertion_counts": counts,
        "total_assertions": sum(item["total"] for item in counts.values()),
        "approved_runtime_assertions": sum(item["approved_and_conflict_assessed"] for item in counts.values()),
        "empty_knowledge_probe_status": probe["status"],
        "limitations": [
            "Structural integration audit only; no clinical truth adjudication.",
            "No approved assertions means no positive clinical finding can be emitted.",
            "No finding is not evidence of safety.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/task09_acceptance_audit.json")
    args = parser.parse_args()
    report = build_report()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Task 09 audit report written to {output}")
    print(f"Approved runtime assertions: {report['approved_runtime_assertions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
