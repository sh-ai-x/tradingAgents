"""head_manager — elicitation interview, halt checks, bundle composition.

The head_manager is the orchestrator. It:

1. Runs the elicitation interview (or accepts prior elicitation results).
2. Spawns per-output workers (fair_value, drivers, macro, forward_range, user_qa).
3. Composes the bundle, applying halt conditions and accumulating
   follow_up + postmortem_required from prior runs.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import fair_value as WFV
import drivers as WD
import macro as WM
import forward_range as WFR
import user_qa as WUQ
import recency_checker as WRC
import json
from lib.persist import (
    write_bundle, accumulate, iso_filename_stem, list_runs
)
from lib.citation import format_citation

REQUIRED_OUTPUTS = ["fair_value", "drivers", "macro_market_state", "forward_range", "user_qa"]

def elicit(ticker: str, questions: list[str], date_of_record: str) -> dict[str, Any]:
    """Ouroboros-style elicitation. In this deterministic implementation, we
    formalize the questions as the research scope. Returns a profile."""
    return {
        "ticker": ticker.upper(),
        "questions": questions,
        "date_of_record": date_of_record,
        "depth": "standard",
        "interview_complete": True,
    }

def compose(
    ticker: str,
    today_iso: str,
    fair_value_inputs: list[dict[str, Any]],
    drivers_inputs: list[dict[str, Any]],
    macro_inputs: list[dict[str, Any]],
    forward_range_inputs: list[dict[str, Any]],
    user_qas_inputs: list[dict[str, Any]],
    questions: list[str],
    decision_package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a full bundle from worker inputs."""
    root_path = None  # resolved by caller via write_bundle

    fv = WFV.run(fair_value_inputs, today_iso)
    drivers_out = WD.run(drivers_inputs, today_iso)
    macro_out = WM.run(macro_inputs, today_iso)
    fr = WFR.run(forward_range_inputs, today_iso)
    uqa, uqa_recency_log = WUQ.run(user_qas_inputs, today_iso)

    halt_flags = []
    omitted = []
    if not macro_out:
        halt_flags.append({"output": "macro_market_state", "flag": "[macro_stale]",
                           "reason": "all macro sources dropped on recency"})
        omitted.append("macro_market_state")

    status = "ok" if not omitted else "partial"

    # Decision package defaults.
    dp = decision_package or {}
    dp.setdefault("forecastable_claims", [])
    dp.setdefault("lifecycle_assumptions", [])
    dp.setdefault("contrary_evidence", [])
    dp.setdefault("owner_roles", [])
    dp.setdefault("follow_up", [])
    dp.setdefault("postmortem_required", [])

    # Flatten citations from fair_value + drivers + macro + forward_range.
    citations = _flatten_citations(fv, drivers_out, macro_out, fr)

    # Aggregate recency logs from every per-output worker. Cross-cutting
    # recency_checker also emits a unified log over the same inputs so the
    # bundle carries both per-output events and a cross-cutting trace.
    recency_log = (
        fv.get("recency_log", [])
        + _recency_log_for_drivers(drivers_inputs, today_iso)
        + _recency_log_for_macro(macro_inputs, today_iso)
        + _recency_log_for_forward_range(forward_range_inputs, today_iso)
        + _recency_log_for_user_qa(user_qas_inputs, today_iso)
        + uqa_recency_log
    )
    cross_log = WRC.run({
        "fair_value": fair_value_inputs,
        "drivers": drivers_inputs,
        "macro": macro_inputs,
        "forward_range": forward_range_inputs,
        "user_qa": user_qas_inputs,
    }, today_iso)
    recency_log = _dedup(recency_log + cross_log)

    bundle = {
        "run_id": iso_filename_stem() + "_" + ticker.upper(),
        "ticker": ticker.upper(),
        "generated_at": today_iso,
        "status": status,
        "fair_value": fv,
        "drivers": drivers_out,
        "macro_market_state": macro_out,
        "forward_range": fr,
        "user_qa": uqa,
        "decision_package": dp,
        "citations": citations,
        "recency_log": recency_log,
        "halt_flags": halt_flags,
        "omitted_outputs": omitted,
    }
    return bundle

def _dedup(events):
    seen = set()
    out = []
    for e in events:
        key = (e.get("source"), e.get("age_days"), e.get("tier"), e.get("action"))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out

def _recency_log_for_drivers(events, today_iso):
    return _recency_log_for(events, today_iso, "drivers", "url")

def _recency_log_for_macro(rows, today_iso):
    return _recency_log_for(rows, today_iso, "macro", "source")

def _recency_log_for_forward_range(ranges, today_iso):
    return _recency_log_for(ranges, today_iso, "forward_range", "url")

def _recency_log_for_user_qa(qas, today_iso):
    out = []
    for q in qas:
        for s in q.get("sources", []):
            budget = q.get("budget_type", "drivers")
            rr = WRC.check(budget, s["tier"], s["retrieval_iso"], today_iso)
            if rr.action == "drop":
                out.append({"source": s["url"], "age_days": rr.age_days,
                            "budget_days": rr.budget_days, "tier": s["tier"],
                            "action": "drop",
                            "context": q.get("question", "")})
    return out

def _recency_log_for(items, today_iso, data_type, url_key):
    out = []
    for it in items or []:
        rr = WRC.check(data_type, it["tier"], it["retrieval_iso"], today_iso)
        if rr.action == "drop":
            out.append({"source": it.get(url_key, ""), "age_days": rr.age_days,
                        "budget_days": rr.budget_days, "tier": it["tier"],
                        "action": "drop"})
        elif rr.action == "flag":
            out.append({"source": it.get(url_key, ""), "age_days": rr.age_days,
                        "budget_days": rr.budget_days, "tier": it["tier"],
                        "action": "flag"})
    return out

def _flatten_citations(fv, drivers, macro, fr) -> list[dict[str, Any]]:
    """Flatten every cited source into the canonical citation list."""
    out = []
    seen = set()
    for cit in fv.get("citations", []):
        # Fair-value citation strings.
        from lib.citation import parse_citation
        p = parse_citation(cit)
        if not p:
            continue
        key = (p["url"], p["retrieval_iso"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"url": p["url"], "retrieval_iso": p["retrieval_iso"],
                    "source_title": p["source_title"], "tier": p["tier"],
                    "claim_class": "interpretive", "capability": "read",
                    "origin": "fair_value"})
    for d in drivers:
        key = (d["source"], d["retrieval_iso"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"url": d["source"], "retrieval_iso": d["retrieval_iso"],
                    "source_title": d.get("source_title", d.get("claim", "")[:60]),
                    "tier": d["tier"], "claim_class": "factual",
                    "capability": "read", "origin": "drivers"})
    return out

def write(root, ticker, bundle):
    return write_bundle(root, ticker, bundle)

def accumulate_across_runs(root, ticker, bundle):
    """Merge follow_up + postmortem_required from prior runs."""
    merged = accumulate(root, ticker, ["follow_up", "postmortem_required"])
    dp = bundle.setdefault("decision_package", {})
    dp["follow_up"] = list({json.dumps(x, sort_keys=True) if not isinstance(x, str) else x
                            for x in (dp.get("follow_up") or []) + merged["follow_up"]})
    dp["postmortem_required"] = list({json.dumps(x, sort_keys=True) if not isinstance(x, str) else x
                                      for x in (dp.get("postmortem_required") or []) + merged["postmortem_required"]})
    return bundle
