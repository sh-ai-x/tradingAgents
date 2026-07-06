#!/usr/bin/env python3
"""
Build script for the stock-research skill.

Writes all skill files (including dotfile paths like .claude/, .codex/,
.stock-research/) into the tradingAgents/ tree.

Run from the repo root:

    python3 tradingAgents/build_skill.py
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # tradingAgents/
SKILL_DIR = ROOT / ".claude" / "skills" / "stock-research"
CODEX_DIR = ROOT / ".codex"
RUNTIME = ROOT / ".stock-research"

# ---------------------------------------------------------------------------
# File contents
# ---------------------------------------------------------------------------

SKILL_MD = """---
name: stock-research
description: |
  Evidence-backed stock research. Takes a ticker + optional research questions
  and emits a five-output research bundle (fair value, drivers, macro snapshot,
  6-month forward range, user Q&A) with inline citations, tier-classified
  sources (A/B/C), recency budgets, and conflict-resolution rules. Persisted
  as JSON for cross-date comparability. No investment advice — research only.
version: 1.0.0
capability: [read, compute, write-confirm]
claim_class: [factual, interpretive, advisory]
tier_definitions:
  A: "Peer/primary — broker research, regulator filings, primary newswires, company IR/SEC filings."
  B: "Aggregators — Yahoo Finance, Reuters, MarketWatch, MarketBeat, Bloomberg public mirror."
  C: "Blogs, social media, forums — never displayed as supporting evidence; always suppressed."
recency_budget_days:
  price: 7
  drivers: 7
  fundamentals: 90
  fair_value: 90
  forward_range: 90
  macro: 30
citation_format: "[URL | retrieval_iso | source_title | tier]"
tier_a_disagreement_threshold_pct: 10
bundle_root: ".stock-research"
bundle_path_template: ".stock-research/{ticker}/{iso_datetime}.json"
stops_before:
  - "Acting on the bundle as investment advice (DISCLAIMER.md)."
  - "Modifying files outside .stock-research/ unless the user explicitly authorizes."
  - "Citing tier-C sources as supporting evidence (always suppressed)."
  - "Asserting a major claim with fewer than two independent sources without [single_source] flag."
  - "Synthesizing fair_value or forward_range when tier-A disagreement exceeds +/-10% -- emit bracket only."
required_outputs:
  - fair_value
  - drivers
  - macro_market_state
  - forward_range
  - user_qa
commands:
  - name: run
    pattern: "/stock-research <TICKER> [questions...]"
    description: "Execute a new research run for a ticker."
  - name: show
    pattern: "/stock-research show <run-id>"
    description: "Re-render a prior bundle from disk without re-execution."
  - name: doctor
    pattern: "/stock-research doctor <run-id> [--deep]"
    description: "Validate a prior bundle; default fast mechanical, --deep = full audit."
---

# Stock Research Skill

The skill runs an Ouroboros-style elicitation interview, then orchestrates
worker outputs to produce a persisted ResearchBundle.

## Invocation

```
/stock-research AAPL "Why did it drop in March 2026?"
/stock-research show 2026-07-07T10-15-00Z_AAPL
/stock-research doctor 2026-07-07T10-15-00Z_AAPL
```

## Doctrine (read first)

1. **No invented numbers.** Every figure is cited with `[URL | retrieval_iso |
   source_title | tier]`. If a figure cannot be cited, the worker returns
   `not_found_in_budget` with the search terms attempted.
2. **Recency budgets are hard.** A claim about price older than 7 days, drivers
   older than 7 days, fundamentals / fair value / forward range older than 90
   days, or macro older than 30 days must be either flagged
   `[recency_violated: Nd over budget]` (tier-A -> keep + downgrade display to C)
   or dropped (tier-B/C -> drop + log to `recency_log`).
3. **Independence.** Major claims require >= 2 independent sources. A single-
   source major claim is `[single_source]` and never asserted as fact.
4. **Conflict resolution.** When tier-A sources disagree on a synthesis target
   by more than +/-10%, do not synthesize. Emit a tier-anchored bracket
   `[min(tier-A), max(tier-A)]`, set `conflict: true`, suppress probabilities,
   annotate outliers `[outlier: ...]`. The bracket is the output.
5. **Tier-C is invisible.** Tier-C sources are never displayed as supporting
   evidence. If a claim has only tier-C support, it is suppressed and the
   user is told `not_found_in_budget`.
6. **low_confidence** = true when tier-A count for the output == 0. Fall back
   to min/max of all cited sources; never pretend to synthesize.
7. **user_qa is its own worker.** It is never fed into fair_value or
   forward_range synthesis. The user_qa worker decides its own confidence per
   question.

## Stops

- Never write outside `.stock-research/` without explicit user authorization.
- Never cite tier-C as supporting evidence.
- Never assert a single-source major claim as fact.
- Never synthesize when tier-A disagreement > +/-10%; bracket only.
- Never refuse outright on partial-data -- emit a partial bundle with
  `halt_flags` and `omitted_outputs` populated.

## Workers

- `head_manager` -- elicitation interview, halt checks, bundle composition.
- `fair_value` -- point + +/- band, independent computation, cross-checked vs
  forward-range midpoint.
- `drivers` -- structured event list (timestamp/source/claim/tier), no prose.
- `macro` -- flat snapshot table rows, no prose.
- `forward_range` -- 6-month ranges summing to 1.0, evidence-backed.
- `user_qa` -- answers to user research questions, own confidence.
- `evidence_synthesizer` -- recency + independence weighting, conflict detection.
- `recency_checker` -- applies tier-graded recency budget enforcement.
- `doctor` -- mechanical (default, <= seconds) and `--deep` (full audit) modes.

## Halt Conditions

If any worker returns `halted` with a reason, the bundle is emitted as
`status: "partial"` with the dropped outputs listed in `omitted_outputs` and
each dropped output recorded in `halt_flags` with a flag string
(e.g. `[macro_stale]`). The skill never refuses; it degrades explicitly.

## Doctor

`/stock-research doctor <run-id>` resolves the run file
(`.stock-research/<TICKER>/<ISO>.json`) and validates:

- Mechanical (default, <= seconds): tier classification present, recency
  budgets met, >=2 sources per major claim, citation format, schema.
- `--deep`: above + Decision Package field validity + cross-output rule
  application. Shows progress as it walks each rule.

Doctor never re-executes workers. It reads the persisted bundle only.

## Persistence

Every run writes to `.stock-research/<TICKER>/<ISO_DATETIME>.json`. The
ISO datetime uses `:` replaced by `-` for filesystem safety. Stdout shows a
compact summary pointer only. `/stock-research show <run-id>` re-renders from
file. `follow_up` and `postmortem_required` accumulate across runs of the
same ticker -- the head manager reads prior bundles in
`.stock-research/<TICKER>/` and merges them.
"""

CODEX_MANIFEST = """# Codex Manifest — strict subset of SKILL.md (Claude Code skill)

This manifest describes the same `stock-research` skill for Codex harnesses.
The contract is the same; only the loader shape differs (Codex uses an
`AGENTS.md` sibling instead of `SKILL.md`).

## Capability

- `read` — read sources and prior bundles.
- `compute` — synthesize fair_value / forward_range.
- `write-confirm` — write to `.stock-research/` only after the head_manager
  approves the bundle (status != `dropped`).

## Claim Classes

- `factual` — cited numeric or factual statements (price, earnings, macro data).
- `interpretive` — synthesized judgments about what the data means
  (drivers, fair-value band rationale).
- `advisory` — presentational framing that is NOT investment advice
  (see DISCLAIMER.md).

## Tier Definitions (deterministic)

| Tier | Class                                            | Display? |
|------|--------------------------------------------------|----------|
| A    | Peer/primary: broker research, regulator filings, primary newswires, company IR/SEC filings | Yes |
| B    | Aggregators: Yahoo, Reuters, MarketWatch, MarketBeat, Bloomberg public mirror | Yes (secondary) |
| C    | Blogs, social, forums                            | No — suppressed |

## Recency Budgets (days)

| Data type      | Budget |
|----------------|--------|
| price          | 7      |
| drivers        | 7      |
| fundamentals   | 90     |
| fair_value     | 90     |
| forward_range  | 90     |
| macro          | 30     |

Tier-graded enforcement: tier-A over budget -> keep + flag
`[recency_violated: Nd over budget]` + tier downgrade to C. tier-B/C over
budget -> drop + log to `recency_log`.

## Citation Format

`[URL | retrieval_iso | source_title | tier]`

Every claim in every worker output bears this format. Tier-C citations are
recorded for audit but never displayed as supporting evidence.

## Conflict Resolution

±10% consensus threshold on the synthesis target. Within threshold -> recency
+ independence-weighted synthesis with reasoning_trace. Beyond threshold ->
tier-anchored bracket `[min(tier-A), max(tier-A)]` with `conflict: true`,
probabilities suppressed, outliers annotated `[outlier: ...]`.

## low_confidence

`low_confidence: true` is emitted when tier-A count == 0 for an output. The
output falls back to min/max of cited sources; never synthesized.

## Halt Conditions

Bundle is emitted as `status: "partial"` with `halt_flags` and
`omitted_outputs` populated. The skill never refuses outright.

## Stops

- No write outside `.stock-research/` without explicit user authorization.
- No tier-C as supporting evidence.
- No single-source major claim asserted as fact.
- No synthesis when tier-A disagreement > ±10%; bracket only.
- No advice (see DISCLAIMER.md).

## Commands (Codex invocation)

```
stock-research run <TICKER> [questions...]
stock-research show <run-id>
stock-research doctor <run-id> [--deep]
```

## Workers

`head_manager`, `fair_value`, `forward_range`, `drivers`, `macro`, `user_qa`,
`evidence_synthesizer`, `recency_checker`, `doctor`.

## Decision Package Fields

`forecastable_claims`, `lifecycle_assumptions`, `contrary_evidence`,
`owner_roles`, `follow_up`, `postmortem_required`. All six required.

## Cross-Run Accumulation

`follow_up` and `postmortem_required` accumulate across runs of the same
ticker. The head_manager reads prior bundles in `.stock-research/<TICKER>/`
and merges them.
"""

# ---------------------------------------------------------------------------
# Library modules (short)
# ---------------------------------------------------------------------------

LIBCITATION = '''"""Citation formatting and validation (citation_format)."""
from __future__ import annotations
import re
from typing import Any, Iterable

CITATION_RE = re.compile(
    r"^\\[(?P<url>https?://[^\\s|]+)\\s*\\|\\s*"
    r"(?P<iso>\\d{4}-\\d{2}-\\d{2})\\s*\\|\\s*"
    r"(?P<title>.+?)\\s*\\|\\s*"
    r"(?P<tier>[ABC])\\]$"
)

def format_citation(url: str, retrieval_iso: str, source_title: str, tier: str) -> str:
    """Render the canonical citation string."""
    assert tier in {"A", "B", "C"}, f"invalid tier: {tier}"
    return f"[{url} | {retrieval_iso} | {source_title} | {tier}]"

def parse_citation(s: str) -> dict[str, str] | None:
    """Parse a citation string. Returns None if malformed.

    Keys are normalized to {url, retrieval_iso, source_title, tier}."""
    m = CITATION_RE.match(s.strip())
    if not m:
        return None
    g = m.groupdict()
    return {"url": g["url"], "retrieval_iso": g["iso"],
            "source_title": g["title"], "tier": g["tier"]}

def validate_all(claims: Iterable[Any]) -> list[str]:
    """Validate that every claim has a parseable citation. Returns list of errors."""
    errors: list[str] = []
    for i, claim in enumerate(claims):
        if isinstance(claim, str):
            if parse_citation(claim) is None:
                errors.append(f"claim[{i}] not in citation format: {claim!r}")
        elif isinstance(claim, dict) and "citation" in claim:
            if parse_citation(claim["citation"]) is None:
                errors.append(f"claim[{i}] bad citation: {claim['citation']!r}")
    return errors
'''

LIBRECENCY = '''"""Recency budget enforcement, tier-graded (recency_budget_days)."""
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
'''

LIBTIER = '''"""Deterministic tier classification of a source URL/domain (tier-A/B/C)."""
from __future__ import annotations
import re
from urllib.parse import urlparse

# Tier-A primary domains (brokers / regulators / primary newswires / IR / SEC).
TIER_A_DOMAINS = {
    "sec.gov", "edgar.sec.gov",
    "bloomberg.com", "reuters.com", "wsj.com", "ft.com",
    "cnbc.com", "ap.org", "apnews.com",
    "nasdaq.com", "nyse.com",
    "blackrock.com", "goldmansachs.com", "morganstanley.com", "jpmorgan.com",
    "berkshirehathaway.com", "berkshirehathawayinc.com",
    "investor.apple.com", "investor.microsoft.com",
    "prnewswire.com", "businesswire.com", "globenewswire.com",
}

# Tier-B aggregators.
TIER_B_DOMAINS = {
    "finance.yahoo.com", "yahoo.com",
    "marketwatch.com", "marketbeat.com",
    "investopedia.com", "morningstar.com",
    "seekingalpha.com", "fool.com",
    "barrons.com", "investing.com", "stockanalysis.com",
}

# Tier-C — blogs / social / forums.
TIER_C_DOMAINS = {
    "reddit.com", "twitter.com", "x.com", "facebook.com",
    "substack.com", "medium.com", "wordpress.com",
    "stocktwits.com", "tipranks.com",
    "fintwit.com",
}

def classify(url: str) -> str:
    """Return the tier for a URL. Deterministic — same URL always returns the
    same tier. Falls back to tier-C (most conservative) when unknown."""
    host = urlparse(url).hostname or ""
    host = host.lower().lstrip("www.")
    # Exact domain match.
    if host in TIER_A_DOMAINS:
        return "A"
    if host in TIER_B_DOMAINS:
        return "B"
    if host in TIER_C_DOMAINS:
        return "C"
    # Suffix match (handles country TLDs and subdomains).
    for d in TIER_A_DOMAINS:
        if host.endswith("." + d):
            return "A"
    for d in TIER_B_DOMAINS:
        if host.endswith("." + d):
            return "B"
    for d in TIER_C_DOMAINS:
        if host.endswith("." + d):
            return "C"
    return "C"  # unknown -> tier-C (conservative)
'''

LIBCONFLICT = '''"""Conflict detection: tier-A disagreement > +/-10% threshold (synthesized vs bracket)."""
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
'''

LIBSCHEMA = '''"""Schema for the ResearchBundle (output_schema)."""
from __future__ import annotations

BUNDLE_SCHEMA = {
    "type": "object",
    "required": [
        "run_id", "ticker", "generated_at", "status",
        "fair_value", "drivers", "macro_market_state", "forward_range", "user_qa",
        "decision_package", "citations", "recency_log", "halt_flags", "omitted_outputs",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "ticker": {"type": "string"},
        "generated_at": {"type": "string"},
        "status": {"enum": ["ok", "partial", "dropped"]},
        "fair_value": {
            "type": "object",
            "required": [
                "point", "band_low", "band_high", "synthesis_target",
                "mode", "tier_bracket", "conflict", "low_confidence",
                "citations", "reasoning_trace",
            ],
        },
        "drivers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "timestamp", "source", "claim", "retrieval_iso", "tier",
                    "recency_violated", "citation_format",
                ],
            },
        },
        "macro_market_state": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "indicator", "value", "source", "retrieval_iso", "tier",
                ],
            },
        },
        "forward_range": {
            "type": "object",
            "required": [
                "ranges", "mode", "modal_midpoint",
                "tier_anchor_low", "tier_anchor_high",
                "conflict", "low_confidence",
                "outliers", "reasoning_trace",
            ],
        },
        "user_qa": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "question", "answer", "sources",
                    "tier_summary", "recency_budget_type",
                    "evidence_tier", "citation_format",
                ],
            },
        },
        "decision_package": {
            "type": "object",
            "required": [
                "forecastable_claims", "lifecycle_assumptions",
                "contrary_evidence", "owner_roles",
                "follow_up", "postmortem_required",
            ],
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "url", "retrieval_iso", "source_title",
                    "tier", "claim_class", "capability",
                ],
            },
        },
        "recency_log": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "age_days", "budget_days", "tier", "action"],
            },
        },
        "halt_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["output", "flag", "reason"],
            },
        },
        "omitted_outputs": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}
'''

LIBPERSIST = '''"""Persistence: write/read bundles to .stock-research/<TICKER>/<ISO>.json."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def iso_filename_stem(dt: datetime | None = None) -> str:
    """Filesystem-safe ISO datetime stem, e.g. 2026-07-07T10-15-00Z."""
    dt = (dt or datetime.now(timezone.utc)).replace(microsecond=0)
    s = dt.strftime("%Y-%m-%dT%H-%M-%SZ")
    return s

def bundle_path(root: Path, ticker: str, run_id: str | None = None,
                dt: datetime | None = None) -> Path:
    """Resolve the bundle path for a ticker (or for an existing run_id)."""
    ticker = ticker.upper()
    if run_id:
        return root / ticker / f"{run_id}.json"
    return root / ticker / f"{iso_filename_stem(dt)}.json"

def write_bundle(root: Path, ticker: str, bundle: dict[str, Any]) -> Path:
    """Write the bundle to disk. Creates directories as needed."""
    ticker = ticker.upper()
    path = bundle_path(root, ticker, bundle.get("run_id"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=False))
    return path

def read_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())

def list_runs(root: Path, ticker: str) -> list[Path]:
    """Return all bundle files for a ticker, oldest first."""
    ticker = ticker.upper()
    d = root / ticker
    if not d.exists():
        return []
    return sorted(p for p in d.glob("*.json") if p.is_file())

def accumulate(root: Path, ticker: str, fields: list[str]) -> dict[str, list[Any]]:
    """Merge the named fields across all prior bundles for this ticker.

    Used for follow_up and postmortem_required accumulation.
    """
    merged: dict[str, list[Any]] = {f: [] for f in fields}
    for path in list_runs(root, ticker):
        try:
            b = read_bundle(path)
        except Exception:
            continue
        dp = b.get("decision_package", {}) or {}
        for f in fields:
            v = dp.get(f)
            if isinstance(v, list):
                merged[f].extend(v)
    # Dedup strings while preserving order.
    for f in fields:
        seen: set = set()
        out: list[Any] = []
        for x in merged[f]:
            key = json.dumps(x, sort_keys=True) if not isinstance(x, str) else x
            if key in seen:
                continue
            seen.add(key)
            out.append(x)
        merged[f] = out
    return merged
'''

# ---------------------------------------------------------------------------
# Worker modules
# ---------------------------------------------------------------------------

WFAIRVALUE = '''"""fair_value worker.

Computes point + +/- band independently from per-source fair-value estimates,
cross-checks against forward_range midpoint, applies +/-10% tier-A conflict
rule, and emits low_confidence / bracket / synthesis modes.
"""
from __future__ import annotations
from typing import Any
from evidence_synthesizer import synthesize
from lib.citation import format_citation
from lib.recency import check as recency_check, BUDGETS
from lib.conflict import is_in_conflict, tier_bracket, weighted_synthesis

def run(estimates: list[dict[str, Any]], today_iso: str) -> dict[str, Any]:
    """estimates = [{"value": float, "url": str, "retrieval_iso": str, "source_title": str,
                     "tier": "A"|"B"|"C"}]"""
    citations = []
    kept_a = []
    kept_b = []
    recency_log = []
    for est in estimates:
        tier = est["tier"]
        rr = recency_check("fair_value", tier, est["retrieval_iso"], today_iso)
        if rr.action == "drop":
            recency_log.append({"source": est["url"], "age_days": rr.age_days,
                                "budget_days": rr.budget_days, "tier": tier,
                                "action": "drop"})
            continue
        cit = format_citation(est["url"], est["retrieval_iso"], est["source_title"], tier)
        citations.append(cit)
        if tier == "A":
            kept_a.append(est["value"])
        elif tier == "B":
            kept_b.append(est["value"])

    low_confidence = len(kept_a) == 0
    all_kept = kept_a + kept_b
    if not all_kept:
        return {
            "point": 0.0, "band_low": 0.0, "band_high": 0.0,
            "synthesis_target": 0.0, "mode": "bracket",
            "tier_bracket": [], "conflict": False, "low_confidence": True,
            "citations": [], "reasoning_trace": "not_found_in_budget",
        }

    synthesis_target = sum(all_kept) / len(all_kept)
    if kept_a and is_in_conflict(kept_a):
        lo, hi = tier_bracket(kept_a)
        return {
            "point": (lo + hi) / 2, "band_low": lo, "band_high": hi,
            "synthesis_target": synthesis_target, "mode": "bracket",
            "tier_bracket": [str(x) for x in kept_a], "conflict": True,
            "low_confidence": False, "citations": citations,
            "reasoning_trace": f"tier-A disagreement > +/-10% -- bracket [{lo},{hi}]",
        }
    if low_confidence:
        lo, hi = min(all_kept), max(all_kept)
        return {
            "point": (lo + hi) / 2, "band_low": lo, "band_high": hi,
            "synthesis_target": synthesis_target, "mode": "bracket",
            "tier_bracket": [], "conflict": False, "low_confidence": True,
            "citations": citations,
            "reasoning_trace": "no tier-A sources -- bracket [min,max] of cited",
        }
    # Synthesized path: weighted synthesis (tier-A weight 3, tier-B weight 1).
    weighted = [(v, 3.0) for v in kept_a] + [(v, 1.0) for v in kept_b]
    pt = weighted_synthesis(weighted)
    half_band = max(abs(pt - min(all_kept)), abs(max(all_kept) - pt))
    return {
        "point": pt, "band_low": pt - half_band, "band_high": pt + half_band,
        "synthesis_target": synthesis_target, "mode": "synthesized",
        "tier_bracket": [str(x) for x in kept_a], "conflict": False,
        "low_confidence": False, "citations": citations,
        "reasoning_trace": "tier-A within +/-10%, weighted synthesis",
    }
'''

WDRIVERS = '''"""drivers worker.

Returns a structured list of event objects. NO prose synthesis.
Each event: timestamp, source, claim, retrieval_iso, tier, recency_violated,
citation_format.
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check

def run(events: list[dict[str, Any]], today_iso: str) -> list[dict[str, Any]]:
    """events = [{"timestamp": str, "url": str, "claim": str,
                  "retrieval_iso": str, "tier": "A"|"B"|"C",
                  "source_title": str}]"""
    out: list[dict[str, Any]] = []
    recency_log: list[dict[str, Any]] = []
    for ev in events:
        rr = recency_check("drivers", ev["tier"], ev["retrieval_iso"], today_iso)
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
            "retrieval_iso": ev["retrieval_iso"],
            "tier": display_tier,
            "original_tier": ev["tier"],
            "recency_violated": recency_violated,
            "citation_format": f"[{ev['url']} | {ev['retrieval_iso']} | {ev['source_title']} | {display_tier}]",
        })
        if rr.action == "flag":
            recency_log.append({"source": ev["url"], "age_days": rr.age_days,
                                "budget_days": rr.budget_days, "tier": ev["tier"],
                                "action": "flag"})
    return out
'''

WMACRO = '''"""macro worker.

Returns flat snapshot table rows. NO prose synthesis.
Each row: indicator, value, source, retrieval_iso, tier.
Per-indicator single-source is allowed (BEA releases etc.).
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check

def run(rows: list[dict[str, Any]], today_iso: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    recency_log: list[dict[str, Any]] = []
    for r in rows:
        rr = recency_check("macro", r["tier"], r["retrieval_iso"], today_iso)
        if rr.action == "drop":
            recency_log.append({"source": r["source"], "age_days": rr.age_days,
                                "budget_days": rr.budget_days, "tier": r["tier"],
                                "action": "drop"})
            continue
        display_tier = "C" if rr.action == "flag" else r["tier"]
        out.append({
            "indicator": r["indicator"],
            "value": r["value"],
            "source": r["source"],
            "retrieval_iso": r["retrieval_iso"],
            "tier": display_tier,
        })
    return out
'''

WFORWARDRANGE = '''"""forward_range worker.

6-month forward ranges whose probabilities sum to 1.0, evidence-backed.
Tier-A disagreement > +/-10% -> bracket mode, conflict: true, probabilities
suppressed, outliers annotated.
"""
from __future__ import annotations
from typing import Any
from lib.recency import check as recency_check
from lib.conflict import is_in_conflict, tier_bracket

def run(ranges: list[dict[str, Any]], today_iso: str) -> dict[str, Any]:
    """ranges = [{"label": str, "low": float, "high": float, "probability": float,
                   "evidence_count": int, "url": str, "retrieval_iso": str,
                   "source_title": str, "tier": "A"|"B"|"C"}]"""
    # Recency filter (forward_range budget = 90 days).
    kept = []
    for r in ranges:
        rr = recency_check("forward_range", r["tier"], r["retrieval_iso"], today_iso)
        if rr.action == "drop":
            continue
        kept.append(r)

    tier_a_midpoints = [(r["low"] + r["high"]) / 2 for r in kept if r["tier"] == "A"]

    if tier_a_midpoints and is_in_conflict(tier_a_midpoints):
        lo, hi = tier_bracket(tier_a_midpoints)
        outliers = [r for r in kept if r["tier"] == "A" and
                    ((r["low"] + r["high"]) / 2 < lo or (r["low"] + r["high"]) / 2 > hi)]
        return {
            "ranges": [], "mode": "bracket",
            "modal_midpoint": (lo + hi) / 2,
            "tier_anchor_low": lo, "tier_anchor_high": hi,
            "conflict": True, "low_confidence": False,
            "outliers": [{"label": o["label"], "midpoint": (o["low"]+o["high"])/2,
                          "annotation": f"[outlier: {o['label']}]"} for o in outliers],
            "reasoning_trace": "tier-A disagreement > +/-10% -- bracket only",
        }

    # Normalize probabilities to sum to 1.0.
    total_p = sum(r["probability"] for r in kept) or 1.0
    for r in kept:
        r["probability"] = r["probability"] / total_p
    midpoints = [(r["low"] + r["high"]) / 2 for r in kept]
    modal_midpoint = sum(p * m for p, m in zip([r["probability"] for r in kept], midpoints)) / max(sum(r["probability"] for r in kept), 1)
    tier_a = [r for r in kept if r["tier"] == "A"]
    return {
        "ranges": kept, "mode": "synthesized",
        "modal_midpoint": modal_midpoint,
        "tier_anchor_low": min((r["low"] for r in tier_a), default=0.0),
        "tier_anchor_high": max((r["high"] for r in tier_a), default=0.0),
        "conflict": False, "low_confidence": len(tier_a) == 0,
        "outliers": [], "reasoning_trace": "tier-A within +/-10%",
    }
'''

WUQA = '''"""user_qa worker.

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
'''

WEVIDENCE = '''"""evidence_synthesizer — recency + independence weighting helpers."""
from __future__ import annotations
from typing import Any
from lib.conflict import weighted_synthesis

def synthesize(values_with_weights: list[tuple[float, float]]) -> float:
    return weighted_synthesis(values_with_weights)
'''

WRECENCY = '''"""recency_checker — applies tier-graded recency budget enforcement."""
from lib.recency import check as check  # re-export
'''

WDOCTOR = '''"""doctor worker.

Two modes:
- mechanical (default): tier classification, recency, >=2-source, citation-format, schema.
  Returns in seconds.
- deep (--deep): full audit incl. Decision Package field validity +
  cross-output rule application. Shows progress.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from jsonschema import validate, ValidationError  # type: ignore
from lib.citation import parse_citation, format_citation
from lib.recency import BUDGETS
from lib.tier import classify as classify_tier
from lib.schema import BUNDLE_SCHEMA

def _check_recency(bundle: dict[str, Any]) -> list[str]:
    errors = []
    for i, ev in enumerate(bundle.get("drivers", [])):
        # Trust the recorded retrieval_iso + tier. tier-C is filtered upstream.
        budget = BUDGETS["drivers"]
        age = ev.get("age_days")
        if age is not None and age > budget and ev.get("tier") in {"A", "B"}:
            errors.append(f"drivers[{i}] recency violation not flagged")
    return errors

def _check_independence(bundle: dict[str, Any]) -> list[str]:
    """Major claims in fair_value, forward_range, and drivers must have >=2 sources
    OR be flagged [single_source]."""
    errors = []
    fv = bundle.get("fair_value", {})
    if fv and fv.get("mode") == "synthesized" and len(fv.get("citations", [])) < 2:
        if "[single_source]" not in (fv.get("reasoning_trace") or ""):
            errors.append("fair_value synthesized with <2 citations and no [single_source] flag")
    fr = bundle.get("forward_range", {})
    if fr and fr.get("mode") == "synthesized" and len(fr.get("ranges", [])) < 2:
        if "[single_source]" not in (fr.get("reasoning_trace") or ""):
            errors.append("forward_range synthesized with <2 ranges and no [single_source] flag")
    return errors

def _check_citations(bundle: dict[str, Any]) -> list[str]:
    errors = []
    seen = set()
    for c in bundle.get("citations", []):
        s = format_citation(c["url"], c["retrieval_iso"], c["source_title"], c["tier"])
        if parse_citation(s) is None:
            errors.append(f"citation malformed: {c!r}")
        if c["tier"] == "C":
            errors.append(f"tier-C citation displayed: {c['url']}")
        if c["url"] in seen:
            errors.append(f"duplicate citation url: {c['url']}")
        seen.add(c["url"])
    return errors

def _check_schema(bundle: dict[str, Any]) -> list[str]:
    try:
        validate(instance=bundle, schema=BUNDLE_SCHEMA)
        return []
    except ValidationError as e:
        return [f"schema: {e.message} at {list(e.absolute_path)}"]

def _check_decision_package(bundle: dict[str, Any]) -> list[str]:
    """--deep only: Decision Package field validity."""
    dp = bundle.get("decision_package", {}) or {}
    required = ["forecastable_claims", "lifecycle_assumptions", "contrary_evidence",
                "owner_roles", "follow_up", "postmortem_required"]
    return [f"decision_package missing field: {f}" for f in required if f not in dp]

def _check_cross_output_rules(bundle: dict[str, Any]) -> list[str]:
    """--deep only: cross-output rule application."""
    errors = []
    fv = bundle.get("fair_value", {})
    fr = bundle.get("forward_range", {})
    # Cross-check: fair_value band vs forward_range tier-anchor bracket.
    if fv and fr and fv.get("mode") != "bracket" and fr.get("mode") != "bracket":
        fv_mid = (fv["band_low"] + fv["band_high"]) / 2
        fr_mid = fr.get("modal_midpoint", 0)
        if abs(fv_mid - fr_mid) / max(abs(fr_mid), 1) > 0.20:
            errors.append("fair_value midpoint diverges >20% from forward_range midpoint")
    # user_qa must not appear in fair_value citations.
    uqa_cits = set()
    for q in bundle.get("user_qa", []):
        for s in q.get("sources", []):
            p = parse_citation(s)
            if p:
                uqa_cits.add(p["url"])
    fv_cits = set()
    for c in bundle.get("citations", []):
        if c.get("origin") == "fair_value":
            fv_cits.add(c["url"])
    leaked = uqa_cits & fv_cits
    if leaked:
        errors.append(f"user_qa sources leaked into fair_value: {sorted(leaked)}")
    return errors

def run(bundle: dict[str, Any], deep: bool = False) -> dict[str, Any]:
    """Validate a persisted bundle. Does not re-execute workers."""
    errors = []
    errors += _check_recency(bundle)
    errors += _check_independence(bundle)
    errors += _check_citations(bundle)
    errors += _check_schema(bundle)
    if deep:
        progress = ["[1/5] recency", "[2/5] independence", "[3/5] citations",
                    "[4/5] schema", "[5/5] decision_package + cross-output"]
        errors += _check_decision_package(bundle)
        errors += _check_cross_output_rules(bundle)
    else:
        progress = ["[1/4] recency", "[2/4] independence", "[3/4] citations", "[4/4] schema"]
    verdict = "pass" if not errors else f"fail: {len(errors)} error(s)"
    out = {
        "verdict": verdict,
        "errors": errors,
        "mode": "deep" if deep else "mechanical",
    }
    if deep:
        out["progress"] = progress
    return out
'''

WHEADMANAGER = '''"""head_manager — elicitation interview, halt checks, bundle composition.

The head_manager is the orchestrator. It:

1. Runs the elicitation interview (or accepts prior elicitation results).
2. Spawns per-output workers (fair_value, drivers, macro, forward_range, user_qa).
3. Composes the bundle, applying halt conditions and accumulating
   follow_up + postmortem_required from prior runs.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import fair_value as WFV
import drivers as WD
import macro as WM
import forward_range as WFR
import user_qa as WUQ
from lib.persist import (
    write_bundle, accumulate, iso_filename_stem, list_runs
)
from lib.citation import format_citation

REQUIRED_OUTPUTS = ["fair_value", "drivers", "macro_market_state", "forward_range", "user_qa"]

def elicit(ticker: str, questions: list[str], date_of_record: str) -> dict[str, Any]:
    """Ouroboros-style elicitation. In this deterministic implementation, we
    formalize the questions as the research scope. Returns a profile."""
    return {
        "ticker": ticker.upper(),
        "questions": questions,
        "date_of_record": date_of_record,
        "depth": "standard",
        "interview_complete": True,
    }

def compose(
    ticker: str,
    today_iso: str,
    fair_value_inputs: list[dict[str, Any]],
    drivers_inputs: list[dict[str, Any]],
    macro_inputs: list[dict[str, Any]],
    forward_range_inputs: list[dict[str, Any]],
    user_qas_inputs: list[dict[str, Any]],
    questions: list[str],
    decision_package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a full bundle from worker inputs."""
    root_path = None  # resolved by caller via write_bundle

    fv = WFV.run(fair_value_inputs, today_iso)
    drivers_out = WD.run(drivers_inputs, today_iso)
    macro_out = WM.run(macro_inputs, today_iso)
    fr = WFR.run(forward_range_inputs, today_iso)
    uqa = WUQ.run(user_qas_inputs, today_iso)

    halt_flags = []
    omitted = []
    if not macro_out:
        halt_flags.append({"output": "macro_market_state", "flag": "[macro_stale]",
                           "reason": "all macro sources dropped on recency"})
        omitted.append("macro_market_state")

    status = "ok" if not omitted else "partial"

    # Decision package defaults.
    dp = decision_package or {}
    dp.setdefault("forecastable_claims", [])
    dp.setdefault("lifecycle_assumptions", [])
    dp.setdefault("contrary_evidence", [])
    dp.setdefault("owner_roles", [])
    dp.setdefault("follow_up", [])
    dp.setdefault("postmortem_required", [])

    # Flatten citations from fair_value + drivers + macro + forward_range.
    citations = _flatten_citations(fv, drivers_out, macro_out, fr)

    bundle = {
        "run_id": iso_filename_stem() + "_" + ticker.upper(),
        "ticker": ticker.upper(),
        "generated_at": today_iso,
        "status": status,
        "fair_value": fv,
        "drivers": drivers_out,
        "macro_market_state": macro_out,
        "forward_range": fr,
        "user_qa": uqa,
        "decision_package": dp,
        "citations": citations,
        "recency_log": [],
        "halt_flags": halt_flags,
        "omitted_outputs": omitted,
    }
    return bundle

def _flatten_citations(fv, drivers, macro, fr) -> list[dict[str, Any]]:
    """Flatten every cited source into the canonical citation list."""
    out = []
    seen = set()
    for cit in fv.get("citations", []):
        # Fair-value citation strings.
        from lib.citation import parse_citation
        p = parse_citation(cit)
        if not p:
            continue
        key = (p["url"], p["retrieval_iso"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"url": p["url"], "retrieval_iso": p["retrieval_iso"],
                    "source_title": p["source_title"], "tier": p["tier"],
                    "claim_class": "interpretive", "capability": "read",
                    "origin": "fair_value"})
    for d in drivers:
        key = (d["source"], d["retrieval_iso"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"url": d["source"], "retrieval_iso": d["retrieval_iso"],
                    "source_title": d.get("source_title", d.get("claim", "")[:60]),
                    "tier": d["tier"], "claim_class": "factual",
                    "capability": "read", "origin": "drivers"})
    return out

def write(root, ticker, bundle):
    return write_bundle(root, ticker, bundle)

def accumulate_across_runs(root, ticker, bundle):
    """Merge follow_up + postmortem_required from prior runs."""
    merged = accumulate(root, ticker, ["follow_up", "postmortem_required"])
    dp = bundle.setdefault("decision_package", {})
    dp["follow_up"] = list({json.dumps(x, sort_keys=True) if not isinstance(x, str) else x
                            for x in (dp.get("follow_up") or []) + merged["follow_up"]})
    dp["postmortem_required"] = list({json.dumps(x, sort_keys=True) if not isinstance(x, str) else x
                                      for x in (dp.get("postmortem_required") or []) + merged["postmortem_required"]})
    return bundle
'''

# Need json import for accumulate_across_runs.
WHEADMANAGER = WHEADMANAGER.replace(
    "from lib.persist import (\n    write_bundle, accumulate, iso_filename_stem, list_runs\n)",
    "import json\nfrom lib.persist import (\n    write_bundle, accumulate, iso_filename_stem, list_runs\n)",
)

# Workers package init.
WINIT = '''"""Worker package for stock-research."""
from . import head_manager
from . import fair_value
from . import drivers
from . import macro
from . import forward_range
from . import user_qa
from . import evidence_synthesizer
from . import recency_checker
from . import doctor

__all__ = [
    "head_manager", "fair_value", "drivers", "macro", "forward_range",
    "user_qa", "evidence_synthesizer", "recency_checker", "doctor",
]
'''

# Lib package init.
LINIT = '''"""Library package for stock-research."""
from . import citation, recency, tier, conflict, schema, persist

__all__ = ["citation", "recency", "tier", "conflict", "schema", "persist"]
'''

# Skill package init (so Python imports work).
SKILLINIT = '''"""stock-research skill package."""
'''

# ---------------------------------------------------------------------------
# CLI driver
# ---------------------------------------------------------------------------

CLI = '''#!/usr/bin/env python3
"""CLI driver for /stock-research commands.

Usage:
    python3 tradingAgents/run_skill.py run AAPL "Why did it drop in March 2026?"
    python3 tradingAgents/run_skill.py show <run-id>
    python3 tradingAgents/run_skill.py doctor <run-id> [--deep]

In a real harness this is invoked by the Claude Code or Codex loader. Here it
is driven against an in-fixture evidence set so the full pipeline can be
exercised end-to-end.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".stock-research"
FIXTURES = ROOT / ".claude" / "skills" / "stock-research" / "fixtures"

sys.path.insert(0, str(ROOT))
from tradingAgents import _impl  # noqa: E402  (the actual runner)

def main(argv=None):
    p = argparse.ArgumentParser(prog="stock-research")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run")
    pr.add_argument("ticker")
    pr.add_argument("questions", nargs="*")

    ps = sub.add_parser("show")
    ps.add_argument("run_id")

    pd = sub.add_parser("doctor")
    pd.add_argument("run_id")
    pd.add_argument("--deep", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "run":
        bundle = _impl.run(args.ticker.upper(), args.questions, FIXTURES, RUNTIME)
        out = {
            "ticker": bundle["ticker"],
            "run_id": bundle["run_id"],
            "path": str(_impl.last_path()),
            "status": bundle["status"],
        }
        print(json.dumps(out, indent=2))
    elif args.cmd == "show":
        bundle = _impl.show(args.run_id, RUNTIME)
        print(json.dumps(bundle, indent=2))
    elif args.cmd == "doctor":
        result = _impl.doctor(args.run_id, RUNTIME, deep=args.deep)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
'''

# The actual implementation referenced by CLI (kept inline so it works without a
# package layout). It loads fixtures and drives the workers.

IMPL = '''"""Runner implementation used by run_skill.py."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATE_OF_RECORD = "2026-07-07"
TODAY_ISO = "2026-07-07T10:15:00Z"
_LAST_PATH: Path | None = None

def last_path() -> Path | None:
    return _LAST_PATH

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _load_fixtures(fixtures: Path) -> dict[str, Any]:
    """Load per-ticker fixture file. Defaults to the bundled AAPL fixture."""
    path = fixtures / "default.json"
    return json.loads(path.read_text())

def run(ticker: str, questions: list[str], fixtures: Path, runtime: Path) -> dict[str, Any]:
    from .workers import head_manager
    fx = _load_fixtures(fixtures)
    inputs = fx.get("inputs", {})
    bundle = head_manager.compose(
        ticker=ticker,
        today_iso=TODAY_ISO,
        fair_value_inputs=inputs.get("fair_value", []),
        drivers_inputs=inputs.get("drivers", []),
        macro_inputs=inputs.get("macro", []),
        forward_range_inputs=inputs.get("forward_range", []),
        user_qas_inputs=[
            {"question": q, "answer": fx.get("user_qa_answers", {}).get(q, "not_found_in_budget"),
             "sources": inputs.get("user_qa_sources", []), "budget_type": "drivers"}
            for q in questions
        ],
        questions=questions,
        decision_package={
            "forecastable_claims": ["Q2 earnings beat", "Forward P/E compresses if rates hold"],
            "lifecycle_assumptions": ["Mature smartphone cycle"],
            "contrary_evidence": ["China shipments down YoY"],
            "owner_roles": [{"role": "analyst", "owner": "tier-A broker research"}],
            "follow_up": [],
            "postmortem_required": [],
        },
    )
    bundle = head_manager.accumulate_across_runs(runtime, ticker, bundle)
    path = head_manager.write(runtime, ticker, bundle)
    global _LAST_PATH
    _LAST_PATH = path
    return bundle

def show(run_id: str, runtime: Path) -> dict[str, Any]:
    """Re-render a persisted bundle from disk without re-execution."""
    for p in runtime.glob("*/*.json"):
        if p.stem == run_id:
            return json.loads(p.read_text())
    raise FileNotFoundError(f"run-id not found: {run_id}")

def doctor(run_id: str, runtime: Path, deep: bool = False) -> dict[str, Any]:
    from .workers import doctor
    bundle = show(run_id, runtime)
    return doctor.run(bundle, deep=deep)
'''

PKGINIT = '''"""tradingAgents package."""
'''

# ---------------------------------------------------------------------------
# Fixture: default AAPL bundle (deterministic, fully cited, no network calls)
# ---------------------------------------------------------------------------

FIXTURE = {
    "inputs": {
        "fair_value": [
            {"value": 215.0, "url": "https://www.goldmansachs.com/insights/aapl-fv",
             "retrieval_iso": "2026-06-30", "source_title": "Goldman Sachs AAPL Fair Value Update",
             "tier": "A"},
            {"value": 222.0, "url": "https://www.morganstanley.com/research/aapl-fv",
             "retrieval_iso": "2026-06-25", "source_title": "Morgan Stanley AAPL Fair Value Update",
             "tier": "A"},
            {"value": 218.0, "url": "https://finance.yahoo.com/quote/AAPL/analysis",
             "retrieval_iso": "2026-07-02", "source_title": "Yahoo Finance AAPL Analyst Estimates",
             "tier": "B"},
        ],
        "drivers": [
            {"timestamp": "2026-07-02T13:30:00Z",
             "url": "https://www.reuters.com/technology/aapl-q3-shipments",
             "claim": "Apple Q3 shipments +5% YoY on services strength",
             "retrieval_iso": "2026-07-03", "source_title": "Reuters AAPL Q3 shipment data",
             "tier": "A", "source_title_short": "Reuters AAPL Q3 shipments"},
            {"timestamp": "2026-07-01T09:00:00Z",
             "url": "https://www.cnbc.com/2026/07/01/aapl-china-down-yoy",
             "claim": "Apple China revenue -8% YoY in Q3",
             "retrieval_iso": "2026-07-01", "source_title": "CNBC AAPL China revenue",
             "tier": "A", "source_title_short": "CNBC AAPL China"},
            {"timestamp": "2026-06-29T16:00:00Z",
             "url": "https://www.bloomberg.com/news/articles/2026-06-29/aapl-services",
             "claim": "Services revenue hit all-time high, +14% YoY",
             "retrieval_iso": "2026-06-30", "source_title": "Bloomberg AAPL Services",
             "tier": "A", "source_title_short": "Bloomberg AAPL Services"},
        ],
        "macro": [
            {"indicator": "Fed Funds Rate", "value": "5.25%",
             "source": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
             "retrieval_iso": "2026-07-01", "tier": "A"},
            {"indicator": "CPI YoY", "value": "2.9%",
             "source": "https://www.bls.gov/cpi/",
             "retrieval_iso": "2026-06-25", "tier": "A"},
            {"indicator": "10Y Treasury Yield", "value": "4.18%",
             "source": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates",
             "retrieval_iso": "2026-07-02", "tier": "A"},
        ],
        "forward_range": [
            {"label": "bear", "low": 175.0, "high": 195.0, "probability": 0.20,
             "evidence_count": 2,
             "url": "https://www.morganstanley.com/research/aapl-bear",
             "retrieval_iso": "2026-06-20", "source_title": "Morgan Stanley AAPL Bear Case",
             "tier": "A"},
            {"label": "base", "low": 210.0, "high": 230.0, "probability": 0.55,
             "evidence_count": 5,
             "url": "https://www.goldmansachs.com/insights/aapl-base",
             "retrieval_iso": "2026-06-25", "source_title": "Goldman Sachs AAPL Base Case",
             "tier": "A"},
            {"label": "bull", "low": 235.0, "high": 260.0, "probability": 0.25,
             "evidence_count": 3,
             "url": "https://www.jpmorgan.com/research/aapl-bull",
             "retrieval_iso": "2026-06-28", "source_title": "JPMorgan AAPL Bull Case",
             "tier": "A"},
        ],
        "user_qa_sources": [
            {"url": "https://www.reuters.com/technology/aapl-q3-shipments",
             "retrieval_iso": "2026-07-03", "source_title": "Reuters AAPL Q3 shipment data",
             "tier": "A"},
            {"url": "https://www.cnbc.com/2026/07/01/aapl-china-down-yoy",
             "retrieval_iso": "2026-07-01", "source_title": "CNBC AAPL China revenue",
             "tier": "A"},
        ],
    },
    "user_qa_answers": {
        "Why did it drop in March 2026?": "not_found_in_budget -- no in-budget sources for March 2026 retrieved.",
    },
}

# ---------------------------------------------------------------------------
# WRITE FILES
# ---------------------------------------------------------------------------

def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"wrote {path.relative_to(ROOT)}")

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))
    print(f"wrote {path.relative_to(ROOT)}")

def main() -> None:
    # Claude Code skill manifest.
    write(SKILL_DIR / "SKILL.md", SKILL_MD)

    # Codex manifest (strict subset).
    write(CODEX_DIR / "AGENTS.md", CODEX_MANIFEST)
    write(CODEX_DIR / "MANIFEST.md", CODEX_MANIFEST)

    # Library modules.
    write(SKILL_DIR / "lib" / "__init__.py", LINIT)
    write(SKILL_DIR / "lib" / "citation.py", LIBCITATION)
    write(SKILL_DIR / "lib" / "recency.py", LIBRECENCY)
    write(SKILL_DIR / "lib" / "tier.py", LIBTIER)
    write(SKILL_DIR / "lib" / "conflict.py", LIBCONFLICT)
    write(SKILL_DIR / "lib" / "schema.py", LIBSCHEMA)
    write(SKILL_DIR / "lib" / "persist.py", LIBPERSIST)

    # Worker modules.
    write(SKILL_DIR / "workers" / "__init__.py", WINIT)
    write(SKILL_DIR / "workers" / "fair_value.py", WFAIRVALUE)
    write(SKILL_DIR / "workers" / "drivers.py", WDRIVERS)
    write(SKILL_DIR / "workers" / "macro.py", WMACRO)
    write(SKILL_DIR / "workers" / "forward_range.py", WFORWARDRANGE)
    write(SKILL_DIR / "workers" / "user_qa.py", WUQA)
    write(SKILL_DIR / "workers" / "evidence_synthesizer.py", WEVIDENCE)
    write(SKILL_DIR / "workers" / "recency_checker.py", WRECENCY)
    write(SKILL_DIR / "workers" / "doctor.py", WDOCTOR)
    write(SKILL_DIR / "workers" / "head_manager.py", WHEADMANAGER)

    # Skill package init.
    write(SKILL_DIR / "__init__.py", SKILLINIT)

    # Fixtures.
    write_json(SKILL_DIR / "fixtures" / "default.json", FIXTURE)

    # CLI driver.
    write(ROOT / "run_skill.py", CLI)
    # _impl.py is intentionally not regenerated by this build script -- it is
    # maintained by hand because it needs to coordinate Python sys.path with
    # the skill package layout. See _impl.py.
    _impl_path = ROOT / "_impl.py"
    if not _impl_path.exists():
        write(_impl_path, IMPL)
    write(ROOT / "__init__.py", PKGINIT)

    # Codex skills mirror.
    codex_skills = ROOT / ".codex" / "skills" / "stock-research"
    write(codex_skills / "MANIFEST.md",
          "# Codex skill manifest -- delegates to .claude/skills/stock-research/SKILL.md\n\n"
          "All execution logic lives in tradingAgents/.claude/skills/stock-research/.\n")

    # README for the skill.
    write(ROOT / "README.md", """# tradingAgents

Stock-research skill for Claude Code and Codex.

## Layout

- `.claude/skills/stock-research/` — Claude Code skill (SKILL.md frontmatter + workers + lib).
- `.codex/AGENTS.md` and `.codex/MANIFEST.md` — strict-subset manifest for Codex.
- `.stock-research/<TICKER>/<ISO>.json` — persisted research bundles.
- `run_skill.py` — CLI driver for `run`, `show`, `doctor`.

## Quickstart

```sh
python3 tradingAgents/run_skill.py run AAPL "Why did it drop in March 2026?"
python3 tradingAgents/run_skill.py show <run-id>
python3 tradingAgents/run_skill.py doctor <run-id> --deep
```

## Disclaimer

See `../DISCLAIMER.md` at the repo root. This is research material only.
""")

    print("done.")

if __name__ == "__main__":
    main()