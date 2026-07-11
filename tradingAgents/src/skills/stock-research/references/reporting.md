---
name: integrated-reporting-contract
description: Render stock-research results into a local HTML report. Use after stock-research or whenever the user asks to show, convert, publish, preview, or render a stock research bundle, output, or JSON as HTML. Supports the flow output to JSON bundle to HTML report and should be used as a post-processing skill without modifying the source research skill.
---

# Stock Research HTML Report

Apply this as the mandatory final stage of `stock-research`. Do not modify the
research evidence rules or source facts.

## Workflow

1. Locate the source bundle.
   - Prefer an explicit JSON path from the user.
   - Otherwise use the latest `.stock-research/**/*.json` file in the current
     workspace.
   - If the previous assistant answer has not been saved as JSON yet, first
     create or update a JSON bundle under `.stock-research/` and include the
     displayed tables, citations, halt flags, and current prices.
   - Never create a shortened representative-reference bundle. Copy every
     eligible ticker-specific reference from the research result.

2. Classify the source data into report sections.
   - `metadata`: status, retrieval time, tickers, halt flags.
   - `current_price`: per-ticker quote context sourced from `current_prices`
     when present, or the backward-compatible `current_price` alias for
     single-ticker bundles.
   - `summary_ranking`: comparative ranking, fair value, prices, confidence.
     - Derive fair value bands from `per_ticker_results` or `fair_value` when
       the ranking row omits a duplicate `fair_value_band`.
     - Derive action labels from `action_guidance` when the ranking row omits
       a duplicate `research_action`.
   - `band_probabilities`: downside, neutral, upside bands.
     - Accept both the structured band-object shape and the older
       `[low, high, probability]` tuple shape from bundled research output.
     - Do not assume or rewrite probabilities to a fixed 25/50/25 split;
       render the source probabilities as provided.
   - `indicator_scores`: reliability, moat, stability, growth, risk score.
   - `reference_coverage`: per-ticker count of in-window references, distinct
     domains, and pass/fail status against the coverage floor.
   - `reference_confidence`: cited sources and confidence.
   - `references_by_ticker`: every cited source grouped by the ticker or
     tickers it supports.
   - `action_guidance`: research workflow actions.
   - `analysis`: concise narrative, caveats, and disclaimer.
   - `detailed_analysis`: executive summary, methodology, ticker-by-ticker
     theses and counter-theses, valuation and price-band reasoning, quality
     score explanations, risks, catalysts, evidence gaps, comparative analysis,
     scenario methodology, and limitations.

3. Render HTML with the bundled script:

```bash
python3 src/skills/stock-research/scripts/build_all_artifacts.py bundle.json
```

4. Show the result.
   - The script writes HTML next to the JSON by default.
   - Give the user the generated local path.
   - If a dev server is useful, run `python3 -m http.server` from the report
     directory and provide the localhost URL.

## Output Rules

- Preserve research caveats such as `partial`, `[evidence_coverage_shortfall]`,
  missing Tier-A support, and no-investment-advice disclaimers.
- Do not invent missing fields. If a section is absent, render a visible
  "not found in bundle" note.
- Keep citations as clickable source links when URLs are present.
- Preserve the source probability values in the band table. If the bundle
  uses raw tuples, translate them directly into readable rows instead of
  substituting a synthetic allocation.
- Render current price context explicitly. Prefer the `current_prices` map in
  the bundle; if only `current_price` exists, show that object rather than
  leaving the price column blank.
- Show reference coverage by ticker before the reference tables. The default
  floor is at least 10 cited references, at least 5 distinct domains, and dates
  within 7 days of `retrieval_iso`. This is a hard per-ticker render gate, not
  a whole-report aggregate. Refuse successful rendering when any ticker fails;
  report the exact missing count and return to stock-research retrieval.
- Render all qualifying references for every ticker. Never truncate to a
  representative subset, even when the same references were summarized in the
  conversational answer.
- Show references by ticker. Each ticker section must include direct
  ticker-specific references plus shared market, macro, or sector references
  that were used for the multi-ticker thesis.
- Prefer local-market source mix by ticker. For U.S.-listed tickers such as
  `MU`, `SNDK`, `WDC`, and `LITE`, prioritize U.S. company IR, SEC filings,
  U.S. broker/newswire/market sources, and U.S. analyst coverage. For
  Korea-listed tickers such as `000660.KS` and `402340.KS`, prioritize Korean
  company IR, DART/KRX filings, Korean broker reports, and Korean financial
  media; use global ADR or U.S. market sources as supplemental references and
  label them clearly through `domain` and `used_in`.
- Keep HTML self-contained: inline CSS, no network assets, no JavaScript
  dependency.
- Use readable table-first layout for multi-ticker runs.
- After the tables, render the complete `detailed_analysis` payload. Prefer
  multiple substantive paragraphs and labeled subsections over compressed
  one-line summaries. Preserve lists and nested score explanations.
- For every ticker, explain why each score and scenario differs from peers,
  what evidence supports it, what contrary evidence weakens it, and what event
  would change the assessment. Include citations as clickable links when the
  narrative contains URLs.
- Render each explanation with its own adjacent `Evidence` and, when present,
  `Contrary evidence` list. Each evidence row must show source title,
  publication date, tier, clickable URL, and the exact claim supported. A
  detached references section does not satisfy this rule.
- Require every substantive ticker narrative field and each nested
  quality-factor explanation to use the `text`, `cited_evidence`,
  `contrary_evidence`, and `reasoning_trace` structure defined by
  stock-research. Fail rendering when `text` or `cited_evidence` is empty, or
  when an evidence URL is absent from `reference_confidence_table`.
- Do not manufacture detail. If a required narrative field is absent, show a
  visible `Not found in bundle` message and treat the source bundle as
  incomplete rather than silently producing a thin report.

## Script

`scripts/render_stock_research_html.py` accepts:

```bash
python3 render_stock_research_html.py input.json
python3 render_stock_research_html.py input.json --output report.html
python3 render_stock_research_html.py input.json --strict-coverage
```

Coverage enforcement is strict by default. The renderer exits non-zero and
does not write or replace the HTML report when any ticker has fewer than 10
recent references or fewer than 5 recent distinct domains. `--strict-coverage`
is retained as a compatibility alias.
