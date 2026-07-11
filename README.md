# tradingAgents

Evidence-backed stock-research plugin for Codex and Claude Code.

`tradingAgents` turns a ticker request into an auditable research bundle. It
retrieves fresh public evidence, validates publication dates, classifies source
quality, checks conflicts, builds valuation and six-month scenarios, scores
research quality and business durability, and renders reader-facing reports.

The project produces research material only. It does not issue buy, sell, or
hold recommendations. Read [DISCLAIMER.md](DISCLAIMER.md) before using an
output for a financial decision.

## Contents

- [Core principles](#core-principles)
- [Plugin skills](#plugin-skills)
- [Installation and updates](#installation-and-updates)
- [Quick start](#quick-start)
- [Research workflow](#research-workflow)
- [Evidence policy](#evidence-policy)
- [Research outputs](#research-outputs)
- [JSON, HTML, and PDF artifacts](#json-html-and-pdf-artifacts)
- [Saved runs and diagnostics](#saved-runs-and-diagnostics)
- [Project layout](#project-layout)
- [Local development](#local-development)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

## Core Principles

The plugin is designed around five constraints:

1. **Fresh retrieval:** a new research request must perform new source
   retrieval. Previous bundles and fixtures cannot support a live run.
2. **Source-backed numbers:** every material figure must be traceable to an
   eligible source. Missing evidence is reported rather than inferred.
3. **Hard recency window:** evidence used in a live bundle must have a
   source-displayed publication, release, filing, or session-close date inside
   the inclusive seven-day window ending at the retrieval time.
4. **Per-ticker coverage:** each ticker must have at least 10 eligible
   references across at least five distinct domains before completed synthesis
   and comparative ranking.
5. **Research, not advice:** workflow guidance is limited to the next research
   action. The plugin never emits `buy`, `sell`, or `hold`.

When evidence is insufficient, the correct result is a partial or halted
diagnostic bundle—not invented values, stale backfill, or a silently empty
report.

## Plugin Skills

The `trading-agents` plugin exposes one integrated skill.

### `trading-agents:stock-research`

Run fresh research for one or more tickers. This is the primary skill and owns:

- current-source retrieval and seven-day date validation
- per-ticker coverage and domain-count gates
- current-price retrieval through yfinance
- drivers, filing-backed fundamentals, and macro context
- fair-value and six-month bear/base/bull scenarios
- mutually exclusive price-band probabilities
- multi-ticker comparison and research workflow guidance
- persistence, saved-run display, and doctor validation

```text
$trading-agents:stock-research MU
$trading-agents:stock-research MU SNDK 000660.KS
```

Natural-language research questions can follow the tickers:

```text
$trading-agents:stock-research MU SNDK "Compare evidence quality, six-month ranges, and key downside risks."
```

### Integrated quality factors

Add the companion decision-quality layer. It scores:

- reliability
- economic moat
- structural stability
- growth quality
- risk-adjusted quality
- individual reference confidence
- aggregate analysis confidence

`stock-research` normally loads this companion automatically for a complete
multi-factor bundle. The companion does not alter fair value, scenario ranges,
or cited facts, and it is not a standalone stock picker.

### Integrated reports

Post-process the newest or explicitly selected research JSON into durable
report artifacts. It preserves completed, partial, halted, coverage-warning,
and missing-evidence states instead of hiding them.

No second skill invocation is required; `stock-research` creates JSON, HTML,
and PDF automatically after research and Doctor validation.

## Installation and Updates

### Requirements

- Codex or Claude Code with plugin/skill support
- Python 3.11 or newer for local helpers
- `uv` for the declared Python environment
- network access for live research
- Playwright Chromium when PDF rendering is enabled

The Python project declares `yfinance>=0.2.65`; live runs must use the bundled
environment rather than installing packages ad hoc.

### Local Codex plugin development

The local marketplace exposes the plugin as:

```text
trading-agents@trading-agents-dev
```

After editing plugin sources, refresh the installed cached plugin:

```sh
cd tradingAgents
./scripts/update-plugin.sh
```

The update script:

1. validates required files and the Codex CLI;
2. adds a temporary cachebuster version;
3. validates the plugin manifest;
4. reinstalls the plugin from the local marketplace;
5. restores the source manifest; and
6. prints the installed version.

Start a new Codex thread after updating. Existing conversations retain the
plugin version loaded when the thread began.

## Quick Start

Run a single-ticker investigation:

```text
$trading-agents:stock-research AAPL "What changed this week?" "What evidence would invalidate the base case?"
```

Run a multi-ticker comparison:

```text
$trading-agents:stock-research MU SNDK NVDA "Compare price ranges, durability, and evidence quality."
```

The same invocation renders the saved result automatically.

Typical outputs are written beneath `.stock-research/`. Runtime bundles and
agent scratch files are local artifacts and should not be committed.

## Research Workflow

### 1. Resolve tickers

Use exchange-native symbols where possible. Examples:

| Company | Symbol |
|---|---|
| Micron | `MU` |
| SanDisk | `SNDK` |
| SK hynix | `000660.KS` |
| SK Square | `402340.KS` |
| Samsung Electronics | `005930.KS` |

### 2. Retrieve current prices

The plugin first attempts the bundled yfinance helper:

```sh
cd tradingAgents
uv run python src/skills/stock-research/scripts/get_current_price_yfinance.py MU SNDK 000660.KS
```

Each quote records the requested ticker, currency, price type, market state,
source timestamp or session date, source, and retrieval time. A multi-ticker
bundle uses `current_prices`; `current_price` remains a single-ticker
compatibility alias.

If a valid timestamp or session date is unavailable, price-relative returns
are omitted. Absolute valuation and scenario ranges may still be produced when
their own evidence is sufficient.

### 3. Search evidence lanes

The live workflow iterates across:

- company IR and newsroom releases
- regulator, exchange, and government disclosures
- SEC EDGAR or equivalent filing sources
- primary newswires
- broker research and analyst-target evidence
- local-market financial media
- industry data providers
- reputable market aggregators

Queries expand across earnings, guidance, valuation, products, customers,
capex, supply, pricing, competition, policy, macro conditions, and risk.

### 4. Validate and deduplicate

Every accepted reference requires:

- URL
- domain
- source title
- source-displayed `published_iso`
- tier
- concise supported claim
- explicit ticker assignment

Canonical URL duplicates and syndicated copies of the same underlying
publication are counted once per ticker.

### 5. Synthesize

After the coverage gate passes, the plugin builds drivers, fundamentals,
macro state, fair value, three six-month scenarios, non-overlapping price
bands, quality scores, comparison rows, and research workflow guidance.

### 6. Persist and validate

The final bundle is persisted beneath:

```text
.stock-research/<TICKER>/<ISO_DATETIME>.json
```

Multi-ticker or diagnostic runs may use an appropriate combined directory.
Doctor validates the exact persisted bundle rather than regenerating research.

## Evidence Policy

### Source tiers

| Tier | Meaning | Usage |
|---|---|---|
| A | Company filings and IR, regulators, primary newswires, broker research, filing-derived fundamentals | Preferred support for major and numeric claims |
| B | Reputable aggregators and secondary market sources | Corroboration and fallback support |
| C | Blogs, forums, social posts, and weak secondary sources | Never displayed or counted as supporting evidence |

### Coverage floor

The floor applies independently to every ticker:

- at least 10 eligible persisted references
- at least five distinct domains
- publication dates inside the inclusive seven-day window
- explicit ticker assignment for shared evidence

A five-ticker completed report therefore needs at least 50 ticker-reference
assignments. Shared macro evidence counts only when its claim genuinely applies
to every assigned ticker.

### Independence

Major claims require at least two independent sources. A claim supported by
only one eligible source is marked `[single_source]` and is not presented as
settled fact.

### Conflict handling

If eligible Tier-A sources disagree on a synthesis target by more than 10%, the
plugin does not average them into a false point estimate. It emits the
tier-anchored bracket, marks the conflict, suppresses unsupported probability
precision, and records outliers.

### Fundamentals

Fundamental claims prefer SEC EDGAR or equivalent Tier-A filing support. When
fresh primary fundamentals cannot be found inside the window, the bundle flags
the gap and avoids presenting Tier-B summaries as primary evidence.

### Rejected evidence

Candidates are rejected when they are outside the date window, undated,
duplicated, syndicated copies, Tier C, or merely mention a company without
supporting the attached claim. Attempted lanes, queries, and rejection reasons
are retained in diagnostics when coverage fails.

## Research Outputs

A completed multi-ticker bundle contains these reader-facing tables in order:

1. Summary Ranking
2. Price-Band Probability
3. Indicator Scores
4. Reference Confidence
5. Action Guidance

### Fair value and six-month scenarios

Fair value and forward range are separate outputs. The forward range contains
exactly three evidence-backed scenarios: `bear`, `base`, and `bull`. Scenario
probabilities are model judgments tied to current evidence and must sum to
1.0; they are not fixed template weights.

### Price-band probabilities

Price bands are ordered, mutually exclusive intervals that collectively cover
the rendered scenario range. Their probability means “probability of finishing
inside this exact interval,” not “probability the stock rises.”

Current price is only an annotation anchor for implied returns. It does not
determine band boundaries or ranking.

### Return/risk ratio

For each ticker, the report derives midpoint returns for the displayed bands,
then calculates:

```text
probability-weighted upside / probability-weighted downside risk
```

If weighted downside is zero, the ratio is reported as `n/a` rather than an
infinite or invented value.

### Quality-factor scores

Each top-level score ranges from 0 to 100 and includes sub-scores, positive and
negative evidence, a reasoning trace, and missing-evidence penalties.

| Score | Grade |
|---:|---|
| 85–100 | `durable_compounder` |
| 70–84 | `high_quality_cyclical` |
| 55–69 | `constructive_but_volatile` |
| 40–54 | `fragile_opportunity` |
| 0–39 | `low_conviction` |

### Comparative ranking

Multi-ticker ranking sorts by risk-adjusted score, then analysis confidence,
structural stability, and growth quality. Low analysis confidence can cap a
ticker at watchlist status regardless of its price distribution.

Allowed research workflow labels are:

- `prioritize_deeper_due_diligence`
- `watch_for_pullback_or_confirmation`
- `monitor_key_risk_before_action`
- `avoid_new_commitment_until_evidence_improves`

These labels describe the next evidence-gathering action, not a trade.

## JSON, HTML, and PDF Artifacts

Reporting is the mandatory final stage of `stock-research`; no separate report
skill is exposed.

The integrated report workflow targets three sibling artifacts:

- `<run>.report.json` — normalized source bundle plus generation metadata
- `<run>.report.html` — self-contained table-first report with inline CSS
- `<run>.report.pdf` — A4 Chromium rendering of the HTML

The newest source JSON is selected when no explicit bundle is provided.

Completed, partial, halted, diagnostic, and legacy bundles are reportable. A
halted bundle must not render as an unexplained blank page. The report shows:

- current prices that were successfully retrieved
- declared reference and domain counts
- exact per-ticker shortfalls
- omitted synthesis outputs
- attempted source lanes and query classes
- rejection reasons
- `not computed` for rankings and scores that were intentionally not built

Coverage failures produce report artifacts with a warning state. They do not
convert missing research into fabricated values.

## Saved Runs and Diagnostics

### Show a saved run

```text
/stock-research show <run-id>
```

This re-renders the persisted bundle without fresh retrieval.

### Fast doctor

```text
/stock-research doctor <run-id>
```

The fast doctor checks schema, tiers, citation shape, dates, per-ticker
coverage, source independence, and major mechanical rules.

### Deep doctor

```text
/stock-research doctor <run-id> --deep
```

Deep doctor adds cross-output and decision-package validation. Doctor never
reruns research workers; it audits the exact saved JSON.

### Halted runs

If a ticker remains below 10 eligible references or five domains after
exhaustive retrieval, completed synthesis and ranking are blocked for that
ticker. The diagnostic bundle records:

- `status: halted` or `status: partial`
- `halt_flags`
- `evidence_coverage`
- `omitted_outputs`
- `not_found_in_budget`
- current-price metadata when available

## Project Layout

```text
.
├── README.md
├── DISCLAIMER.md
├── .agents/
│   └── plugins/marketplace.json
└── tradingAgents/
    ├── pyproject.toml
    ├── uv.lock
    ├── run_skill.py
    ├── _impl.py
    ├── scripts/
    │   └── update-plugin.sh
    ├── tests/
    └── src/
        ├── .codex-plugin/plugin.json
        ├── claude/settings.json
        ├── codex/
        └── skills/
            └── stock-research/
```

Key components:

- `stock-research/SKILL.md` — live research contract and evidence doctrine
- `stock-research/workers/` — drivers, fundamentals, macro, valuation,
  forward-range, evidence, recency, user-Q&A, and doctor workers
- `stock-research/lib/` — schema, persistence, citations, recency, source tiers,
  conflicts, and SEC helper code
- `stock-research/references/quality-factors.md` — integrated reliability and
  durability scoring contract
- `stock-research/references/reporting.md` — integrated saved-bundle report
  rendering contract
- `src/.codex-plugin/plugin.json` — Codex plugin metadata
- `src/codex/` — Codex shims, manifests, MCP metadata, and hooks
- `src/claude/` — Claude-only configuration

## Local Development

### Install the Python environment

```sh
cd tradingAgents
uv sync
```

### Run deterministic fixture research

Fixtures are for local tests only and are not valid live research:

```sh
cd tradingAgents
python3 run_skill.py run-fixture AAPL "Why did it drop?"
```

The command prints a compact pointer containing the ticker, run ID, saved path,
and status.

### Inspect and validate fixture output

```sh
python3 run_skill.py show <run-id>
python3 run_skill.py doctor <run-id>
python3 run_skill.py doctor <run-id> --deep
```

### Run tests

```sh
cd tradingAgents
python3 -m pytest tests/test_ac2_cross_validation_and_conflict.py
```

The suite exercises cross-validation, source conflicts, persistence, worker
contracts, price bands, current-price handling, ranking, and report-related
rules.

### Refresh the local plugin

```sh
cd tradingAgents
./scripts/update-plugin.sh
```

Do not expect source edits to hot-reload into an existing Codex conversation.

## Troubleshooting

### The report is empty

Inspect the source bundle status. A halted bundle may intentionally lack
ranking, fair value, probabilities, and quality scores. A compatible renderer
must read `current_prices`, `evidence_coverage`, `omitted_outputs`, and
`not_found_in_budget` and display a diagnostic instead of empty tables.

### Coverage shows zero despite recorded counts

The renderer may be recomputing from a missing `reference_confidence_table`.
For halted diagnostic bundles, prefer persisted `evidence_coverage`. For
completed bundles, validate coverage against the actual persisted reference
rows.

### A live run stops below the evidence floor

This is expected when the eligible public source space inside seven days is too
small. Do not backfill with older, undated, duplicated, syndicated, or Tier-C
sources. Review `not_found_in_budget` and retry after new eligible publications
appear.

### Current prices look unusual

yfinance is Tier B. Verify the exchange-native symbol, quote timestamp,
currency, corporate actions, and split adjustments before relying on
price-relative outputs. The source quote is preserved so anomalies remain
auditable.

### Plugin changes do not appear

Run `./scripts/update-plugin.sh`, confirm the installed version it prints, then
start a new conversation.

### PDF generation fails

Confirm that the Playwright CLI and Chromium are installed and available in
`PATH`. A successful PDF must exist, be non-empty, and begin with `%PDF-`.

## Limitations

- The seven-day window can exclude the latest annual or quarterly filing even
  when it remains economically relevant.
- Public source availability differs significantly by ticker and market.
- Analyst targets can disagree materially or use incompatible units.
- yfinance prices are aggregator data and may reflect symbol or corporate-action
  anomalies.
- Scenario probabilities and quality scores are model synthesis, not observed
  frequencies or guarantees.
- A passing evidence count does not guarantee that every desired claim has
  strong primary support.
- Markets and source documents can change immediately after retrieval.

## License and Disclaimer

The plugin manifest currently declares `UNLICENSED`. See
[DISCLAIMER.md](DISCLAIMER.md) for the full no-investment-advice, no-fiduciary,
user-responsibility, and no-warranty terms.
