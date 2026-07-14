---
name: stock-research
description: |
  Run evidence-backed stock research and create JSON, self-contained HTML, and
  verified PDF artifacts in one invocation. Supports one or more tickers,
  valuation, scenarios, integrated quality factors, citations, diagnostics,
  saved-run validation, and complete or halted reports. Research only.
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
    fundamentals: 7
    fair_value: 7
    forward_range: 7
    macro: 7
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

## Required Integrated Contracts

Before every live run, read both reference contracts completely and apply them
as part of this single skill:

- `references/quality-factors.md` — preserve the complete former integrated
  quality-factors scoring, evidence, grade, cap, and output contract.
- `references/reporting.md` — preserve the complete former report coverage,
  narrative, reference, and rendering contract.

These files are references, not separately exposed skills. Their requirements
remain mandatory and must not be replaced by the shorter summary below. When a
rule conflicts, keep the stricter evidence, coverage, narrative, or artifact
validation requirement.

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
- Every counted or displayed evidence item must have `published_iso` inside the
  inclusive 7-day window ending at `retrieval_iso`. This single window applies
  to drivers, fundamentals, fair value, forward range, macro, quality factors,
  ranking, and user Q&A. Older sources do not count and must not be displayed
  or used in synthesis, regardless of tier.
- Every evidence item must include `url`, `domain`, `title`, `published_iso`,
  `tier`, and a concise `claim`.
- Extract `published_iso` from the source's own displayed publication, release,
  filing, or session-close date. Do not substitute retrieval date.
- Do not stop the normal research pass when fewer than 10 eligible items have
  been found. Continue the iterative search procedure below until the floor is
  met or the eligible public source space has been exhaustively searched.
- If exhaustive retrieval still yields fewer than 5 domains or 10 eligible
  items for any ticker, do not finalize, rank, persist, or render that ticker's
  research as a completed run. Continue retrieval through every source lane
  and query expansion. If the public eligible source space is genuinely
  exhausted, emit a halted diagnostic only, add
  `[evidence_coverage_shortfall]`, and record every attempted search term and
  source lane in `not_found_in_budget`. Never backfill with older, duplicated,
  syndicated, undated, or Tier-C sources.

### Per-Ticker Ten-Reference Persistence Gate

The minimum is **10 eligible references for each ticker**, not 10 for the
whole run and not 10 collected only in worker scratch output.

Before synthesis, persistence, ranking, HTML conversion, or final display:

1. Build the final `reference_confidence_table` from the accepted evidence.
2. Attach `ticker` or `tickers` to every reference row. Shared macro evidence
   may list multiple tickers, but it counts once for each explicitly listed
   ticker only.
3. Deduplicate by canonical URL and underlying publication separately for each
   ticker.
4. Recompute the eligible reference count and distinct-domain count from the
   actual persisted `reference_confidence_table`, not from search notes or a
   worker summary.
   `doctor` must fail when a declared `evidence_coverage` count cannot be
   reproduced from those persisted ticker-assigned rows, including halted
   diagnostic bundles.
5. Require at least 10 eligible rows and 5 distinct domains for every ticker.
6. Persist and render all eligible rows used to satisfy the gate. Never replace
   them with a shorter representative-source table or truncate them for
   readability.
7. Run `doctor` against the exact final bundle. A coverage failure is a hard
   completion failure: return the halted diagnostic and resume retrieval; do
   not claim that the research report is complete.

For a five-ticker run, the bundle must therefore contain at least 50
ticker-reference assignments. A shared source can support more than one ticker
only when each assignment is explicit and the claim genuinely applies to each.
- Tier-C sources may be collected internally for exploration only, but must not
  count toward `domain_count`, `evidence_count`, or displayed support.

## Iterative Seven-Day Retrieval

For each ticker, repeat retrieval and date validation until at least 10 eligible
evidence items across at least 5 domains are collected:

1. Search the ticker, company name, exchange-native name, and major products
   with an explicit date range covering `retrieval_iso - 7 days` through
   `retrieval_iso`.
2. Search primary lanes separately: company IR/newsroom, regulator filings,
   exchange disclosures, government releases, and official presentations.
3. Search independent lanes separately: primary newswires, local-market
   financial media, broker research, industry data providers, and reputable
   market aggregators.
4. Expand queries by claim class: earnings, guidance, analyst target,
   valuation, product, customer, capex, supply, pricing, competition, policy,
   macro, and risk.
5. Deduplicate by canonical URL and underlying publication. Syndicated mirrors
   of the same article count as one independent evidence item.
6. Open every candidate and extract the source-displayed `published_iso` before
   counting it. Search-result dates and retrieval timestamps are not valid
   substitutes.
7. Recount eligible items and domains after each pass. Persist
   `search_iterations`, with queries, source lanes, accepted count, rejected
   count, and rejection reasons for every pass.

Do not declare `not_found_in_budget` merely because the first search page or
first query set produced fewer than 10 items. Exhaust the query expansions and
source lanes above first. "Continue until 10" never permits invented,
duplicated, Tier-C, undated, or out-of-window evidence.

## Integrated Quality Factors

Compute quality factors directly inside this skill after the fresh evidence
layer is complete. Score reliability, economic moat, structural stability,
growth quality, and their equal-weight risk-adjusted average from 0-100. Tie
every sub-score to persisted Tier-A/B evidence or an explicit missing-evidence
penalty. Reliability covers source quality, independence, recency, consistency,
and numeric traceability. Moat covers technology, switching cost, scale,
ecosystem, pricing power, and customer stickiness. Stability covers
geopolitics, China competition, macro, supply chain, policy, and cyclicality.
Growth quality covers visibility, margins, demand durability, capex efficiency,
estimate revisions, and market expansion. Never score from Tier C.

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
- Record current prices in a `current_prices` map keyed by ticker. Each entry
  must contain `ticker_used`, `currency`, `price`, `price_type`,
  `market_state`, `asof_iso`, `source`, and `retrieval_iso`.
- For single-ticker bundles, keep `current_price` as a backward-compatible
  alias of the same object. For multi-ticker bundles, `current_prices` is the
  canonical source for the report layer.
- Prefer `regularMarketPrice` when the quote timestamp is available and the
  market state is clear. Otherwise use `regularMarketPreviousClose` or the
  latest historical regular-session close from yfinance.
- `asof_iso` must be the quote timestamp or session date supplied by yfinance,
  not a substituted retrieval timestamp.
- If yfinance is unavailable, fails, or lacks a timestamp/session date, set
  `current_prices[ticker].status: "unavailable"` and omit price-relative
  returns for that ticker. Continue with absolute fair value and forward-range
  scenarios.
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

## Price-Band Probability Table

In addition to the existing `forward_range` bear/base/bull scenarios, render a
reader-facing `band_probability_table` that answers: "What is the probability
that the 6-month price lands in each displayed price interval?" This is a
distribution across price intervals, not an "upside probability" score.

Render at least three ordered rows named `price_band_1`, `price_band_2`, and
`price_band_3`. Add more rows only when the evidence supports useful additional
resolution.

Probability assignment must be model-driven, not template-driven. Use the
LLM to infer each band's probability from the cited evidence, scenario
dispersion, source quality, and recency. Do not default to a preset split such
as `25/50/25` unless that exact allocation is the direct result of the evidence
and the model's synthesis. If the evidence is weak or ambiguous, lower the
confidence in the explanation instead of forcing a canned distribution.

Each row must include:

- `band_id`
- `price_range`
- `probability`
- `scenario_source`: one or more of `bear`, `base`, `bull`
- `rationale`
- `cited_evidence`
- `implied_return_range` when `current_price.status == "ok"`
- `return_risk_ratio` when `current_price.status == "ok"`

Rules:

- Price bands must be ordered from lowest to highest, mutually exclusive, and
  collectively cover the full rendered 6-month scenario range. Adjacent bands
  may share a boundary only when interval inclusivity is explicitly recorded;
  otherwise use non-overlapping boundaries.
- Probabilities across all displayed price bands must sum to 1.0 exactly after
  rounding adjustment.
- Derive boundaries from the evidence-backed bear/base/bull ranges, resolving
  overlaps into explicit price intervals. Do not force boundaries at arbitrary
  current-price return thresholds such as -10% or +15%.
- `probability` means the probability of finishing inside that exact
  `price_range`. Never label it or reuse it as the probability that the stock
  rises.
- Current price is an annotation only. When available, calculate each band's
  `implied_return_range`; it must not determine the band identity or ranking.
- If current price is unavailable, keep absolute price ranges and omit implied
  returns; do not invent a price anchor.
- The table may start from `forward_range` scenario probabilities, but any
  overlapping scenario ranges must be redistributed into non-overlapping price
  bands with the allocation method stated in `reasoning_trace`.
- The allocation method itself must be explained from the evidence, not from a
  fixed formula. The model should state why the probability mass lands where it
  does, using the support, contradictions, and scenario geometry in the current
  bundle.
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
- `fair_value_band` or enough per-ticker fair-value payload for the report
  layer to derive it from `per_ticker_results` / `fair_value`
- `risk_adjusted_score`
- `analysis_confidence_score`
- `structural_stability_score`
- `growth_quality_score`
- `key_positive`
- `key_risk`
- `ranking_reason`

Ranking method:

- Primary sort: `risk_adjusted_score` descending.
- Tie-breakers in order: `analysis_confidence_score`,
  `structural_stability_score`, then `growth_quality_score`.
- If `analysis_confidence_score < 50`, cap rank at "watchlist" tier regardless
  of the shape of the price-band distribution.

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
   - risk-adjusted score
   - analysis confidence score
   - recommended research action

2. **Price-Band Probability Table**
   - ticker
   - ordered, non-overlapping price range
   - probability of finishing in that exact range
   - scenario source and rationale
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
   - render every eligible reference that satisfies the per-ticker coverage
     gate; never show only representative references

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

## Detailed HTML Narrative Payload

When the bundle may be rendered as HTML or PDF, persist a
`detailed_analysis` object. Do not rely on the conversational answer as the
only source of explanation. Write complete, evidence-linked prose rather than
one-line descriptions.

Required fields:

- `executive_summary`: explain the market regime, the central comparative
  conclusion, and the most important limitations in at least three substantive
  paragraphs.
- `methodology`: explain the seven-day evidence window, tier policy,
  independence and deduplication rules, fair-value method, scenario-probability
  method, scoring method, ranking tie-breaks, and current-price limitations.
- `ticker_analyses`: one object per ticker containing:
  - `business_and_market_context`
  - `current_setup`
  - `bull_case`
  - `base_case`
  - `bear_case`
  - `fair_value_reasoning`
  - `price_band_reasoning`
  - `quality_factor_reasoning` with separate explanations for reliability,
    economic moat, structural stability, growth quality, risk-adjusted score,
    and analysis confidence
  - `positive_evidence`
  - `negative_and_contrary_evidence`
  - `key_risks`
  - `catalysts_and_checkpoints`
  - `evidence_gaps`
  - `research_action_reasoning`
- `comparative_analysis`: explain rank order, trade-offs, evidence conflicts,
  and why similarly scored companies are ordered differently.
- `scenario_methodology`: explain how overlapping bear/base/bull scenarios were
  converted into mutually exclusive bands and how probabilities were assigned.
- `limitations`: enumerate coverage, primary-fundamentals, current-price,
  currency, target-price, and model-risk limitations that apply.

Every ticker section must cite the relevant persisted references by URL or
stable reference identifier. Aim for decision-useful detail: explain causal
links and counterarguments, not merely repeat table cells. Never pad with
generic company descriptions or invent unsupported facts.

### Evidence Attached to Every Explanation

Store every substantive narrative block as an evidence-bearing object:

```json
{
  "text": "Detailed explanation of the claim, causal link, and uncertainty.",
  "cited_evidence": [
    {
      "url": "https://...",
      "published_iso": "YYYY-MM-DD",
      "source_title": "...",
      "tier": "A",
      "claim_supported": "The exact portion of the explanation this supports"
    }
  ],
  "contrary_evidence": [],
  "reasoning_trace": "How the evidence leads to the interpretation"
}
```

Apply this structure to business context, current setup, bull/base/bear cases,
fair value, price bands, every quality-factor explanation, positive evidence,
negative evidence, risks, catalysts, evidence gaps, research action,
comparative conclusions, and scenario methodology. Method descriptions that
state only the skill's rules may cite `method_rule` instead of an external URL.

Rules:

- Place evidence immediately next to the explanation it supports; do not rely
  on a detached reference list alone.
- Include `claim_supported` so the reader can see why the source is attached.
- Use only rows already present in the final `reference_confidence_table`.
- Include contrary evidence beside conclusions whenever it exists.
- A substantive explanation with no `cited_evidence` must be labeled
  `[unsupported_explanation]` and blocks final HTML/PDF completion.
- Never attach a source merely because it mentions the company; it must support
  the specific explanatory claim.

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
- Present or synthesize from a source unless its `published_iso` falls inside
  the inclusive 7-day window ending at `retrieval_iso`.

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
2. **The 7-day publication window is hard.** Any source published before
   `retrieval_iso - 7 days`, after `retrieval_iso`, or without a discoverable
   source-displayed date is dropped from synthesis and display and logged in
   `recency_log`. Tier-A status does not override this rule.
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
- `band_probability_table` -- reader-facing distribution across ordered,
  non-overlapping 6-month price intervals; current price affects return
  annotations only.
- quality-factors layer -- RALF step for reliability, economic moat,
  structural stability, growth quality, and risk-adjusted score.
- `comparative_ranking` / `action_guidance` -- multi-ticker ranking and
  research workflow guidance, using quality factors and band probabilities.
- `user_qa` -- answers to user research questions, own confidence.
- `evidence_synthesizer` -- recency + independence weighting, conflict detection.
- `recency_checker` -- applies tier-graded recency budget enforcement.
- `doctor` -- mechanical (default, <= seconds) and `--deep` (full audit) modes.

## Halt Conditions

If any worker returns `halted` with a reason unrelated to reference coverage,
the bundle is emitted as `status: "partial"` with the dropped outputs listed in
`omitted_outputs`. Reference coverage is stricter: fewer than 10 eligible
persisted references or 5 domains for any ticker blocks completed synthesis,
ranking, and report rendering for that ticker. Emit a halted coverage
diagnostic and continue retrieval when possible.

## Doctor

`/stock-research doctor <run-id>` resolves the run file
(`.stock-research/<TICKER>/<ISO>.json`) and validates:

- Mechanical (default, <= seconds): tier classification present, every cited
  source inside the inclusive 7-day publication window, at least 10 eligible
  references and 5 domains per ticker, >=2 sources per major claim, citation
  format, and schema.
- `--deep`: above + Decision Package field validity + cross-output rule
  application. Shows progress as it walks each rule.

Doctor never re-executes workers. It reads the persisted bundle only.

Doctor must support both legacy single-ticker bundles and current multi-ticker
bundles. Resolve run IDs from both `tradingAgents/.stock-research/` and the
workspace-level `.stock-research/`. For multi-ticker bundles, validate the
persisted reference table, per-ticker coverage, publication dates, ticker
assignments, Tier-C suppression, schema, and probability sums. Do not apply
legacy flat-driver or `decision_package` assumptions to multi-ticker objects.

## Persistence

Every run writes to `.stock-research/<TICKER>/<ISO_DATETIME>.json`. The
ISO datetime uses `:` replaced by `-` for filesystem safety. Stdout shows a
compact summary pointer only. `/stock-research show <run-id>` re-renders from
file. `follow_up` and `postmortem_required` accumulate across runs of the
same ticker -- the head manager reads prior bundles in
`.stock-research/<TICKER>/` and merges them.

## Mandatory Artifact Finalization

Every new research run must finish with JSON, HTML, and PDF. Persist and Doctor
validate the JSON first, including the complete evidence-bearing
`detailed_analysis`. Then run:

```bash
python3 src/skills/stock-research/scripts/build_all_artifacts.py <bundle.json>
```

The internal renderer writes self-contained HTML and Playwright Chromium writes
an A4 PDF. Validate that JSON and HTML are non-empty and the PDF begins with
`%PDF-`. Partial or halted research must still produce a visible diagnostic
HTML/PDF; label uncomputed fields and preserve coverage failures. Never claim
completion unless paths for all three verified artifacts are returned.
