"""Print an evidence-aware inventory of medication knowledge coverage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.knowledge_coverage import DEFAULT_KNOWLEDGE_ROOT, build_coverage_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-root", type=Path, default=DEFAULT_KNOWLEDGE_ROOT)
    parser.add_argument("--output", type=Path, help="Optional path for a JSON report")
    args = parser.parse_args(argv)
    report = build_coverage_report(args.knowledge_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Coverage report written to {args.output}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
