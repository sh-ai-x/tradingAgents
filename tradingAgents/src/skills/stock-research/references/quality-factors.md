---
name: integrated-quality-factors-contract
description: |
  Companion skill for stock-research. Adds a decision-quality layer with
  concrete reliability, economic moat, structural stability, growth quality,
  and risk-adjusted scoring. Use together with stock-research when the user
  needs more than fair value and forward range. No investment advice.
metadata:
  version: 1.0.0
  capability: [read, compute]
  claim_class: [factual, interpretive, advisory]
  companion_for:
    - stock-research
  required_inputs:
    - evidence_coverage
    - citations
    - drivers
    - fundamentals
    - macro_market_state
    - fair_value
    - forward_range
  output_key: quality_factors
---

# Stock Quality Factors

This integrated contract keeps the main `stock-research` skill focused on evidence
collection, fair value, fundamentals, macro state, and 6-month scenarios. It
adds a separate decision-quality layer that explains how much confidence to put
in the research and how durable the business setup appears.

## RALF Bundle Method

Apply this contract inside `stock-research` through RALF:

1. **Route** -- `stock-research` performs fresh retrieval, evidence coverage,
   fundamentals, drivers, macro, fair value, and forward range.
2. **Attach** -- pass the resulting evidence objects, citations, source tiers,
   recency logs, and scenario assumptions into the integrated quality-factors
   layer.
3. **Layer** -- produce `quality_factors` without changing `fair_value`,
   `forward_range`, or source facts.
4. **Finalize** -- `stock-research` embeds `quality_factors` in the bundle and
   renders the table-first summary.

Do not use this section as a standalone stock picker. It scores research
quality and business durability; it does not produce investment advice.

## Output Contract

Every output must be written under:

```json
"quality_factors": {
  "reliability": {},
  "economic_moat": {},
  "structural_stability": {},
  "growth_quality": {},
  "risk_adjusted_score": {},
  "indicator_score_table": [],
  "reference_confidence_table": [],
  "analysis_confidence": {}
}
```

Each factor must include:

- `score`: integer 0-100.
- `grade`: one of the grade labels below.
- `sub_scores`: object of named component scores.
- `cited_evidence`: citations in `[URL | published_iso | source_title | tier]`
  format.
- `negative_evidence`: contrary evidence using the same citation format.
- `reasoning_trace`: concise explanation of what drove the score.
- `missing_evidence`: list of required evidence that was not found in budget.

The integrated skill must also produce reader-facing tables:

- `indicator_score_table`: one row per factor and sub-factor.
- `reference_confidence_table`: one row per cited evidence item.
- `analysis_confidence`: aggregate confidence score for the whole analysis.

## Grade Scale

Use these labels consistently:

| Score | Grade | Meaning |
|---:|---|---|
| 85-100 | durable_compounder | Strong evidence, moat, growth, and stability. |
| 70-84 | high_quality_cyclical | High quality but exposed to cycles or valuation. |
| 55-69 | constructive_but_volatile | Upside evidence exists, but risks are material. |
| 40-54 | fragile_opportunity | Opportunity exists, but structure or evidence is weak. |
| 0-39 | low_conviction | Evidence, durability, or risk profile is insufficient. |

## Reliability

Reliability answers: "How much can we trust this research bundle?"

Score exactly these sub-factors:

| Sub-factor | Weight | What to evaluate |
|---|---:|---|
| `source_quality` | 25 | Tier-A share, company/SEC/primary support, broker/primary newswire quality. |
| `source_independence` | 20 | Distinct domains, independent institutions, lack of circular sourcing. |
| `recency_strength` | 20 | Share of core claims inside recency budgets. |
| `claim_consistency` | 20 | Agreement across revenue, EPS, guidance, target, driver, and macro claims. |
| `numeric_traceability` | 15 | Whether key numbers are directly cited and reproducible. |

Rules:

- If `evidence_coverage.domain_count < 5` or `evidence_count < 10`, cap
  reliability at 49 and add `[evidence_coverage_shortfall]`.
- If no Tier-A fundamentals are present, cap `source_quality` at 16 and add
  `[fundamentals_primary_missing]` to `missing_evidence`.
- If latest completed close is unavailable, do not penalize reliability by
  itself; only penalize price-relative claims if they were still made.

## Indicator Score Table

Render every factor score and every sub-score in `indicator_score_table`.

Each row must include:

- `category`: one of `reliability`, `economic_moat`,
  `structural_stability`, `growth_quality`, `risk_adjusted_score`.
- `indicator`
- `score`
- `weight`
- `grade`
- `positive_evidence`
- `negative_evidence`
- `reasoning_trace`

Rules:

- Include a category-level row for each top-level factor.
- Include one row for every sub-factor listed in this skill.
- Scores must match the values inside each factor's `sub_scores`; do not create
  separate unexplained numbers for display.
- If an indicator lacks enough direct evidence, keep the row and add
  `[missing_evidence]` in `reasoning_trace` instead of omitting it.

## Reference Confidence Table

Every source used in synthesis must receive an explicit reference confidence
score. This is separate from source tier. A Tier-B source can score high if it is
recent, direct, numeric, and independent; a Tier-A source can score lower if it
is stale or indirect.

Each `reference_confidence_table` row must include:

- `url`
- `domain`
- `published_iso`
- `source_title`
- `tier`
- `used_in`: array such as `fair_value`, `forward_range`, `drivers`,
  `quality_factors`, `ranking`
- `source_quality_score`
- `recency_score`
- `directness_score`
- `numeric_traceability_score`
- `independence_score`
- `conflict_penalty`
- `reference_confidence_score`
- `confidence_grade`
- `reasoning_trace`

Scoring rubric:

| Component | Range | Guidance |
|---|---:|---|
| `source_quality_score` | 0-25 | Tier-A primary/filing/broker is highest; Tier-B aggregator/news lower; Tier-C is 0 and must not display. |
| `recency_score` | 0-20 | Full score inside recency budget; partial credit if close; 0 when stale and not allowed. |
| `directness_score` | 0-20 | Direct company/filing/analyst claim > reported summary > broad market commentary. |
| `numeric_traceability_score` | 0-20 | Full score when key numeric claim is directly quoted and reproducible. |
| `independence_score` | 0-15 | Higher when the source is independent of other cited claims and not circular. |
| `conflict_penalty` | 0 to -30 | Apply when the source conflicts with higher-tier or more recent evidence. |

`reference_confidence_score` is the sum of the positive components plus
`conflict_penalty`, clipped to 0-100.

Confidence grades:

| Score | Grade |
|---:|---|
| 85-100 | very_high |
| 70-84 | high |
| 55-69 | medium |
| 40-54 | low |
| 0-39 | very_low |

Rules:

- Do not count Tier-C rows in displayed evidence or aggregate confidence.
- Every major numeric claim must have at least one row with
  `numeric_traceability_score >= 12`; otherwise add `[numeric_traceability_gap]`
  to `analysis_confidence.missing_evidence`.
- If a source lacks `published_iso`, it must not appear in this table.

## Analysis Confidence

`analysis_confidence` answers: "How reliable is this entire analysis after
source-level scoring?"

Required fields:

- `score`
- `grade`
- `formula`
- `reference_confidence_average`
- `reliability_score`
- `coverage_score`
- `conflict_penalty`
- `missing_evidence`
- `reasoning_trace`

Formula:

```json
{
  "reference_confidence_average": 0.40,
  "reliability_score": 0.30,
  "coverage_score": 0.20,
  "conflict_penalty": 0.10
}
```

Coverage score:

- 100 when evidence coverage floor is met and Tier-A fundamentals are present.
- 80 when evidence coverage floor is met but Tier-A fundamentals are missing.
- 49 or lower when evidence coverage floor is not met.

Conflict penalty:

- Start at 100.
- Subtract 15 for material conflict between top-tier sources.
- Subtract 10 for stale but displayed Tier-A support.
- Subtract 10 for missing current price when price-relative outputs are shown.
- Subtract 0 for missing current price when price-relative outputs are properly
  omitted.

The final `analysis_confidence.score` must be shown in summary tables and used
by `stock-research` ranking tie-breaks.

## Economic Moat

Economic moat answers: "How defensible is the company's long-term profit pool?"

Score exactly these sub-factors, each 0-100, then average:

- `technology_leadership`
- `switching_cost`
- `scale_advantage`
- `ecosystem_lock_in`
- `pricing_power`
- `customer_stickiness`

Ticker-specific interpretation:

- Memory names such as MU and SNDK should emphasize supply discipline,
  manufacturing scale, HBM/DRAM/NAND technology, long-term customer contracts,
  and pricing power through shortages.
- Accelerator/platform names such as NVDA should emphasize software ecosystem,
  developer lock-in, networking, chip roadmap, hyperscaler adoption, and
  inference/training performance.

## Structural Stability

Structural stability answers: "How exposed is the thesis to external shocks?"

Score exactly these sub-factors, each 0-100 where higher means more stable:

- `geopolitical_resilience`
- `china_competition_resilience`
- `macro_resilience`
- `supply_chain_resilience`
- `regulatory_policy_resilience`
- `cyclicality_resilience`

Required risk checks:

- China competition: DeepSeek, Huawei, YMTC, CXMT, domestic China AI chips,
  domestic memory sourcing, and export-control workarounds where relevant.
- Geopolitics: U.S. export controls, Taiwan/Korea exposure, China demand,
  sanctions, and subsidy dependency.
- Macro: rates, dollar, AI capex cycle, consumer device cycle, enterprise
  spending, energy costs, and credit conditions.
- Policy: antitrust, national-security controls, CHIPS Act or equivalent
  subsidy effects, import/export restrictions.

Never bury a structural risk because the fair-value output is bullish.

## Growth Quality

Growth quality answers: "Is growth durable, profitable, and visible?"

Score exactly these sub-factors, each 0-100, then average:

- `revenue_growth_visibility`
- `margin_expansion_quality`
- `demand_durability`
- `capex_efficiency`
- `estimate_revision_momentum`
- `market_expansion`

Rules:

- Distinguish cyclical price-led growth from unit/share-led growth.
- Treat one-quarter earnings spikes as lower quality unless supported by
  backlog, long-term contracts, secular demand, or repeated estimate revisions.
- Penalize growth quality when growth requires extreme capex with uncertain
  return on invested capital.

## Risk-Adjusted Score

The final score is the weighted average:

```json
{
  "reliability": 0.25,
  "economic_moat": 0.25,
  "structural_stability": 0.25,
  "growth_quality": 0.25
}
```

Rules:

- If `reliability.score < 50`, cap `risk_adjusted_score.score` at 59.
- If `structural_stability.score < 40`, cap `risk_adjusted_score.score` at 64.
- If both `economic_moat.score >= 75` and `growth_quality.score >= 75`, but
  `structural_stability.score < 55`, use grade `high_quality_cyclical` at most.
- Explain caps in `reasoning_trace`.

## Stops

- Do not modify `fair_value`, `forward_range`, or cited source facts.
- Do not score from Tier-C sources.
- Do not invent numeric sub-scores without tying them to cited evidence or
  explicit missing-evidence penalties.
- Do not present `risk_adjusted_score` as a buy/sell/hold rating.
