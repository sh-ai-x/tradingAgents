# tradingAgents

Evidence-backed stock research tools for Claude Code and Codex.

`tradingAgents` helps an agent gather current market evidence, classify source
quality, apply recency and conflict rules, and produce a table-first stock
research bundle. It is research material only and does not provide buy, sell,
or hold recommendations.

## What You Get

A stock research run produces a persisted JSON bundle under
`tradingAgents/.stock-research/<TICKER>/<RUN_ID>.json` and a reader-facing
summary that can include:

- current price metadata from yfinance when available
- fair value band
- 6-month bear/base/bull forward range
- downside, neutral, and upside probability bands
- implied return ranges and return/risk ratio
- key drivers and macro context
- fundamentals from filing-backed sources when available
- source citations, recency flags, and confidence checks
- optional quality-factor scoring for reliability, moat, stability, growth
  quality, and risk-adjusted score

Current price is stored in the bundle as `current_prices` keyed by ticker,
with `current_price` kept only as a single-ticker compatibility alias. Fair
value bands are derived from `per_ticker_results` or `fair_value` when the
ranking row does not repeat them.

## Usage

Live research should be run through Claude Code or Codex so the agent can
perform fresh web/source retrieval during the run.

Example prompt:

```text
/stock-research NVDA "What changed this week?" "What are the key risks?"
```

Multiple tickers can be requested in one run when you want a comparative
ranking:

```text
/stock-research MU SNDK NVDA "Compare 6-month upside, downside risk, and evidence quality."
```

Expected reader-facing output starts with tables before the written analysis.
For example:

```text
Summary Ranking Table
| ticker | rank | current price | fair value band | upside band probability | risk-adjusted score | research action |
| MU     | 1    | 938.38 USD    | 980-1,080       | 42%                     | 78                  | prioritize deeper due diligence |
| NVDA   | 2    | 154.20 USD    | 150-180         | 35%                     | 74                  | watch for confirmation |
| SNDK   | 3    | 65.10 USD     | 58-72           | 24%                     | 61                  | monitor key risk before action |

Band Probability Table
| ticker | downside band | neutral band | upside band | implied return range | return/risk |
| MU     | 830-900 / 25% | 900-1,000 / 33% | 1,000-1,120 / 42% | -12% to +19% | 1.8x |
```

The exact numbers depend on current sources gathered during the run. The skill
keeps citations and recency/conflict flags with the bundle so the result can be
audited later.

## JSON, HTML, and PDF Reports

The local `stock-research-html-report` skill builds a complete artifact set in
one command:

```sh
python3 ~/.codex/skills/stock-research-html-report/scripts/build_report_bundle.py \
  .stock-research/<TICKER>/<run>.json
```

When the input path is omitted, the command selects the newest source JSON
under `.stock-research/`. It creates three sibling files:

- `<run>.report.json` — normalized source bundle plus generation metadata
- `<run>.report.html` — self-contained, table-first browser report
- `<run>.report.pdf` — A4 Chromium rendering of the HTML

Completed, partial, halted, diagnostic, and legacy bundles are supported. A
coverage shortfall does not produce a blank report: the HTML and PDF show the
available current prices, declared reference/domain counts, exact shortfalls,
omitted outputs, attempted retrieval lanes, and rejection reasons. Rankings or
scores that were not synthesized are labeled `not computed`.

The command verifies that all three artifacts exist and that the PDF is
non-empty with a valid `%PDF-` signature. Its successful warning state is
`complete_with_coverage_warnings` when artifacts were generated but the
research coverage floor was not met. Use `--strict-coverage` only when callers
also need a nonzero exit status for that warning.

For local deterministic testing, use the fixture runner:

```sh
cd tradingAgents
python3 run_skill.py run-fixture AAPL "Why did it drop in March 2026?"
```

The fixture command prints a compact JSON pointer like:

```json
{
  "ticker": "AAPL",
  "run_id": "2026-07-07T10-15-00Z_AAPL",
  "path": "tradingAgents/.stock-research/AAPL/2026-07-07T10-15-00Z_AAPL.json",
  "status": "ok"
}
```

Use that run id with:

```sh
python3 run_skill.py show <run-id>
python3 run_skill.py doctor <run-id> --deep
```

## Development

Run the test suite:

```sh
cd tradingAgents
python3 -m pytest tests/test_ac2_cross_validation_and_conflict.py
```

Important project paths:

- `tradingAgents/src/skills/stock-research/SKILL.md` - main skill contract
- `tradingAgents/src/skills/stock-quality-factors/SKILL.md` - companion quality
  scoring contract
- `tradingAgents/src/skills/stock-research/workers/` - worker implementation
- `tradingAgents/run_skill.py` - local fixture/show/doctor CLI
- `~/.codex/skills/stock-research-html-report/` - local one-command JSON, HTML,
  and PDF report pipeline

## Disclaimer

This repository produces research material only. It is not investment advice.
