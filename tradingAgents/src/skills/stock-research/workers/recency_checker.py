"""recency_checker — tier-graded recency budget enforcement.

Single-entry orchestrator used by head_manager to drive per-data-type
recency checks across every input set. Also re-exports
``lib.recency.check`` for direct use.

Recency budgets (per ``lib/recency.BUDGETS``):
    price         <= 7d
    drivers       <= 7d
    fundamentals  <= 90d
    fair_value    <= 90d
    forward_range <= 90d
    macro         <= 30d

Tier-graded response:
    tier-A over budget -> keep, flag [recency_violated: Nd over budget],
                          tier is downgraded to C for display.
    tier-B / tier-C over budget -> drop, log.

Un-verifiable claims (no in-budget sources) surface as
``not_found_in_budget`` with the search terms attempted.
"""
from __future__ import annotations
from typing import Any
from lib.recency import check, age_days, BUDGETS
from lib.citation import MissingPublicationDate, source_date_iso

__all__ = ["check", "age_days", "BUDGETS", "run", "scan"]


def _emit(recency_log, source, tier, rr):
    recency_log.append({
        "source": source,
        "age_days": rr.age_days,
        "budget_days": rr.budget_days,
        "tier": tier,
        "action": rr.action,
    })


def _source_date(obj, recency_log, source, tier):
    try:
        return source_date_iso(obj)
    except MissingPublicationDate as exc:
        recency_log.append({
            "source": source,
            "tier": tier,
            "action": "missing_published_iso",
            "reason": str(exc),
        })
        return None


def _scan_fair_value(inputs, today_iso, recency_log):
    for est in inputs or []:
        date_iso = _source_date(est, recency_log, est.get("url", ""), est["tier"])
        if not date_iso:
            continue
        rr = check("fair_value", est["tier"], date_iso, today_iso)
        _emit(recency_log, est.get("url", ""), est["tier"], rr)


def _scan_drivers(inputs, today_iso, recency_log):
    for ev in inputs or []:
        date_iso = _source_date(ev, recency_log, ev.get("url", ""), ev["tier"])
        if not date_iso:
            continue
        rr = check("drivers", ev["tier"], date_iso, today_iso)
        _emit(recency_log, ev.get("url", ""), ev["tier"], rr)


def _scan_fundamentals(inputs, today_iso, recency_log):
    for row in inputs or []:
        date_iso = _source_date(row, recency_log, row.get("source", ""), row["tier"])
        if not date_iso:
            continue
        rr = check("fundamentals", row["tier"], date_iso, today_iso)
        _emit(recency_log, row.get("source", ""), row["tier"], rr)


def _scan_macro(inputs, today_iso, recency_log):
    for r in inputs or []:
        date_iso = _source_date(r, recency_log, r.get("source", ""), r["tier"])
        if not date_iso:
            continue
        rr = check("macro", r["tier"], date_iso, today_iso)
        _emit(recency_log, r.get("source", ""), r["tier"], rr)


def _scan_forward_range(inputs, today_iso, recency_log):
    for r in inputs or []:
        date_iso = _source_date(r, recency_log, r.get("url", ""), r["tier"])
        if not date_iso:
            continue
        rr = check("forward_range", r["tier"], date_iso, today_iso)
        _emit(recency_log, r.get("url", ""), r["tier"], rr)


def _scan_user_qa(inputs, today_iso, recency_log):
    for q in inputs or []:
        budget = q.get("budget_type", "drivers")
        for s in q.get("sources", []) or []:
            date_iso = _source_date(s, recency_log, s.get("url", ""), s["tier"])
            if not date_iso:
                continue
            rr = check(budget, s["tier"], date_iso, today_iso)
            _emit(recency_log, s.get("url", ""), s["tier"], rr)


def scan(grouped: dict[str, list[dict[str, Any]]], today_iso: str) -> list[dict[str, Any]]:
    """Return the cross-cutting recency log for every input set.

    grouped = {"fair_value": [...], "drivers": [...], "fundamentals": [...], "macro": [...],
                "forward_range": [...], "user_qa": [...]}"""
    recency_log: list[dict[str, Any]] = []
    _scan_fair_value(grouped.get("fair_value"), today_iso, recency_log)
    _scan_drivers(grouped.get("drivers"), today_iso, recency_log)
    _scan_fundamentals(grouped.get("fundamentals"), today_iso, recency_log)
    _scan_macro(grouped.get("macro"), today_iso, recency_log)
    _scan_forward_range(grouped.get("forward_range"), today_iso, recency_log)
    _scan_user_qa(grouped.get("user_qa"), today_iso, recency_log)
    return recency_log


def run(grouped: dict[str, list[dict[str, Any]]], today_iso: str) -> list[dict[str, Any]]:
    """Alias for ``scan``. Kept for naming parity with other workers."""
    return scan(grouped, today_iso)
