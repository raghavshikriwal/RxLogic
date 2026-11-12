"""
Architecture-boundary tests (checklist Section 1, items 1-2).

Enforces the neuro-symbolic contract:

1. The LLM parser only *extracts* structured ``Medication`` objects. It never
   imports, calls or influences the reasoning layers, and extra "decision"
   fields a model might emit are discarded.
2. The symbolic core never depends on the LLM module (or on ``requests``) and
   produces a full plan with those modules made un-importable.

Static checks use the AST, so they hold without executing any code.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
from dataclasses import fields
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.schemas import Medication  # noqa: E402
from services.llm_parser import LLMParser  # noqa: E402

LLM_MODULE = "services.llm_parser"
NETWORK_MODULES = frozenset({"requests"})
FORBIDDEN_FOR_CORE = frozenset({LLM_MODULE, "services.drug_data_client", *NETWORK_MODULES})

CORE_MODULES = (
    "services/reasoning_service.py",
    "services/rule_engine.py",
    "services/csp_scheduler.py",
    "services/planner.py",
    "services/uncertainty.py",
    "services/food_rules.py",
    "services/name_normalizer.py",
    "models/schemas.py",
    "models/exceptions.py",
)

ALLOWED_PARSER_INTERNAL_PREFIX = "models"
SUBPROCESS_TIMEOUT_SECONDS = 60

# Fields a misbehaving model might add to try to make clinical decisions.
INJECTED_DECISION_FIELDS = {
    "severity": "severe",
    "interaction": "none",
    "safe_to_combine": True,
    "recommendation": "take both at the same time",
    "scheduled_time": "08:00",
}


def _imported_modules(relative_path: str) -> set[str]:
    """Every module name imported (absolute form) by the given source file."""
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _violations(imported: set[str], forbidden: frozenset[str]) -> set[str]:
    return {m for m in imported if m in forbidden or m.split(".")[0] in forbidden}


# -- 1. Parser extracts only; never decides ---------------------------------


def test_parser_imports_nothing_from_reasoning_layers() -> None:
    internal = {
        m for m in _imported_modules("services/llm_parser.py")
        if m.split(".")[0] in {"services", "models", "routes"}
    }
    offenders = {m for m in internal if m.split(".")[0] != ALLOWED_PARSER_INTERNAL_PREFIX}
    assert not offenders, f"LLM parser must only depend on models.*, found: {sorted(offenders)}"


@patch("services.llm_parser.requests.post")
def test_parser_returns_only_medication_objects_and_drops_decision_fields(mock_post: Mock) -> None:
    entry = {
        "name": "warfarin",
        "dosage_mg": 5,
        "frequency_per_day": 1,
        "timing_preference": "evening",
        "with_food": None,
        **INJECTED_DECISION_FIELDS,
    }
    mock_post.return_value.raise_for_status = Mock()
    mock_post.return_value.json.return_value = {"message": {"content": json.dumps([entry])}}

    result = LLMParser().parse("warfarin 5mg in the evening")

    assert len(result) == 1 and all(isinstance(m, Medication) for m in result)
    medication_fields = {f.name for f in fields(Medication)}
    assert medication_fields.isdisjoint(INJECTED_DECISION_FIELDS)
    for injected in INJECTED_DECISION_FIELDS:
        assert not hasattr(result[0], injected)


# -- 2. Symbolic core is LLM-independent -------------------------------------


@pytest.mark.parametrize("module_path", CORE_MODULES)
def test_core_module_has_no_llm_or_network_dependency(module_path: str) -> None:
    offenders = _violations(_imported_modules(module_path), FORBIDDEN_FOR_CORE)
    assert not offenders, f"{module_path} must not import {sorted(offenders)}"


def test_reasoning_pipeline_runs_with_llm_and_network_modules_blocked() -> None:
    """Runs in a clean interpreter where importing the LLM module or
    ``requests`` raises ImportError, then generates a real plan."""
    script = textwrap.dedent(
        f"""
        import sys
        for blocked in {sorted(FORBIDDEN_FOR_CORE)!r}:
            sys.modules[blocked] = None  # any import of these now raises ImportError

        from models.schemas import Medication
        from services.reasoning_service import generate_daily_plan

        plan = generate_daily_plan([
            Medication(name="warfarin", frequency_per_day=1),
            Medication(name="aspirin", frequency_per_day=1),
        ])
        assert plan.entries, "expected scheduled doses"
        assert plan.goal_trace, "expected a goal trace"
        assert plan.coverage is not None and plan.coverage.is_complete
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
