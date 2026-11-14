"""Verify every RxCUI in knowledge/medication_catalog.json against NLM RxNav.

Requires network access. Exit code 0 only when every entry matches.

Example:
  python -m scripts.verify_rxcuis
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from services.medication_catalog import DEFAULT_CATALOG_PATH, catalog_maps, load_medication_catalog
from services.rxcui_verification import verify_rxcuis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    args = parser.parse_args(argv)

    rxcuis, _ = catalog_maps(load_medication_catalog(args.catalog))
    results = verify_rxcuis(rxcuis)
    for check in results:
        marker = "OK  " if check.passed else "FAIL"
        extra = f" ({check.rxnav_name or '-'}; {check.detail})" if not check.passed else ""
        print(f"{marker} {check.canonical_name:<20} {check.rxcui:>8} {check.status}{extra}")

    failed = [check for check in results if not check.passed]
    print(f"\n{len(results) - len(failed)}/{len(results)} RxCUIs verified against RxNav.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
