"""Runner implementation used by run_skill.py."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATE_OF_RECORD = "2026-07-07"
TODAY_ISO = "2026-07-07T10:15:00Z"
_LAST_PATH: Path | None = None

def _skill_root() -> Path:
    return Path(__file__).resolve().parent / ".claude" / "skills" / "stock-research"

def _ensure_skill_path() -> None:
    root = _skill_root()
    for sub in (root, root / "workers", root / "lib"):
        sp = str(sub)
        if sp not in sys.path:
            sys.path.insert(0, sp)

def last_path() -> Path | None:
    return _LAST_PATH

def _load_fixtures(fixtures: Path) -> dict[str, Any]:
    path = fixtures / "default.json"
    return json.loads(path.read_text())

def _user_qa_input(questions, fx, inputs):
    """Build per-question inputs. When the configured answer is the literal
    ``not_found_in_budget`` placeholder, attach no sources so the worker
    emits the proper not-found envelope with search terms attempted."""
    out = []
    uqa_sources = inputs.get("user_qa_sources", [])
    answers = fx.get("user_qa_answers", {})
    for q in questions:
        answer = answers.get(q, "not_found_in_budget")
        if answer.startswith("not_found_in_budget"):
            sources = []
        else:
            sources = uqa_sources
        out.append({"question": q, "answer": answer, "sources": sources,
                    "budget_type": "drivers"})
    return out

def run(ticker: str, questions: list[str], fixtures: Path, runtime: Path) -> dict[str, Any]:
    _ensure_skill_path()
    from workers import head_manager
    fx = _load_fixtures(fixtures)
    inputs = fx.get("inputs", {})
    bundle = head_manager.compose(
        ticker=ticker,
        today_iso=TODAY_ISO,
        fair_value_inputs=inputs.get("fair_value", []),
        drivers_inputs=inputs.get("drivers", []),
        macro_inputs=inputs.get("macro", []),
        forward_range_inputs=inputs.get("forward_range", []),
        user_qas_inputs=_user_qa_input(questions, fx, inputs),
        questions=questions,
        decision_package={
            "forecastable_claims": ["Q2 earnings beat", "Forward P/E compresses if rates hold"],
            "lifecycle_assumptions": ["Mature smartphone cycle"],
            "contrary_evidence": ["China shipments down YoY"],
            "owner_roles": [{"role": "analyst", "owner": "tier-A broker research"}],
            "follow_up": [],
            "postmortem_required": [],
        },
    )
    bundle = head_manager.accumulate_across_runs(runtime, ticker, bundle)
    path = head_manager.write(runtime, ticker, bundle)
    global _LAST_PATH
    _LAST_PATH = path
    return bundle

def show(run_id: str, runtime: Path) -> dict[str, Any]:
    for p in runtime.glob("*/*.json"):
        if p.stem == run_id:
            return json.loads(p.read_text())
    raise FileNotFoundError(f"run-id not found: {run_id}")

def doctor(run_id: str, runtime: Path, deep: bool = False) -> dict[str, Any]:
    _ensure_skill_path()
    from workers import doctor as doctor_worker
    bundle = show(run_id, runtime)
    return doctor_worker.run(bundle, deep=deep)
