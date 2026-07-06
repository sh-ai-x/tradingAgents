"""Conflict detection: tier-A disagreement > +/-10% threshold (synthesized vs bracket)."""
from __future__ import annotations
from typing import Iterable

THRESHOLD_PCT = 10.0

def dispersion_pct(values: Iterable[float]) -> float:
    """Return max-relative-deviation of values from their median, in percent.

    dispersion = (max - min) / median * 100
    """
    vs = list(values)
    if not vs:
        return 0.0
    vs_sorted = sorted(vs)
    lo, hi = vs_sorted[0], vs_sorted[-1]
    median = vs_sorted[len(vs_sorted) // 2]
    if median == 0:
        return 0.0
    return (hi - lo) / abs(median) * 100.0

def is_in_conflict(values: Iterable[float], threshold: float = THRESHOLD_PCT) -> bool:
    """True when tier-A values disagree by more than the threshold."""
    return dispersion_pct(values) > threshold

def tier_bracket(values: Iterable[float]) -> tuple[float, float]:
    vs = sorted(values)
    return (vs[0], vs[-1])

def weighted_synthesis(
    values_with_weights: list[tuple[float, float]]
) -> float:
    """Recency+independence-weighted point synthesis."""
    num = sum(v * w for v, w in values_with_weights)
    den = sum(w for _, w in values_with_weights)
    return num / den if den else 0.0
