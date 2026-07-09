---
name: stock-research
description: |
  Evidence-backed stock research. Takes a ticker + optional research questions
  and emits a table-first research bundle (fair value, drivers, fundamentals,
  macro snapshot, 6-month forward range, user Q&A) with inline citations,
  tier-classified sources (A/B/C), recency budgets, and conflict-resolution
  rules. No investment advice — research only.
metadata:
  version: 1.0.0
  capability: [read, compute, write-confirm]
  claim_class: [factual, interpretive, advisory]
  tier_definitions:
    A: "Peer/primary — broker research, SEC EDGAR/sec-edgar fundamentals, regulator filings, primary newswires, company IR/SEC filings."
    B: "Aggregators — Yahoo Finance, Reuters, MarketWatch, MarketBeat, Bloomberg public mirror."
    C: "Blogs, social media, forums — never displayed as supporting evidence; always suppressed."
  recency_budget_days:
    price: 7
    drivers: 7
    fundamentals: 90
    fair_value: 90
    forward_range: 90
    macro: 30
  citation_format: "[URL | published_iso | source_title | tier]"
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
    - current_price
    - fair_value
    - drivers
    - fundamentals
    - macro_market_state
    - forward_range
    - band_probability_table
    - quality_factors
    - comparative_ranking
    - action_guidance
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

The skill captures the requested research scope, then orchestrates worker
outputs to produce a persisted ResearchBundle.

## Invocation

```
/stock-research AAPL "Why did it drop in March 2026?"
/stock-research show 2026-07-07T10-15-00Z_AAPL
/stock-research doctor 2026-07-07T10-15-00Z_AAPL
```

## Fresh Search Contract

`/stock-research <TICKER>` is a live research command. Every new run must
perform fresh web/source retrieval for that ticker during the current
invocation. Do not use prior `.stock-research/` bundles, analyst scratch files,
fixtures, cached bundle outputs, or another ticker's evidence as support for a
new run.

Allowed reuse is narrow:

- `show` and `doctor` may read persisted bundles because they do not create new
  research.
- `follow_up` and `postmortem_required` may accumulate after the fresh evidence
  bundle is composed.
- Local fixture execution is test-only and must be explicitly labeled as such;
  it is not a valid `/stock-research <TICKER>` run.

For Codex, use built-in web search for current sources. For Claude, the
Claude-only `insane-search@gptaku-plugins` setting may be used. In both hosts,
record `retrieval_iso` for the current run, but do not use it as the date basis
for freshness, ranking, or citation strings. Emit `not_found_in_budget` with
search terms attempted instead of filling gaps from old outputs.

## Evidence Coverage Floor

For each ticker in a live `/stock-research <TICKER>` run, collect and persist an
`evidence_coverage` block before synthesis:

- `domain_count` must be at least 5 distinct news/source domains per ticker.
- `evidence_count` must be at least 10 cited evidence items per ticker.
- Every evidence item must include `url`, `domain`, `title`, `published_iso`,
  `tier`, and a concise `claim`.
- Extract `published_iso` from the source's own displayed publication, release,
  filing, or session-close date. Do not substitute retrieval date.
- If fewer than 5 domains or 10 evidence items are found in budget, emit
  `status: "partial"`, add `[evidence_coverage_shortfall]` to `halt_flags`, and
  record attempted search terms in `not_found_in_budget`.
- Tier-C sources may be collected internally for exploration only, but must not
  count toward `domain_count`, `evidence_count`, or displayed support.

## Companion Skill Bundle

Keep this skill focused on fresh retrieval, evidence coverage, fair value,
drivers, fundamentals, macro state, 6-month forward range, and user Q&A. Do not
inline long decision-quality frameworks here. When the user asks for concrete
reliability, economic moat, structural stability, geopolitical/China risk,
macro sensitivity, DeepSeek/Huawei/YMTC/CXMT exposure, or growth-quality
scoring, load the companion skill:

- `trading-agents:stock-quality-factors`

Use the RALF bundle method:

1. **Route** -- this skill gathers fresh evidence and builds the core bundle.
2. **Attach** -- pass evidence, citations, recency logs, and scenario
   assumptions to `stock-quality-factors`.
3. **Layer** -- the companion skill computes `quality_factors`.
4. **Finalize** -- embed `quality_factors` in the research bundle without
   changing `fair_value`, `forward_range`, or cited source facts.

`quality_factors` must contain:

- `reliability`
- `economic_moat`
- `structural_stability`
- `growth_quality`
- `risk_adjusted_score`
- `indicator_score_table`
- `reference_confidence_table`
- `analysis_confidence`

Each factor must include `score`, `grade`, `sub_scores`, `cited_evidence`,
`negative_evidence`, `reasoning_trace`, and `missing_evidence`. These scores
are decision-quality metadata only; they must not be rendered as buy/sell/hold
investment advice.

## Current Price Via yfinance

For every ticker, attempt current price retrieval with `yfinance` before
price-relative synthesis:

- Use the bundled helper script via uv:
  `uv run python src/skills/stock-research/scripts/get_current_price_yfinance.py MU SNDK 000660.KS`
  from the repository root. The project `pyproject.toml` declares `yfinance`;
  do not install dependencies ad hoc inside the skill run.
- Use the exchange-native ticker when known, e.g. `MU`, `SNDK`, `NVDA`,
  `000660.KS` for SK Hynix.
- Record a `current_price` object with `ticker_used`, `currency`, `price`,
  `price_type`, `market_state`, `asof_iso`, `source`, and `retrieval_iso`.
- Prefer `regularMarketPrice` when the quote timestamp is available and the
  market state is clear. Otherwise use `regularMarketPreviousClose` or the
  latest historical regular-session close from yfinance.
- `asof_iso` must be the quote timestamp or session date supplied by yfinance,
  not a substituted retrieval timestamp.
- If yfinance is unavailable, fails, or lacks a timestamp/session date, set
  `current_price.status: "unavailable"` and omit price-relative returns.
  Continue with absolute fair value and forward-range scenarios.
- Treat yfinance as Tier-B aggregator evidence. Do not use it as Tier-A
  fundamentals support.

Example:

```json
"current_price": {
  "status": "ok",
  "ticker_used": "MU",
  "price": 938.38,
  "currency": "USD",
  "price_type": "regular_market_close",
  "market_state": "closed",
  "asof_iso": "2026-07-07",
  "source": "yfinance",
  "retrieval_iso": "2026-07-08T13:32:32Z"
}
```

## Band Probability Table

In addition to the existing `forward_range` bear/base/bull scenarios, render a
three-row `band_probability_table` for each ticker. This is the reader-facing
probability table.

Required rows:

- `downside_band`
- `neutral_band`
- `upside_band`

Each row must include:

- `band`
- `price_range`
- `probability`
- `scenario_source`: one or more of `bear`, `base`, `bull`
- `rationale`
- `cited_evidence`
- `implied_return_range` when `current_price.status == "ok"`
- `return_risk_ratio` when `current_price.status == "ok"`

Rules:

- Probabilities must sum to 1.0 exactly after rounding adjustment.
- If current price is available, define the three bands relative to current
  price and forward scenarios:
  - `downside_band`: expected 6-month price range below current price by more
    than 10%, or the bearish scenario if all scenarios are above current price.
  - `neutral_band`: expected 6-month price range within -10% to +15% of current
    price, or the central overlap around the base scenario.
  - `upside_band`: expected 6-month price range above current price by more
    than 15%, or the bullish scenario if all scenarios are below current price.
- If current price is unavailable, keep absolute price ranges and omit implied
  returns; do not invent a price anchor.
- The `band_probability_table` may reuse the `forward_range` probabilities but
  must be rendered separately as a table-ready object.
- `return_risk_ratio` must be calculated explicitly from the rendered bands:
  - Use each band's midpoint return:
    `band_midpoint_return = ((price_range_low + price_range_high) / 2 / current_price.price) - 1`.
  - Use probability-weighted upside:
    `sum(max(band_midpoint_return, 0) * probability)`.
  - Use probability-weighted downside risk:
    `sum(abs(min(band_midpoint_return, 0)) * probability)`.
  - `return_risk_ratio = probability_weighted_upside / probability_weighted_downside_risk`.
  - Round to 2 decimals and render as `Nx`; if downside risk is 0, render
    `n/a` with `reason: "downside_risk_zero"`.
- Place the `return_risk_ratio` immediately next to `implied_return_range` in
  reader-facing tables, so the return range and risk-adjusted return ratio can
  be compared directly.

## Comparative Ranking And Action Guidance

When a run includes more than one ticker, produce:

```json
"comparative_ranking": []
```

Each ranking row must include:

- `rank`
- `ticker`
- `risk_adjusted_score`
- `analysis_confidence_score`
- `upside_band_probability`
- `structural_stability_score`
- `growth_quality_score`
- `key_positive`
- `key_risk`
- `ranking_reason`

Ranking method:

- Primary sort: `risk_adjusted_score` descending.
- Tie-breakers in order: `analysis_confidence_score`,
  `upside_band_probability`, `structural_stability_score`, then
  `growth_quality_score`.
- If `analysis_confidence_score < 50`, cap rank at "watchlist" tier even when
  upside probability is high.

Also produce:

```json
"action_guidance": []
```

Allowed action labels:

- `prioritize_deeper_due_diligence`
- `watch_for_pullback_or_confirmation`
- `monitor_key_risk_before_action`
- `avoid_new_commitment_until_evidence_improves`

Rules:

- Action guidance is research workflow guidance, not investment advice.
- Each action must include `ticker`, `label`, `why`, `trigger_to_upgrade`,
  `trigger_to_downgrade`, and `evidence_to_check_next`.
- Never output buy/sell/hold.

## Required Rendered Tables

The final answer for a multi-ticker run must be table-first and include these
tables in this order:

1. **Summary Ranking Table**
   - ticker
   - rank
   - current price
   - fair value band
   - upside band probability
   - risk-adjusted score
   - analysis confidence score
   - recommended research action

2. **Band Probability Table**
   - ticker
   - downside band price range / probability
   - neutral band price range / probability
   - upside band price range / probability
   - implied return ranges when yfinance current price is available
   - return/risk ratio when yfinance current price is available

3. **Indicator Score Table**
   - ticker
   - reliability
   - economic moat
   - structural stability
   - growth quality
   - risk-adjusted score
   - analysis confidence score

4. **Reference Confidence Table**
   - ticker
   - source title
   - domain
   - published date
   - tier
   - reference confidence score
   - confidence grade
   - used in

5. **Action Guidance Table**
   - ticker
   - action label
   - why
   - trigger to upgrade
   - trigger to downgrade
   - evidence to check next

After the tables, write a concise integrated analysis explaining the rank order,
the biggest disagreements in evidence, and the most important next evidence to
verify. Keep the disclaimer short: research only, not investment advice.

## Date Rules

MUST:

- Use `published_iso` as the date basis for citations, recency checks, and
  source ordering.
- Use the source's own publication, release, filing, or session-close date for
  `published_iso`.
- Store `retrieval_iso` separately when useful for audit, but treat it as
  metadata only.
- Require `published_iso` on every source object that participates in
  synthesis.
- If a candidate source has no discoverable publication, release, filing, or
  session-close date, do not cite it and do not use it in synthesis. Record it
  as `missing_published_iso` / `not_found_in_budget` with the attempted URL or
  search term.

MUST NOT:

- Use `retrieval_iso` as the date basis for freshness, recency, or citation
  strings.
- Substitute retrieval date when the publication date is missing.
- Present a source as current unless its `published_iso` is within the
  applicable recency budget.

## Execution Policy

Use hybrid execution. Decompose separable research lanes into multi-agent work
when it improves coverage or speed, such as drivers, macro, filings, peer
checks, and user questions. Keep tightly coupled synthesis local to the head
manager or synthesizer, especially fair value, forward range, conflict
resolution, confidence, bundle schema, and final wording.

Fundamentals claims require Tier-A support from SEC EDGAR or sec-edgar-derived
filing data when available. If EDGAR/sec-edgar support is missing within budget,
flag the gap and avoid presenting Tier-B fundamentals as primary support.
The local helper `lib/sec_edgar.py` wraps the optional
`secedgar` package for 10-K/10-Q URL retrieval; metric extraction can be handled
by the host retrieval/parser layer and passed into the `fundamentals` worker.

Run each live skill invocation from an isolated fresh worktree/session whenever
the host supports it. Treat `.stock-research/`, downloaded SEC filings, and
worker scratch files as temporary by default; remove them at the end of the run
unless the user explicitly asks to save/export. This prevents prior runs and
conversation context from contaminating fresh research.

## Doctrine (read first)

1. **No invented numbers.** Every figure is cited with `[URL | published_iso |
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
8. **Exact close gates only price-relative outputs.** If the latest completed
   regular-session close cannot be cited, omit current-price comparisons,
   upside/downside percentages, and exact-close fields. Do not omit the
   6-month bear/base/bull forward ranges solely because the close is missing.
9. **6-month forward range is scenario synthesis.** Always render exactly
   three numeric scenarios (`bear`, `base`, `bull`) when at least two
   independent in-budget Tier-A/B sources support valuation, estimates,
   analyst targets, guidance, or explicit scenario assumptions. Probabilities
   are judgmental synthesis by the model, but each numeric range and rationale
   must be tied to cited, dated evidence. Probabilities must sum to 1.0.
10. **No fake precision from missing anchors.** When exact close is missing,
   the scenario table may still show absolute future price ranges, but it must
   not show implied return percentages or claim the ranges are anchored to the
   last close.

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
- `fundamentals` -- SEC EDGAR/sec-edgar filing-derived rows, metrics, filing
  type, accession, period, citation, and recency status.
- `macro` -- flat snapshot table rows, no prose.
- `forward_range` -- exactly three 6-month bear/base/bull ranges with
  probabilities summing to 1.0, evidence-backed; independent from exact-close
  availability except for return-percentage calculations.
- `band_probability_table` -- reader-facing three-band probability table
  derived from forward-range scenarios and yfinance current price when
  available.
- `stock-quality-factors` companion -- RALF Layer step for reliability,
  economic moat, structural stability, growth quality, and risk-adjusted score.
- `comparative_ranking` / `action_guidance` -- multi-ticker ranking and
  research workflow guidance, using quality factors and band probabilities.
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
