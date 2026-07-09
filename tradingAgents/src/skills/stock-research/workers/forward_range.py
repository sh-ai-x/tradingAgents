"""forward_range worker.

6-month forward ranges whose probabilities sum to 1.0, evidence-backed.
Tier-A disagreement > +/-10% -> bracket mode, conflict: true, probabilities
suppressed, outliers annotated [outlier: ...].
"""
from __future__ import annotations
import math
from typing import Any
from lib.recency import check as recency_check
from lib.conflict import is_in_conflict
from lib.citation import MissingPublicationDate, source_date_iso


def _tier_a_anchor(kept: list[dict[str, Any]]) -> tuple[float, float]:
    """Return [min(tier-A low), max(tier-A high)] across all tier-A ranges."""
    lows = [r["low"] for r in kept if r["tier"] == "A"]
    highs = [r["high"] for r in kept if r["tier"] == "A"]
    return (min(lows) if lows else 0.0, max(highs) if highs else 0.0)


def _outliers(kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate tier-A ranges whose midpoints are more than 1 std-dev away from
    the tier-A midpoint mean -- i.e. ranges driving the spread that produced
    the conflict. Outliers are emitted as evidence -- never collapsed."""
    tier_a = [r for r in kept if r["tier"] == "A"]
    if len(tier_a) < 2:
        return []
    mids = [(r["low"] + r["high"]) / 2 for r in tier_a]
    mean = sum(mids) / len(mids)
    var = sum((m - mean) ** 2 for m in mids) / len(mids)
    std = math.sqrt(var)
    if std == 0:
        return []
    out = []
    for r, m in zip(tier_a, mids):
        if abs(m - mean) > std:
            out.append({
                "label": r["label"],
                "midpoint": m,
                "deviation_std": abs(m - mean) / std,
                "annotation": f"[outlier: {r['label']} mid={m:.2f} >{abs(m-mean)/std:.2f} std from mean]",
                "source": r["url"],
                "tier": r["tier"],
            })
    return out


def run(ranges: list[dict[str, Any]], today_iso: str) -> dict[str, Any]:
    """ranges = [{"label": str, "low": float, "high": float, "probability": float,
                   "evidence_count": int, "url": str, "published_iso": str,
                   "retrieval_iso": str,
                   "source_title": str, "tier": "A"|"B"|"C"}]"""
    # Recency filter (forward_range budget = 90 days).
    kept: list[dict[str, Any]] = []
    recency_log: list[dict[str, Any]] = []
    for r in ranges:
        try:
            date_iso = source_date_iso(r)
        except MissingPublicationDate:
            recency_log.append({"source": r.get("url", ""),
                                "tier": r.get("tier", ""),
                                "action": "missing_published_iso",
                                "reason": "source lacks publication/release date"})
            continue
        rr = recency_check("forward_range", r["tier"], date_iso, today_iso)
        if rr.action == "drop":
            recency_log.append({"source": r.get("url", ""),
                                "age_days": rr.age_days,
                                "budget_days": rr.budget_days,
                                "tier": r["tier"],
                                "action": "drop"})
            continue
        kept.append(r)

    # Drop ranges with zero evidence (per spec: each range evidence-backed).
    kept = [r for r in kept if r.get("evidence_count", 0) > 0]

    tier_a_midpoints = [(r["low"] + r["high"]) / 2 for r in kept if r["tier"] == "A"]

    if tier_a_midpoints and is_in_conflict(tier_a_midpoints):
        anchor_low, anchor_high = _tier_a_anchor(kept)
        mid_lo, mid_hi = min(tier_a_midpoints), max(tier_a_midpoints)
        outliers = _outliers(kept)
        return {
            "ranges": [], "mode": "bracket",
            "modal_midpoint": (mid_lo + mid_hi) / 2,
            "tier_anchor_low": anchor_low, "tier_anchor_high": anchor_high,
            "conflict": True, "low_confidence": False,
            "outliers": outliers,
            "reasoning_trace": (
                f"tier-A disagreement > +/-10% -- bracket "
                f"[{anchor_low},{anchor_high}] from tier-A ranges; "
                f"{len(outliers)} outlier(s) annotated"
            ),
            "recency_log": recency_log,
        }

    # Normalize probabilities to sum to 1.0.
    total_p = sum(r["probability"] for r in kept) or 1.0
    for r in kept:
        r["probability"] = r["probability"] / total_p
    midpoints = [(r["low"] + r["high"]) / 2 for r in kept]
    modal_midpoint = sum(
        p * m for p, m in zip([r["probability"] for r in kept], midpoints)
    ) / max(sum(r["probability"] for r in kept), 1)
    tier_a = [r for r in kept if r["tier"] == "A"]
    return {
        "ranges": kept, "mode": "synthesized",
        "modal_midpoint": modal_midpoint,
        "tier_anchor_low": min((r["low"] for r in tier_a), default=0.0),
        "tier_anchor_high": max((r["high"] for r in tier_a), default=0.0),
        "conflict": False, "low_confidence": len(tier_a) == 0,
        "outliers": [], "reasoning_trace": "tier-A within +/-10%",
        "recency_log": recency_log,
    }
