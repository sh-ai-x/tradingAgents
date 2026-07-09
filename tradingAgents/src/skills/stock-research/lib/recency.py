"""Recency budget enforcement, tier-graded (recency_budget_days)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Literal

Action = Literal["keep", "flag", "drop"]

BUDGETS = {
    "price": 7,
    "drivers": 7,
    "fundamentals": 90,
    "fair_value": 90,
    "forward_range": 90,
    "macro": 30,
}

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
