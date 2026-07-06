"""AC2: Numerical outputs cross-validate against multiple independent cited
evidence streams; forward-range probabilities sum to 1.0 with each range
evidence-backed; tier-A disagreement > ±10% emits tier-A-anchored bracket
with conflict:true and annotated outliers (probabilities suppressed).

Run from repo root or tradingAgents/:
    python3 -m unittest tradingAgents.tests.test_ac2_cross_validation_and_conflict
    python3 tradingAgents/tests/test_ac2_cross_validation_and_conflict.py
"""
from __future__ import annotations
import json
import os
import sys
import unittest
from pathlib import Path

# Resolve skill paths regardless of invocation cwd.
HERE = Path(__file__).resolve()
SKILL_ROOT = HERE.parent.parent / ".claude" / "skills" / "stock-research"
sys.path.insert(0, str(SKILL_ROOT))
sys.path.insert(0, str(SKILL_ROOT / "workers"))
sys.path.insert(0, str(SKILL_ROOT / "lib"))

from workers import forward_range, fair_value  # noqa: E402
from lib.conflict import is_in_conflict, dispersion_pct  # noqa: E402

TODAY = "2026-07-07T10:15:00Z"


def _rng(label, low, high, p, ec, url, tier, ret="2026-06-25"):
    return {"label": label, "low": low, "high": high, "probability": p,
            "evidence_count": ec, "url": url, "retrieval_iso": ret,
            "source_title": f"{label} case", "tier": tier}


def _fv(value, url, tier, ret="2026-06-25"):
    return {"value": value, "url": url, "retrieval_iso": ret,
            "source_title": f"src {url}", "tier": tier}


class FairValueCrossValidationTests(unittest.TestCase):
    """(a) fair_value cross-validates against multiple independent cited streams."""

    def test_fair_value_with_multiple_tier_a_synthesizes(self):
        estimates = [
            _fv(215.0, "https://www.goldmansachs.com/x", "A", "2026-06-30"),
            _fv(222.0, "https://www.morganstanley.com/x", "A", "2026-06-25"),
            _fv(218.0, "https://finance.yahoo.com/x", "B", "2026-07-02"),
        ]
        out = fair_value.run(estimates, TODAY)
        self.assertEqual(out["mode"], "synthesized")
        self.assertFalse(out["conflict"])
        # Citations come from at least 3 independent evidence streams.
        self.assertGreaterEqual(len(out["citations"]), 3)
        # The synthesized point sits inside the tier-A bracket.
        self.assertGreaterEqual(out["point"], 215.0)
        self.assertLessEqual(out["point"], 222.0)
        # band_low/high form a meaningful cross-checked range.
        self.assertLess(out["band_low"], out["point"])
        self.assertGreater(out["band_high"], out["point"])

    def test_fair_value_cites_each_independent_stream(self):
        estimates = [
            _fv(215.0, "https://www.goldmansachs.com/x", "A", "2026-06-30"),
            _fv(222.0, "https://www.morganstanley.com/x", "A", "2026-06-25"),
        ]
        out = fair_value.run(estimates, TODAY)
        # Two independent tier-A streams cited with unique URLs.
        urls = [c.split("|")[0].strip(" []") for c in out["citations"]]
        self.assertEqual(len(urls), 2)
        self.assertEqual(len(set(urls)), 2)


class ForwardRangeSynthesisTests(unittest.TestCase):
    """(b) forward-range probabilities sum to 1.0, each range evidence-backed."""

    def test_probabilities_sum_to_one(self):
        ranges = [
            _rng("bear", 200.0, 215.0, 0.3, 3, "https://www.morganstanley.com/r1", "A", "2026-06-20"),
            _rng("base", 210.0, 225.0, 0.5, 5, "https://www.goldmansachs.com/r1", "A", "2026-06-25"),
            _rng("bull", 220.0, 235.0, 0.2, 3, "https://www.jpmorgan.com/r1", "A", "2026-06-28"),
        ]
        out = forward_range.run(ranges, TODAY)
        self.assertEqual(out["mode"], "synthesized")
        self.assertFalse(out["conflict"])
        probs = [r["probability"] for r in out["ranges"]]
        self.assertAlmostEqual(sum(probs), 1.0, places=9)
        for r in out["ranges"]:
            self.assertGreater(r.get("evidence_count", 0), 0,
                                f"range {r['label']} has no evidence")

    def test_unnormalized_inputs_are_renormalized(self):
        # Input probabilities do not sum to 1.0; renormalization required.
        ranges = [
            _rng("bear", 200.0, 215.0, 1.0, 3, "https://www.morganstanley.com/r1", "A", "2026-06-20"),
            _rng("base", 210.0, 225.0, 2.0, 5, "https://www.goldmansachs.com/r1", "A", "2026-06-25"),
            _rng("bull", 220.0, 235.0, 1.0, 3, "https://www.jpmorgan.com/r1", "A", "2026-06-28"),
        ]
        out = forward_range.run(ranges, TODAY)
        probs = [r["probability"] for r in out["ranges"]]
        self.assertAlmostEqual(sum(probs), 1.0, places=9)

    def test_zero_evidence_range_is_dropped(self):
        ranges = [
            _rng("bear", 200.0, 215.0, 0.3, 3, "https://www.morganstanley.com/r1", "A", "2026-06-20"),
            _rng("base", 210.0, 225.0, 0.5, 0, "https://www.goldmansachs.com/r1", "A", "2026-06-25"),  # no evidence
            _rng("bull", 220.0, 235.0, 0.2, 3, "https://www.jpmorgan.com/r1", "A", "2026-06-28"),
        ]
        out = forward_range.run(ranges, TODAY)
        labels = [r["label"] for r in out["ranges"]]
        self.assertNotIn("base", labels)
        self.assertEqual(len(labels), 2)
        probs = [r["probability"] for r in out["ranges"]]
        self.assertAlmostEqual(sum(probs), 1.0, places=9)


class ConflictBracketTests(unittest.TestCase):
    """(c) tier-A disagreement > ±10% -> bracket + conflict:true + outliers."""

    def test_tier_a_disagreement_within_band_synthesizes(self):
        # Midpoints 200, 210, 220 -> dispersion (220-200)/210*100 = 9.5% < 10%.
        ranges = [
            _rng("bear", 195.0, 205.0, 0.3, 3, "https://www.morganstanley.com/r1", "A", "2026-06-20"),
            _rng("base", 205.0, 215.0, 0.5, 5, "https://www.goldmansachs.com/r1", "A", "2026-06-25"),
            _rng("bull", 215.0, 225.0, 0.2, 3, "https://www.jpmorgan.com/r1", "A", "2026-06-28"),
        ]
        out = forward_range.run(ranges, TODAY)
        self.assertEqual(out["mode"], "synthesized")
        self.assertFalse(out["conflict"])
        self.assertEqual(out["outliers"], [])
        self.assertGreater(len(out["ranges"]), 0)

    def test_tier_a_disagreement_beyond_band_emits_bracket(self):
        # Midpoints 185, 220, 247.5 -> dispersion > 10%.
        ranges = [
            _rng("bear", 175.0, 195.0, 0.2, 2, "https://www.morganstanley.com/r1", "A", "2026-06-20"),
            _rng("base", 210.0, 230.0, 0.55, 5, "https://www.goldmansachs.com/r1", "A", "2026-06-25"),
            _rng("bull", 235.0, 260.0, 0.25, 3, "https://www.jpmorgan.com/r1", "A", "2026-06-28"),
        ]
        out = forward_range.run(ranges, TODAY)
        # Bracket mode
        self.assertEqual(out["mode"], "bracket")
        self.assertTrue(out["conflict"])
        # Probabilities suppressed
        self.assertEqual(out["ranges"], [])
        # Tier-A-anchored bracket = [min(tier-A low), max(tier-A high)]
        self.assertEqual(out["tier_anchor_low"], 175.0)
        self.assertEqual(out["tier_anchor_high"], 260.0)
        # Outliers annotated — never collapsed
        self.assertGreater(len(out["outliers"]), 0)
        for o in out["outliers"]:
            self.assertTrue(o["annotation"].startswith("[outlier:"))
            self.assertEqual(o["tier"], "A")

    def test_two_tier_a_far_apart_emits_bracket(self):
        # Two tier-A streams with midpoints differing by > 10%.
        ranges = [
            _rng("low", 100.0, 110.0, 0.5, 3, "https://www.morganstanley.com/r1", "A", "2026-06-20"),
            _rng("high", 200.0, 210.0, 0.5, 3, "https://www.goldmansachs.com/r1", "A", "2026-06-25"),
        ]
        out = forward_range.run(ranges, TODAY)
        self.assertEqual(out["mode"], "bracket")
        self.assertTrue(out["conflict"])
        self.assertEqual(out["ranges"], [])
        self.assertEqual(out["tier_anchor_low"], 100.0)
        self.assertEqual(out["tier_anchor_high"], 210.0)

    def test_dispersion_helper_threshold(self):
        # Sanity: dispersion_pct returns the right shape around the 10% boundary.
        self.assertGreater(dispersion_pct([100, 200]), 10.0)
        self.assertLessEqual(dispersion_pct([200, 210, 220]), 10.0)


class LowConfidenceTests(unittest.TestCase):
    """(d) low_confidence when tier-A count == 0."""

    def test_no_tier_a_marks_low_confidence_but_synthesizes(self):
        ranges = [
            _rng("bear", 175.0, 195.0, 0.3, 3, "https://finance.yahoo.com/r1", "B", "2026-06-20"),
            _rng("base", 210.0, 230.0, 0.5, 5, "https://www.marketwatch.com/r1", "B", "2026-06-25"),
        ]
        out = forward_range.run(ranges, TODAY)
        self.assertTrue(out["low_confidence"])
        # Probabilities still sum to 1.0 even without tier-A.
        probs = [r["probability"] for r in out["ranges"]]
        self.assertAlmostEqual(sum(probs), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()