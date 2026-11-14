"""Validate required deployment settings before starting a production release."""
from __future__ import annotations

import json

from dotenv import load_dotenv

load_dotenv()

from services.security import security_preflight


def main() -> int:
    report = security_preflight()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
