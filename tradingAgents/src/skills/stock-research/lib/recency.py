"""Recency budget enforcement, tier-graded (recency_budget_days)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Literal

Action = Literal["keep", "flag", "drop"]

BUDGETS = {
    "price": 7,
    "drivers": 7,
    "fundamentals": 120,
    "fair_value": 30,
    "forward_range": 30,
    "macro": 30,
    "quality_factors": 180,
}

REFERENCE_USE_BUDGETS = {
    "price": BUDGETS["price"],
    "drivers": BUDGETS["drivers"],
    "current_setup": BUDGETS["drivers"],
    "fair_value": BUDGETS["fair_value"],
    "analyst_target": BUDGETS["fair_value"],
    "forward_range": BUDGETS["forward_range"],
    "fundamentals": BUDGETS["fundamentals"],
    "filing": BUDGETS["fundamentals"],
    "macro": BUDGETS["macro"],
    "quality_factors": BUDGETS["quality_factors"],
    "moat": BUDGETS["quality_factors"],
    "structural_stability": BUDGETS["quality_factors"],
    "growth_quality": BUDGETS["quality_factors"],
}

def reference_budget(used_in: list[str] | str | None) -> int:
    """Return the strictest applicable budget for a persisted reference."""
    uses = [used_in] if isinstance(used_in, str) else (used_in or [])
    budgets = [REFERENCE_USE_BUDGETS[use] for use in uses if use in REFERENCE_USE_BUDGETS]
    return min(budgets) if budgets else BUDGETS["macro"]

@dataclass
class RecencyResult:
    action: Action
    age_days: int
    budget_days: int
    flag: str | None  # e.g. "recency_violated: 12d over budget"

def age_days(retrieval_iso: str, today_iso: str) -> int:
    """Compute age in days. Both inputs may be full ISO datetimes; only the
    date portion (first 10 chars) is used."""
    def _date(s: str) -> date:
        return date.fromisoformat(s[:10])
    return (_date(today_iso) - _date(retrieval_iso)).days

def check(
    data_type: str, tier: str, retrieval_iso: str, today_iso: str
) -> RecencyResult:
    """Tier-graded recency check.

    - tier-A over budget: keep + flag (downgrade display to C).
    - tier-B / tier-C over budget: drop.
    - within budget: keep.
    """
    budget = BUDGETS[data_type]
    age = age_days(retrieval_iso, today_iso)
    if age <= budget:
        return RecencyResult("keep", age, budget, None)
    if tier == "A":
        flag = f"recency_violated: {age - budget}d over budget"
        return RecencyResult("flag", age, budget, flag)
    return RecencyResult("drop", age, budget, None)
