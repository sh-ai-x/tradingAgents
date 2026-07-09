"""macro worker.

Returns flat snapshot table rows. NO prose synthesis.
Each row: indicator, value, source, published_iso, retrieval_iso, tier.
Per-indicator single-source is allowed (BEA releases etc.).
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check
from lib.citation import MissingPublicationDate, source_date_iso

def run(rows: list[dict[str, Any]], today_iso: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    recency_log: list[dict[str, Any]] = []
    for r in rows:
        try:
            date_iso = source_date_iso(r)
        except MissingPublicationDate:
            recency_log.append({"source": r.get("source", ""),
                                "tier": r.get("tier", ""),
                                "action": "missing_published_iso",
                                "reason": "source lacks publication/release date"})
            continue
        rr = recency_check("macro", r["tier"], date_iso, today_iso)
        if rr.action == "drop":
            recency_log.append({"source": r["source"], "age_days": rr.age_days,
                                "budget_days": rr.budget_days, "tier": r["tier"],
                                "action": "drop"})
            continue
        display_tier = "C" if rr.action == "flag" else r["tier"]
        out.append({
            "indicator": r["indicator"],
            "value": r["value"],
            "source": r["source"],
            "published_iso": date_iso,
            "retrieval_iso": r["retrieval_iso"],
            "tier": display_tier,
        })
    return out
