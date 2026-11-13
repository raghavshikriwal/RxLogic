"""Validate the medication identity catalog and its runtime mapping."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from services.medication_catalog import PROJECT_ROOT, audit_catalog_against_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=PROJECT_ROOT / 'knowledge' / 'medication_catalog.json')
    parser.add_argument('--interaction-rules', type=Path, default=PROJECT_ROOT / 'knowledge' / 'interaction_rules.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    report = audit_catalog_against_runtime(args.catalog, args.interaction_rules)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
        print(f'Medication catalog audit written to {args.output}')
    else:
        print(rendered, end='')
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
