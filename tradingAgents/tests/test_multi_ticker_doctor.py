from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src" / "skills" / "stock-research"
sys.path[:0] = [str(ROOT.parent), str(SKILL), str(SKILL / "workers"), str(SKILL / "lib")]

from tradingAgents import _impl  # noqa: E402
from workers import doctor  # noqa: E402


def multi_bundle() -> dict:
    refs = []
    for ticker in ("AAA", "BBB"):
        for index in range(10):
            refs.append({
                "ticker": ticker,
                "url": f"https://source{index % 5}.example/{ticker}/{index}",
                "domain": f"source{index % 5}.example",
                "source_title": f"{ticker} source {index}",
                "published_iso": "2026-07-10",
                "tier": "A" if index == 0 else "B",
                "used_in": ["drivers"],
                "reference_confidence_score": 80,
                "confidence_grade": "high",
            })
    return {
        "run_id": "multi-run", "status": "complete",
        "retrieval_iso": "2026-07-11T12:00:00Z", "tickers": ["AAA", "BBB"],
        "current_prices": {}, "evidence_coverage": {}, "fair_value": {},
        "forward_range": {}, "band_probability_table": [
            {"ticker": "AAA", "bands": [{"probability": 0.4}, {"probability": 0.6}]},
            {"ticker": "BBB", "bands": [{"probability": 1.0}]},
        ],
        "quality_factors": {}, "comparative_ranking": [], "action_guidance": [],
        "reference_confidence_table": refs, "drivers": {"AAA": [], "BBB": []},
    }


class MultiTickerDoctorTests(unittest.TestCase):
    def test_deep_doctor_accepts_multi_ticker_bundle(self):
        result = doctor.run(multi_bundle(), deep=True)
        self.assertEqual(result["verdict"], "pass", result["errors"])

    def test_probability_sum_is_validated(self):
        bundle = multi_bundle()
        bundle["band_probability_table"][0]["bands"][0]["probability"] = 0.3
        result = doctor.run(bundle)
        self.assertTrue(any("probabilities sum" in error for error in result["errors"]))

    def test_show_searches_workspace_runtime_and_matches_embedded_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            plugin_runtime = workspace / "tradingAgents" / ".stock-research"
            workspace_runtime = workspace / ".stock-research" / "MULTI"
            plugin_runtime.mkdir(parents=True)
            workspace_runtime.mkdir(parents=True)
            path = workspace_runtime / "filename-differs.json"
            path.write_text(json.dumps(multi_bundle()), encoding="utf-8")
            loaded = _impl.show("multi-run", plugin_runtime)
            self.assertEqual(loaded["run_id"], "multi-run")


if __name__ == "__main__":
    unittest.main()
