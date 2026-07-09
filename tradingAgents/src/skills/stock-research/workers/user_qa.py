"""user_qa worker.

Owns its own confidence per question. Never fed into fair_value or
forward_range synthesis. When every cited source for a question is
over-budget and dropped, the question is answered with
``not_found_in_budget`` and the search terms attempted are recorded
(rather than inventing an answer).
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check
from lib.citation import MissingPublicationDate, format_citation, source_date_iso

# Per-question recency budget type. Defaults to drivers (7d) unless overridden.
DEFAULT_BUDGET = "drivers"


def _not_found(recency_log, sources, budget, today_iso, question):
    """Emit not_found_in_budget for a question whose sources were all dropped."""
    search_terms = []
    for s in sources or []:
        search_terms.append(s.get("source_title") or s.get("url", ""))
        try:
            date_iso = source_date_iso(s)
        except MissingPublicationDate:
            recency_log.append({
                "source": s.get("url", ""), "tier": s.get("tier", ""),
                "action": "missing_published_iso", "context": question,
            })
            continue
        rr = recency_check(budget, s["tier"], date_iso, today_iso)
        if rr.action == "drop":
            recency_log.append({
                "source": s["url"], "age_days": rr.age_days,
                "budget_days": rr.budget_days, "tier": s["tier"],
                "action": "drop", "context": question,
            })
    return {
        "answer": (
            f"not_found_in_budget -- no in-budget sources for question "
            f"(budget={budget}d). Search terms attempted: "
            f"{[t for t in search_terms if t]}"
        ),
        "search_terms_attempted": [t for t in search_terms if t],
        "evidence_tier": "C",
        "tier_summary": {"A": 0, "B": 0, "C": 0},
        "citations": [],
    }


def run(qas, today_iso):
    """qas = [{"question": str, "answer": str, "sources": [...], "budget_type": str}]"""
    out = []
    recency_log: list[dict[str, Any]] = []
    for q in qas:
        budget = q.get("budget_type", DEFAULT_BUDGET)
        sources = q.get("sources", []) or []
        kept_sources: list[dict[str, Any]] = []
        evidence_tier = "C"
        for s in sources:
            try:
                date_iso = source_date_iso(s)
            except MissingPublicationDate:
                recency_log.append({
                    "source": s.get("url", ""), "tier": s.get("tier", ""),
                    "action": "missing_published_iso",
                    "context": q.get("question", ""),
                })
                continue
            rr = recency_check(budget, s["tier"], date_iso, today_iso)
            if rr.action == "drop":
                recency_log.append({
                    "source": s["url"], "age_days": rr.age_days,
                    "budget_days": rr.budget_days, "tier": s["tier"],
                    "action": "drop", "context": q.get("question", ""),
                })
                continue
            kept_sources.append(s)
            if s["tier"] == "A":
                evidence_tier = "A"
            elif s["tier"] == "B" and evidence_tier != "A":
                evidence_tier = "B"

        if not kept_sources:
            nf = _not_found(recency_log, sources, budget, today_iso, q.get("question", ""))
            out.append({
                "question": q["question"],
                "answer": nf["answer"],
                "sources": [],
                "tier_summary": nf["tier_summary"],
                "recency_budget_type": budget,
                "evidence_tier": nf["evidence_tier"],
                "citation_format": "[URL | published_iso | source_title | tier]",
                "search_terms_attempted": nf["search_terms_attempted"],
            })
            continue

        citations = [
            format_citation(s["url"], source_date_iso(s), s["source_title"], s["tier"])
            for s in kept_sources
        ]
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
            "citation_format": "[URL | published_iso | source_title | tier]",
        })
    return out, recency_log
