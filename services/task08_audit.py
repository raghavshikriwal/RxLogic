"""Task 08 medication-identity and evidence-coverage acceptance audit."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from services.knowledge_coverage import build_coverage_report
from services.knowledge_validation import validate_knowledge
from services.medication_catalog import audit_catalog_against_runtime


def build_task08_audit(knowledge_root: Path) -> dict[str, Any]:
    root = Path(knowledge_root)
    structural_errors = validate_knowledge(root)
    catalog = audit_catalog_against_runtime(root / 'medication_catalog.json', root / 'interaction_rules.json')
    coverage = build_coverage_report(root)
    assertions = json.loads((root / 'clinical_assertions.json').read_text(encoding='utf-8'))
    new_medication = next((row for row in json.loads((root / 'medication_catalog.json').read_text(encoding='utf-8'))['medications'] if row['canonical_name'] == 'acetaminophen'), None)
    checks = {
        'knowledge_structurally_valid': not structural_errors,
        'catalog_matches_runtime_medication_map': catalog['passed'],
        'acetaminophen_identity_is_registered': bool(new_medication and new_medication.get('rxcui') == '161'),
        'paracetamol_alias_is_registered': bool(new_medication and 'paracetamol' in new_medication.get('aliases', [])),
        'clinical_use_remains_prohibited': json.loads((root / 'manifest.json').read_text(encoding='utf-8')).get('publication_policy', {}).get('clinical_use_permitted') is False,
        'new_medication_has_no_fabricated_clinical_assertions': not any(
            row.get('medication') == 'acetaminophen'
            for domain in ('drug_food_interactions', 'contraindications', 'dosage_references', 'administration_instructions')
            for row in assertions.get(domain, [])
        ),
    }
    return {
        'schema_version': '1.0.0',
        'audit_type': 'task08_medication_identity_and_coverage_structural_audit_not_clinical_validation',
        'passed': all(checks.values()),
        'checks': checks,
        'validation_errors': structural_errors,
        'catalog_audit': catalog,
        'coverage_summary': {
            'medication_count': coverage['medication_count'],
            'drug_drug_interactions': coverage['drug_drug_interactions']['counts'],
            'drug_food_guidance': coverage['drug_food_guidance']['counts'],
            'contraindications': coverage['contraindications']['counts'],
            'dosage_references': coverage['dosage_references']['counts'],
            'administration_instructions': coverage['administration_instructions']['counts'],
        },
        'clinical_assertions_added_for_acetaminophen': 0,
        'limitations': [
            'Catalog identity is not clinical evidence.',
            'No drug interaction, food effect, contraindication, dosage, or administration claim is inferred for acetaminophen.',
            'Not-evaluated means unknown, not safe or risk-free.',
            'This report validates structure and governance only; it is not clinical validation or authorization for patient-care use.',
        ],
    }
