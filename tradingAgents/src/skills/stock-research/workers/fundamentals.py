"""fundamentals worker.

Normalizes company filing metrics, preferably fetched from SEC EDGAR via
``secedgar``. This worker does not download filings itself; host agents or
retrieval code provide filing-derived rows with URLs, accession metadata, and
metrics extracted from 10-K/10-Q filings.
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check
from lib.citation import MissingPublicationDate, source_date_iso


def run(rows: list[dict[str, Any]], today_iso: str) -> list[dict[str, Any]]:
    """rows = [{"metric": str, "value": str|float, "period": str,
                 "filing_type": "10-Q"|"10-K", "filing_date": str,
                 "accession": str, "source": str, "published_iso": str,
                 "retrieval_iso": str, "source_title": str,
                 "tier": "A"|"B"|"C"}]"""
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            date_iso = source_date_iso(row)
        except MissingPublicationDate:
            continue
        rr = recency_check("fundamentals", row["tier"], date_iso, today_iso)
        if rr.action == "drop":
            continue
        display_tier = "C" if rr.action == "flag" else row["tier"]
        recency_violated = (
            f"[recency_violated: {rr.age_days - rr.budget_days}d over budget]"
            if rr.action == "flag"
            else None
        )
        out.append({
            "metric": row["metric"],
            "value": row["value"],
            "period": row.get("period", ""),
            "filing_type": row.get("filing_type", ""),
            "filing_date": row.get("filing_date", ""),
            "accession": row.get("accession", ""),
            "source": row["source"],
            "source_title": row.get("source_title", row["metric"]),
            "published_iso": date_iso,
            "retrieval_iso": row["retrieval_iso"],
            "tier": display_tier,
            "original_tier": row["tier"],
            "recency_violated": recency_violated,
            "citation_format": (
                f"[{row['source']} | {date_iso} | "
                f"{row.get('source_title', row['metric'])} | {display_tier}]"
            ),
            "age_days": rr.age_days,
        })
    return out
