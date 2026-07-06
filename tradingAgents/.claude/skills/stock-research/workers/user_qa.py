"""user_qa worker.

Owns its own confidence per question. Never fed into fair_value or
forward_range synthesis.
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check
from lib.citation import format_citation

# Per-question recency budget type. Defaults to drivers (7d) unless overridden.
DEFAULT_BUDGET = "drivers"

def run(qas: list[dict[str, Any]], today_iso: str) -> list[dict[str, Any]]:
    """qas = [{"question": str, "answer": str, "sources": [...], "budget_type": str}]"""
    out = []
    for q in qas:
        budget = q.get("budget_type", DEFAULT_BUDGET)
        sources = q.get("sources", [])
        kept_sources = []
        evidence_tier = "C"
        for s in sources:
            rr = recency_check(budget, s["tier"], s["retrieval_iso"], today_iso)
            if rr.action == "drop":
                continue
            kept_sources.append(s)
            if s["tier"] == "A":
                evidence_tier = "A"
            elif s["tier"] == "B" and evidence_tier != "A":
                evidence_tier = "B"
        citations = [format_citation(s["url"], s["retrieval_iso"], s["source_title"], s["tier"]) for s in kept_sources]
        tier_summary = {
            "A": sum(1 for s in kept_sources if s["tier"] == "A"),
            "B": sum(1 for s in kept_sources if s["tier"] == "B"),
            "C": sum(1 for s in kept_sources if s["tier"] == "C"),
        }
        out.append({
            "question": q["question"],
            "answer": q["answer"],
            "sources": citations,
            "tier_summary": tier_summary,
            "recency_budget_type": budget,
            "evidence_tier": evidence_tier,
            "citation_format": "[URL | retrieval_iso | source_title | tier]",
        })
    return out
