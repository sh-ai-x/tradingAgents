"""evidence_synthesizer — recency + independence weighting helpers."""
from __future__ import annotations
from typing import Any
from lib.conflict import weighted_synthesis

def synthesize(values_with_weights: list[tuple[float, float]]) -> float:
    return weighted_synthesis(values_with_weights)
