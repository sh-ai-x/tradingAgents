"""drivers worker.

Returns a structured list of event objects. NO prose synthesis.
Each event: timestamp, source, claim, published_iso, retrieval_iso, tier,
recency_violated, citation_format.
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check
from lib.citation import MissingPublicationDate, source_date_iso

def run(events: list[dict[str, Any]], today_iso: str) -> list[dict[str, Any]]:
    """events = [{"timestamp": str, "url": str, "claim": str,
                  "published_iso": str, "retrieval_iso": str, "tier": "A"|"B"|"C",
                  "source_title": str}]"""
    out: list[dict[str, Any]] = []
    recency_log: list[dict[str, Any]] = []
    for ev in events:
        try:
            date_iso = source_date_iso(ev)
        except MissingPublicationDate:
            recency_log.append({"source": ev.get("url", ""),
                                "tier": ev.get("tier", ""),
                                "action": "missing_published_iso",
                                "reason": "source lacks publication/release date"})
            continue
        rr = recency_check("drivers", ev["tier"], date_iso, today_iso)
        if rr.action == "drop":
            recency_log.append({"source": ev["url"], "age_days": rr.age_days,
                                "budget_days": rr.budget_days, "tier": ev["tier"],
                                "action": "drop"})
            continue
        recency_violated = f"[recency_violated: {rr.age_days - rr.budget_days}d over budget]" if rr.action == "flag" else None
        # Display tier is C when flagged (downgrade), but original tier is preserved for audit.
        display_tier = "C" if rr.action == "flag" else ev["tier"]
        out.append({
            "timestamp": ev["timestamp"],
            "source": ev["url"],
            "claim": ev["claim"],
            "published_iso": date_iso,
            "retrieval_iso": ev["retrieval_iso"],
            "tier": display_tier,
            "original_tier": ev["tier"],
            "recency_violated": recency_violated,
            "citation_format": f"[{ev['url']} | {date_iso} | {ev['source_title']} | {display_tier}]",
            "age_days": rr.age_days,
        })
        if rr.action == "flag":
            recency_log.append({"source": ev["url"], "age_days": rr.age_days,
                                "budget_days": rr.budget_days, "tier": ev["tier"],
                                "action": "flag"})
    return out
