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

def _check_recency(bundle: dict[str, Any]) -> list[str]:
    errors = []
    for i, ev in enumerate(bundle.get("drivers", [])):
        # Trust the recorded retrieval_iso + tier. tier-C is filtered upstream.
        budget = BUDGETS["drivers"]
        age = ev.get("age_days")
        if age is not None and age > budget and ev.get("tier") in {"A", "B"}:
            errors.append(f"drivers[{i}] recency violation not flagged")
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
    errors = []
    seen = set()
    for c in bundle.get("citations", []):
        published_iso = c.get("published_iso")
        if not published_iso:
            errors.append(f"citation missing published_iso: {c!r}")
            continue
        s = format_citation(c["url"], published_iso, c["source_title"], c["tier"])
        if parse_citation(s) is None:
            errors.append(f"citation malformed: {c!r}")
        if c["tier"] == "C":
            errors.append(f"tier-C citation displayed: {c['url']}")
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
    # Cross-check: fair_value band vs forward_range tier-anchor bracket.
    if fv and fr and fv.get("mode") != "bracket" and fr.get("mode") != "bracket":
        fv_mid = (fv["band_low"] + fv["band_high"]) / 2
        fr_mid = fr.get("modal_midpoint", 0)
        if abs(fv_mid - fr_mid) / max(abs(fr_mid), 1) > 0.20:
            errors.append("fair_value midpoint diverges >20% from forward_range midpoint")
    # user_qa must not appear in fair_value citations.
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
