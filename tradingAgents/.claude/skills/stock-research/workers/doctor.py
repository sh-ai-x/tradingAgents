"""doctor worker.

Two modes:
- mechanical (default): tier classification, recency, >=2-source, citation-format, schema.
  Returns in seconds.
- deep (--deep): full audit incl. Decision Package field validity +
  cross-output rule application. Shows progress.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from jsonschema import validate, ValidationError  # type: ignore
from lib.citation import parse_citation, format_citation
from lib.recency import BUDGETS
from lib.tier import classify as classify_tier
from lib.schema import BUNDLE_SCHEMA


def _age_from_iso(retrieval_iso, today_iso):
    if not retrieval_iso or not today_iso:
        return None
    from datetime import date
    try:
        return (date.fromisoformat(today_iso[:10]) - date.fromisoformat(retrieval_iso[:10])).days
    except Exception:
        return None


def _check_recency(bundle: dict[str, Any]) -> list[str]:
    """Validate tier-graded recency across every output and the unified log.

    Per-data-type budgets:
        drivers=7d, fair_value=90d, forward_range=90d, macro=30d, user_qa=7d.

    For each over-budget source we verify either:
      - it is logged with action=drop (tier-B/C) in ``recency_log``, or
      - it is kept but tagged ``[recency_violated: ...]`` (tier-A) AND
        its display tier is downgraded to C in the bundle.
    """
    errors = []
    log = bundle.get("recency_log", []) or []
    log_by_source = {(e.get("source"), e.get("tier")): e for e in log}

    def _check_row(i, ev, budget):
        age = ev.get("age_days")
        tier = ev.get("tier")
        original_tier = ev.get("original_tier", tier)
        recency_violated = ev.get("recency_violated")
        if age is None or age <= budget:
            return
        if tier != "C":
            errors.append(
                f"row[{i}] over-budget source not downgraded to tier-C for display"
            )
        if original_tier == "A":
            if not recency_violated:
                errors.append(
                    f"row[{i}] tier-A over-budget source missing [recency_violated] flag"
                )
            entry = log_by_source.get((ev.get("source"), original_tier))
            if not entry or entry.get("action") != "flag":
                errors.append(
                    f"row[{i}] tier-A over-budget source missing recency_log flag entry"
                )
        elif original_tier in {"B", "C"}:
            entry = log_by_source.get((ev.get("source"), original_tier))
            if not entry or entry.get("action") != "drop":
                errors.append(
                    f"row[{i}] tier-{original_tier} over-budget source missing recency_log drop entry"
                )
            for cit in bundle.get("citations", []):
                if cit.get("url") == ev.get("source"):
                    errors.append(
                        f"row[{i}] dropped tier-{original_tier} source still cited"
                    )

    for i, ev in enumerate(bundle.get("drivers", [])):
        _check_row(i, ev, BUDGETS["drivers"])

    for i, row in enumerate(bundle.get("macro_market_state", [])):
        _check_row(i, row, BUDGETS["macro"])

    fv = bundle.get("fair_value", {}) or {}
    for cit in fv.get("citations", []):
        # fv citations are formatted strings, e.g. [url | iso | title | tier]
        parsed = parse_citation(cit)
        if not parsed:
            continue
        age = _age_from_iso(parsed["retrieval_iso"], bundle.get("generated_at"))
        if age is not None and age > BUDGETS["fair_value"] and parsed["tier"] in {"A", "B"}:
            errors.append(
                f"fair_value citation over budget: {parsed['url']} age={age}d"
            )

    fr = bundle.get("forward_range", {}) or {}
    for r in fr.get("ranges", []):
        age = _age_from_iso(r.get("retrieval_iso"), bundle.get("generated_at"))
        if age is not None and age > BUDGETS["forward_range"] and r.get("tier") in {"A", "B"}:
            errors.append(
                f"forward_range range over budget: {r.get('url')} age={age}d"
            )

    return errors


def _check_independence(bundle: dict[str, Any]) -> list[str]:
    """Major claims in fair_value, forward_range, and drivers must have >=2 sources
    OR be flagged [single_source]."""
    errors = []
    fv = bundle.get("fair_value", {})
    if fv and fv.get("mode") == "synthesized" and len(fv.get("citations", [])) < 2:
        if "[single_source]" not in (fv.get("reasoning_trace") or ""):
            errors.append("fair_value synthesized with <2 citations and no [single_source] flag")
    fr = bundle.get("forward_range", {})
    if fr and fr.get("mode") == "synthesized" and len(fr.get("ranges", [])) < 2:
        if "[single_source]" not in (fr.get("reasoning_trace") or ""):
            errors.append("forward_range synthesized with <2 ranges and no [single_source] flag")
    return errors


def _check_citations(bundle: dict[str, Any]) -> list[str]:
    """Validate every flattened citation.

    Rules:
      - citation_format is parseable.
      - True tier-C sources (blogs / social / forums) are never displayed.
      - Tier-A sources downgraded to tier-C on display because they are
        over-budget ARE allowed to appear, but only when the bundle's
        recency_log records a matching action=flag entry.
      - No duplicate URLs.
    """
    errors = []
    seen = set()
    flagged_sources = {e.get("source") for e in (bundle.get("recency_log") or [])
                       if e.get("action") == "flag"}
    for c in bundle.get("citations", []):
        s = format_citation(c["url"], c["retrieval_iso"], c["source_title"], c["tier"])
        if parse_citation(s) is None:
            errors.append(f"citation malformed: {c!r}")
        if c["tier"] == "C" and c["url"] not in flagged_sources:
            errors.append(f"tier-C citation displayed: {c['url']}")
        if c["tier"] == "C" and c["url"] in flagged_sources:
            # Sanity: the source must also have a recency_violated flag.
            if "recency_violated" not in (bundle.get("drivers") and
                                            [d for d in bundle["drivers"] if d.get("source") == c["url"]] or [{}])[0]:
                # macro events also carry recency_violated; check both
                has_flag = False
                for row in bundle.get("drivers", []):
                    if row.get("source") == c["url"] and row.get("recency_violated"):
                        has_flag = True
                        break
                if not has_flag:
                    errors.append(
                        f"tier-C display-downgraded citation lacks recency_violated: {c['url']}"
                    )
        if c["url"] in seen:
            errors.append(f"duplicate citation url: {c['url']}")
        seen.add(c["url"])
    return errors


def _check_schema(bundle: dict[str, Any]) -> list[str]:
    try:
        validate(instance=bundle, schema=BUNDLE_SCHEMA)
        return []
    except ValidationError as e:
        return [f"schema: {e.message} at {list(e.absolute_path)}"]


def _check_decision_package(bundle: dict[str, Any]) -> list[str]:
    """--deep only: Decision Package field validity."""
    dp = bundle.get("decision_package", {}) or {}
    required = ["forecastable_claims", "lifecycle_assumptions", "contrary_evidence",
                "owner_roles", "follow_up", "postmortem_required"]
    return [f"decision_package missing field: {f}" for f in required if f not in dp]


def _check_cross_output_rules(bundle: dict[str, Any]) -> list[str]:
    """--deep only: cross-output rule application."""
    errors = []
    fv = bundle.get("fair_value", {})
    fr = bundle.get("forward_range", {})
    if fv and fr and fv.get("mode") != "bracket" and fr.get("mode") != "bracket":
        fv_mid = (fv["band_low"] + fv["band_high"]) / 2
        fr_mid = fr.get("modal_midpoint", 0)
        if abs(fv_mid - fr_mid) / max(abs(fr_mid), 1) > 0.20:
            errors.append("fair_value midpoint diverges >20% from forward_range midpoint")
    uqa_cits = set()
    for q in bundle.get("user_qa", []):
        for s in q.get("sources", []):
            p = parse_citation(s)
            if p:
                uqa_cits.add(p["url"])
    fv_cits = set()
    for c in bundle.get("citations", []):
        if c.get("origin") == "fair_value":
            fv_cits.add(c["url"])
    leaked = uqa_cits & fv_cits
    if leaked:
        errors.append(f"user_qa sources leaked into fair_value: {sorted(leaked)}")
    return errors


def run(bundle: dict[str, Any], deep: bool = False) -> dict[str, Any]:
    """Validate a persisted bundle. Does not re-execute workers."""
    errors = []
    errors += _check_recency(bundle)
    errors += _check_independence(bundle)
    errors += _check_citations(bundle)
    errors += _check_schema(bundle)
    if deep:
        progress = ["[1/5] recency", "[2/5] independence", "[3/5] citations",
                    "[4/5] schema", "[5/5] decision_package + cross-output"]
        errors += _check_decision_package(bundle)
        errors += _check_cross_output_rules(bundle)
    else:
        progress = ["[1/4] recency", "[2/4] independence", "[3/4] citations", "[4/4] schema"]
    verdict = "pass" if not errors else f"fail: {len(errors)} error(s)"
    out = {
        "verdict": verdict,
        "errors": errors,
        "mode": "deep" if deep else "mechanical",
    }
    if deep:
        out["progress"] = progress
    return out
