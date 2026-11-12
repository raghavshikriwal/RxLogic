"""Run the Task 07 structural and governance acceptance audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.knowledge_coverage import DEFAULT_KNOWLEDGE_ROOT
from services.task07_audit import build_task07_audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-root", type=Path, default=DEFAULT_KNOWLEDGE_ROOT)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args(argv)
    report = build_task07_audit(args.knowledge_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Task 07 audit report written to {args.output}")
    else:
        print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
