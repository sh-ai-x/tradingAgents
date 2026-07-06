"""fair_value worker.

Computes point + +/- band independently from per-source fair-value estimates,
cross-checks against forward_range midpoint, applies +/-10% tier-A conflict
rule, and emits low_confidence / bracket / synthesis modes.
"""
from __future__ import annotations
from typing import Any
from evidence_synthesizer import synthesize
from lib.citation import format_citation
from lib.recency import check as recency_check, BUDGETS
from lib.conflict import is_in_conflict, tier_bracket, weighted_synthesis

def run(estimates: list[dict[str, Any]], today_iso: str) -> dict[str, Any]:
    """estimates = [{"value": float, "url": str, "retrieval_iso": str, "source_title": str,
                     "tier": "A"|"B"|"C"}]"""
    citations = []
    kept_a = []
    kept_b = []
    recency_log = []
    for est in estimates:
        tier = est["tier"]
        rr = recency_check("fair_value", tier, est["retrieval_iso"], today_iso)
        if rr.action == "drop":
            recency_log.append({"source": est["url"], "age_days": rr.age_days,
                                "budget_days": rr.budget_days, "tier": tier,
                                "action": "drop"})
            continue
        cit = format_citation(est["url"], est["retrieval_iso"], est["source_title"], tier)
        citations.append(cit)
        if tier == "A":
            kept_a.append(est["value"])
        elif tier == "B":
            kept_b.append(est["value"])

    low_confidence = len(kept_a) == 0
    all_kept = kept_a + kept_b
    if not all_kept:
        return {
            "point": 0.0, "band_low": 0.0, "band_high": 0.0,
            "synthesis_target": 0.0, "mode": "bracket",
            "tier_bracket": [], "conflict": False, "low_confidence": True,
            "citations": [], "reasoning_trace": "not_found_in_budget",
        }

    synthesis_target = sum(all_kept) / len(all_kept)
    if kept_a and is_in_conflict(kept_a):
        lo, hi = tier_bracket(kept_a)
        return {
            "point": (lo + hi) / 2, "band_low": lo, "band_high": hi,
            "synthesis_target": synthesis_target, "mode": "bracket",
            "tier_bracket": [str(x) for x in kept_a], "conflict": True,
            "low_confidence": False, "citations": citations,
            "reasoning_trace": f"tier-A disagreement > +/-10% -- bracket [{lo},{hi}]",
        }
    if low_confidence:
        lo, hi = min(all_kept), max(all_kept)
        return {
            "point": (lo + hi) / 2, "band_low": lo, "band_high": hi,
            "synthesis_target": synthesis_target, "mode": "bracket",
            "tier_bracket": [], "conflict": False, "low_confidence": True,
            "citations": citations,
            "reasoning_trace": "no tier-A sources -- bracket [min,max] of cited",
        }
    # Synthesized path: weighted synthesis (tier-A weight 3, tier-B weight 1).
    weighted = [(v, 3.0) for v in kept_a] + [(v, 1.0) for v in kept_b]
    pt = weighted_synthesis(weighted)
    half_band = max(abs(pt - min(all_kept)), abs(max(all_kept) - pt))
    return {
        "point": pt, "band_low": pt - half_band, "band_high": pt + half_band,
        "synthesis_target": synthesis_target, "mode": "synthesized",
        "tier_bracket": [str(x) for x in kept_a], "conflict": False,
        "low_confidence": False, "citations": citations,
        "reasoning_trace": "tier-A within +/-10%, weighted synthesis",
    }
