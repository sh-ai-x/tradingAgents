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

## Usage

Live research should be run through Claude Code or Codex so the agent can
perform fresh web/source retrieval during the run.

Example prompt:

```text
/stock-research NVDA "What changed this week?" "What are the key risks?"
```

For local deterministic testing, use the fixture runner:

```sh
cd tradingAgents
python3 run_skill.py run-fixture AAPL "Why did it drop in March 2026?"
```

The command prints a compact JSON pointer with the ticker, run id, output path,
and status. Use that run id with:

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

## Disclaimer

This repository produces research material only. It is not investment advice.
