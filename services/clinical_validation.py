"""Clinical validation dataset governance and evaluation metrics (Task 10).

This module evaluates reviewer-adjudicated reference cases. It does not create
clinical labels, approve knowledge, or infer clinical truth from missing data.
Reviewer identity/credentials must be authenticated by an external trusted
workflow; strings in a JSON file are not proof of professional credentials.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

SCHEMA_VERSION = "1.0.0"
DOMAINS = frozenset({
    "drug_drug_interactions", "drug_food_interactions", "contraindications",
    "dosage_references", "administration_instructions",
})
OUTCOMES = frozenset({"finding_present", "insufficient_approved_knowledge"})
REVIEWER_ROLES = frozenset({"clinical_pharmacist", "physician"})


class ClinicalValidationError(ValueError):
    """Raised when a clinical validation dataset or evaluation is malformed."""


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_validation_dataset(
    payload: dict[str, Any], *, assertion_ids: set[str] | None = None,
    source_ids: set[str] | None = None,
) -> list[str]:
    """Return schema/governance errors; never determine whether a claim is true."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["validation dataset root must be an object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return errors + ["cases must be an array"]
    seen: set[str] = set()
    for i, case in enumerate(cases):
        prefix = f"cases[{i}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix}: case must be an object")
            continue
        case_id = case.get("case_id")
        if not _nonempty(case_id):
            errors.append(f"{prefix}: case_id is required")
        elif case_id in seen:
            errors.append(f"{prefix}: duplicate case_id {case_id}")
        else:
            seen.add(case_id)
        if case.get("case_type") not in {"software_invariant", "clinical_reference"}:
            errors.append(f"{prefix}: invalid case_type")
        if case.get("domain") not in DOMAINS:
            errors.append(f"{prefix}: invalid domain")
        if not _nonempty(case.get("scenario")):
            errors.append(f"{prefix}: scenario is required")
        context = case.get("input_context")
        if not isinstance(context, dict):
            errors.append(f"{prefix}: input_context must be an object")
        else:
            meds = context.get("medications")
            if not isinstance(meds, list) or not meds or any(not _nonempty(x) for x in meds):
                errors.append(f"{prefix}: medications must be a non-empty array of names")
            for field in ("foods", "conditions"):
                values = context.get(field, [])
                if not isinstance(values, list) or any(not _nonempty(x) for x in values):
                    errors.append(f"{prefix}: {field} must be an array of non-empty strings")
        if case.get("case_type") == "software_invariant":
            if case.get("adjudication_state") != "not_applicable":
                errors.append(f"{prefix}: software_invariant cases must use not_applicable adjudication")
            if case.get("reference_outcome") is not None:
                errors.append(f"{prefix}: software_invariant cases cannot carry a clinical reference outcome")
            if case.get("reviewer_decisions", []) != []:
                errors.append(f"{prefix}: software_invariant cases cannot carry clinical reviewer decisions")
            continue
        state = case.get("adjudication_state")
        if state not in {"not_adjudicated", "adjudicated"}:
            errors.append(f"{prefix}: invalid adjudication_state")
        outcome = case.get("reference_outcome")
        if state == "not_adjudicated" and outcome is not None:
            errors.append(f"{prefix}: unadjudicated case must not have reference_outcome")
        if state == "adjudicated" and outcome not in OUTCOMES:
            errors.append(f"{prefix}: adjudicated case requires a valid reference_outcome")
        decisions = case.get("reviewer_decisions")
        if not isinstance(decisions, list):
            errors.append(f"{prefix}: reviewer_decisions must be an array")
            continue
        reviewer_ids: set[str] = set()
        for j, decision in enumerate(decisions):
            dp = f"{prefix}.reviewer_decisions[{j}]"
            if not isinstance(decision, dict):
                errors.append(f"{dp}: decision must be an object")
                continue
            rid, role = decision.get("reviewer_id"), decision.get("reviewer_role")
            if not _nonempty(rid):
                errors.append(f"{dp}: reviewer_id is required")
            elif rid in reviewer_ids:
                errors.append(f"{dp}: reviewer IDs must be distinct")
            else:
                reviewer_ids.add(rid)
            if role not in REVIEWER_ROLES:
                errors.append(f"{dp}: reviewer_role must be clinical_pharmacist or physician")
            if decision.get("outcome") not in OUTCOMES:
                errors.append(f"{dp}: invalid outcome")
            if not _nonempty(decision.get("rationale")):
                errors.append(f"{dp}: rationale is required")
            refs = decision.get("evidence_source_ids")
            if not isinstance(refs, list) or not refs or any(not _nonempty(x) for x in refs):
                errors.append(f"{dp}: evidence_source_ids must be a non-empty array")
            elif source_ids is not None:
                for ref in refs:
                    if ref not in source_ids:
                        errors.append(f"{dp}: unknown evidence source {ref!r}")
        if state == "adjudicated":
            if len(decisions) < 2 or len(reviewer_ids) < 2:
                errors.append(f"{prefix}: adjudication requires at least two distinct reviewers")
            if assertion_ids is not None:
                for ref in case.get("related_assertion_ids", []):
                    if ref not in assertion_ids:
                        errors.append(f"{prefix}: unknown related assertion {ref!r}")
            refs = case.get("reference_evidence_source_ids")
            if not isinstance(refs, list) or not refs or any(not _nonempty(x) for x in refs):
                errors.append(f"{prefix}: adjudicated case requires reference_evidence_source_ids")
            elif source_ids is not None:
                for ref in refs:
                    if ref not in source_ids:
                        errors.append(f"{prefix}: unknown reference evidence source {ref!r}")
            adjudication = case.get("adjudication")
            if not isinstance(adjudication, dict):
                errors.append(f"{prefix}: adjudication record is required")
            else:
                if not _nonempty(adjudication.get("adjudicator_id")):
                    errors.append(f"{prefix}: adjudicator_id is required")
                if adjudication.get("adjudicator_role") not in REVIEWER_ROLES:
                    errors.append(f"{prefix}: adjudicator_role is not authorized")
                if not _nonempty(adjudication.get("rationale")):
                    errors.append(f"{prefix}: adjudication rationale is required")
                if adjudication.get("outcome") != outcome:
                    errors.append(f"{prefix}: adjudication outcome must match reference_outcome")
                if adjudication.get("adjudicator_id") in reviewer_ids:
                    errors.append(f"{prefix}: adjudicator must be independent of the two reviewers")
    return errors


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def evaluate_predictions(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Calculate binary metrics only for explicitly adjudicated, valid outcomes.

    Positive class is `finding_present`. Rows must contain reference_outcome and
    predicted_outcome. Missing or unadjudicated labels are rejected, not dropped.
    """
    materialized = list(rows)
    if not materialized:
        return {"status": "not_evaluable", "n": 0, "metrics": None,
                "reason": "No adjudicated reference cases were supplied."}
    tp = tn = fp = fn = 0
    for i, row in enumerate(materialized):
        if not isinstance(row, dict):
            raise ClinicalValidationError(f"row {i} must be an object")
        actual, predicted = row.get("reference_outcome"), row.get("predicted_outcome")
        if actual not in OUTCOMES or predicted not in OUTCOMES:
            raise ClinicalValidationError(f"row {i} requires valid adjudicated and predicted outcomes")
        actual_positive, predicted_positive = actual == "finding_present", predicted == "finding_present"
        if actual_positive and predicted_positive: tp += 1
        elif actual_positive: fn += 1
        elif predicted_positive: fp += 1
        else: tn += 1
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    f1 = _ratio(2 * tp, 2 * tp + fp + fn)
    return {
        "status": "evaluated", "n": len(materialized),
        "confusion_matrix": {"true_positive": tp, "false_positive": fp,
                             "true_negative": tn, "false_negative": fn},
        "metrics": {"accuracy": _ratio(tp + tn, len(materialized)),
                    "precision": precision, "recall_sensitivity": recall,
                    "specificity": specificity, "f1": f1},
        "positive_class": "finding_present",
        "limitations": ["Metrics describe agreement with the supplied adjudicated dataset only.",
                        "They do not establish clinical safety, generalizability, or fitness for patient care."],
    }


def reviewer_agreement(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return raw agreement and Cohen's kappa for cases with exactly two reviewers."""
    pairs: list[tuple[str, str]] = []
    for case in cases:
        decisions = case.get("reviewer_decisions", [])
        if case.get("case_type") == "clinical_reference" and len(decisions) == 2:
            a, b = decisions[0].get("outcome"), decisions[1].get("outcome")
            if a in OUTCOMES and b in OUTCOMES:
                pairs.append((a, b))
    n = len(pairs)
    if not n:
        return {"status": "not_evaluable", "n": 0, "raw_agreement": None, "cohens_kappa": None}
    observed = sum(a == b for a, b in pairs) / n
    labels = tuple(OUTCOMES)
    a_counts = Counter(a for a, _ in pairs)
    b_counts = Counter(b for _, b in pairs)
    expected = sum((a_counts[label] / n) * (b_counts[label] / n) for label in labels)
    kappa = None if expected == 1 else round((observed - expected) / (1 - expected), 6)
    return {"status": "evaluated", "n": n, "raw_agreement": round(observed, 6), "cohens_kappa": kappa}
