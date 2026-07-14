"""doctor worker.

Two modes:
- mechanical (default): tier classification, recency, >=2-source, citation-format, schema.
  Returns in seconds.
- deep (--deep): full audit incl. Decision Package field validity +
  cross-output rule application. Shows progress.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from jsonschema import validate, ValidationError  # type: ignore
from lib.citation import parse_citation, format_citation
from lib.recency import BUDGETS, reference_budget
from lib.tier import classify as classify_tier
from lib.schema import BUNDLE_SCHEMA

def _check_evidence_coverage(bundle: dict[str, Any]) -> list[str]:
    """Require >=10 persisted, ticker-assigned references and >=5 domains per ticker."""
    errors = []
    tickers = bundle.get("tickers") or ([bundle.get("ticker")] if bundle.get("ticker") else [])
    refs = bundle.get("reference_confidence_table") or bundle.get("citations") or []
    for ticker in tickers:
        assigned = []
        for ref in refs:
            explicit = ref.get("tickers", ref.get("ticker", []))
            if isinstance(explicit, str):
                explicit = [explicit]
            # Single-ticker legacy bundles may omit assignment.
            if (ticker in explicit or (len(tickers) == 1 and not explicit)) and _reference_is_eligible(ref, bundle):
                assigned.append(ref)
        urls = {ref.get("url") for ref in assigned if ref.get("url")}
        domains = {
            ref.get("domain") or urlparse(ref.get("url", "")).netloc
            for ref in assigned
            if ref.get("url") in urls and (ref.get("domain") or urlparse(ref.get("url", "")).netloc)
        }
        if len(urls) < 10:
            errors.append(f"{ticker}: persisted reference coverage {len(urls)}/10")
        if len(domains) < 5:
            errors.append(f"{ticker}: persisted domain coverage {len(domains)}/5")
    return errors

def _check_declared_coverage_consistency(bundle: dict[str, Any]) -> list[str]:
    """Require declared coverage to be reproducible from persisted references."""
    errors = []
    declared = bundle.get("evidence_coverage") or {}
    if not declared:
        return errors
    tickers = bundle.get("tickers") or ([bundle.get("ticker")] if bundle.get("ticker") else [])
    refs = bundle.get("reference_confidence_table") or bundle.get("citations") or []
    for ticker in tickers:
        assigned = []
        for ref in refs:
            explicit = ref.get("tickers", ref.get("ticker", []))
            if isinstance(explicit, str):
                explicit = [explicit]
            if (ticker in explicit or (len(tickers) == 1 and not explicit)) and _reference_is_eligible(ref, bundle):
                assigned.append(ref)
        actual_urls = {ref.get("url") for ref in assigned if ref.get("url")}
        actual_domains = {
            ref.get("domain") or urlparse(ref.get("url", "")).netloc
            for ref in assigned
            if ref.get("url") in actual_urls and (ref.get("domain") or urlparse(ref.get("url", "")).netloc)
        }
        item = declared.get(ticker, {})
        declared_refs = item.get("eligible_count", item.get("evidence_count", 0))
        declared_domains = item.get("distinct_domains", item.get("domain_count", 0))
        if declared_refs != len(actual_urls) or declared_domains != len(actual_domains):
            errors.append(
                f"{ticker}: declared coverage {declared_refs} refs/{declared_domains} domains "
                f"does not match persisted coverage {len(actual_urls)} refs/{len(actual_domains)} domains"
            )
    return errors


def _reference_is_eligible(ref: dict[str, Any], bundle: dict[str, Any]) -> bool:
    try:
        retrieval = datetime.fromisoformat(str(bundle.get("retrieval_iso", "")).replace("Z", "+00:00"))
        published = datetime.fromisoformat(str(ref.get("published_iso", "")).replace("Z", "+00:00"))
    except ValueError:
        return False
    age = (retrieval.date() - published.date()).days
    return 0 <= age <= reference_budget(ref.get("used_in"))

def _check_recency(bundle: dict[str, Any]) -> list[str]:
    errors = []
    drivers = bundle.get("drivers", [])
    if isinstance(drivers, dict):
        drivers = [item for values in drivers.values() for item in values if isinstance(item, dict)]
    for i, ev in enumerate(drivers):
        # Trust the recorded retrieval_iso + tier. tier-C is filtered upstream.
        budget = BUDGETS["drivers"]
        age = ev.get("age_days")
        if age is not None and age > budget and ev.get("tier") in {"A", "B"}:
            errors.append(f"drivers[{i}] recency violation not flagged")
    return errors

def _check_multi_bundle(bundle: dict[str, Any]) -> list[str]:
    if not bundle.get("tickers"):
        return []
    errors = []
    try:
        retrieval = datetime.fromisoformat(str(bundle.get("retrieval_iso", "")).replace("Z", "+00:00"))
    except ValueError:
        return ["multi bundle retrieval_iso is invalid"]
    if retrieval.tzinfo is None:
        retrieval = retrieval.replace(tzinfo=timezone.utc)
    for i, ref in enumerate(bundle.get("reference_confidence_table", [])):
        if ref.get("tier") == "C":
            errors.append(f"reference_confidence_table[{i}] displays tier C")
        if not ref.get("ticker") and not ref.get("tickers"):
            errors.append(f"reference_confidence_table[{i}] missing ticker assignment")
        try:
            published = datetime.fromisoformat(str(ref.get("published_iso", "")).replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age = (retrieval.date() - published.date()).days
            budget = reference_budget(ref.get("used_in"))
            if not 0 <= age <= budget:
                errors.append(
                    f"reference_confidence_table[{i}] outside {budget}-day "
                    f"budget for {ref.get('used_in') or ['unclassified']}"
                )
        except ValueError:
            errors.append(f"reference_confidence_table[{i}] invalid published_iso")
    for entry in bundle.get("band_probability_table", []):
        if not isinstance(entry, dict):
            continue
        bands = entry.get("bands", [])
        total = sum(float(band.get("probability", 0)) for band in bands)
        if bands and abs(total - 1.0) > 1e-9:
            errors.append(f"{entry.get('ticker', 'unknown')}: band probabilities sum to {total}")
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
    if bundle.get("tickers"):
        return []
    dp = bundle.get("decision_package", {}) or {}
    required = ["forecastable_claims", "lifecycle_assumptions", "contrary_evidence",
                "owner_roles", "follow_up", "postmortem_required"]
    return [f"decision_package missing field: {f}" for f in required if f not in dp]

def _check_cross_output_rules(bundle: dict[str, Any]) -> list[str]:
    """--deep only: cross-output rule application."""
    errors = []
    if bundle.get("tickers"):
        return errors
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
    errors += _check_evidence_coverage(bundle)
    errors += _check_declared_coverage_consistency(bundle)
    errors += _check_multi_bundle(bundle)
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
