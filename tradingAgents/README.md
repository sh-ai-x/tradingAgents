# tradingAgents

Evidence-backed stock research skill for Claude Code and Codex.

## What it does

`tradingAgents` collects current stock evidence, classifies source quality,
applies recency and conflict rules, and emits table-first research bundles.
It is research material only, not investment advice.

## Repository Layout

- `src/skills/stock-research/` - shared skill manifest, workers, lib, and fixtures.
- `src/skills/stock-quality-factors/` - companion scoring framework for reliability, moat, stability, growth quality, and risk-adjusted score.
- `src/skills/stock-research-html-report/` - post-processing skill that renders saved stock-research JSON bundles as local HTML reports.
- `src/claude/settings.json` - Claude-only settings.
- `src/codex/` - Codex-only shims, hooks, and metadata.
- `src/.codex-plugin/plugin.json` - Codex plugin metadata.
- `.claude/skills/stock-research` - compatibility symlink to the shared skill.
- `.codex/AGENTS.md`, `.codex/MANIFEST.md`, and `.codex/skills/stock-research/MANIFEST.md` - Codex shims.
- `run_skill.py` - local CLI driver for fixture, show, and doctor workflows.

Runtime bundles under `.stock-research/` and agent scratch worktrees are local
artifacts and are not part of the public repository.

## Quickstart

Live research runs are intended to be invoked through the Claude Code or Codex
skill host so the agent can perform fresh web/source retrieval.

```text
/stock-research NVDA "What changed this week?" "What are the key risks?"
```

Multiple tickers can be requested together for comparative ranking:

```text
/stock-research MU SNDK NVDA "Compare 6-month price ranges, interval probabilities, and evidence quality."
```

Expected output is table-first and includes summary ranking, non-overlapping
price-band probabilities, implied return ranges, return/risk ratio, citations,
and recency/conflict flags. A band probability is the probability that the
6-month price finishes inside that exact interval; it is not an upside
probability or a ranking input.

Current price is stored in `current_prices` keyed by ticker, with
`current_price` reserved as a single-ticker compatibility alias. Fair value
bands are derived from `per_ticker_results` or `fair_value` when the ranking
row does not repeat them, so the report does not depend on duplicated fields.

Each live run searches iteratively until every ticker has at least 10 eligible
references across at least 5 domains. Counted and displayed references must
have a source-published date inside the inclusive 7-day window ending at the
run retrieval time. If exhaustive search cannot meet the floor, the run stays
honest: it emits a partial bundle with the attempted queries and coverage
shortfall instead of backfilling older, undated, duplicated, or low-quality
sources.

## Local Plugin Development

The repository marketplace at `../.agents/plugins/marketplace.json` exposes the
plugin as `trading-agents@trading-agents-dev`. Codex installs a cached copy of a
marketplace plugin, so editing `src/` does not hot-reload an already installed
plugin or an existing conversation.

For normal ChatGPT/Codex desktop development, update the local plugin source,
restart the desktop app, and test in a new thread. For a deterministic CLI
refresh, run:

```sh
./scripts/update-plugin.sh
```

The script temporarily adds a cachebuster, validates the plugin, reinstalls it
from `trading-agents-dev`, restores `src/.codex-plugin/plugin.json`, and prints
the installed version. It requires the `codex` CLI and the bundled
`plugin-creator` system skill under `${CODEX_HOME:-$HOME/.codex}/skills`.

## HTML Reports

Use `stock-research-html-report` after a research run when the output should be
shown as a local browser report:

```sh
python3 src/skills/stock-research-html-report/scripts/render_stock_research_html.py .stock-research/<TICKER>/<run>.json
```

The renderer writes an HTML file next to the JSON bundle. It preserves partial
run flags, displays the table-first ranking, and adds:

- `Reference Coverage` - per ticker counts for recent references and distinct domains.
- `Reference Confidence` - the full cited source table.
- `References By Ticker` - direct ticker-specific references plus shared market, macro, or sector references used in the thesis.
- `Current Price` - per-ticker yfinance quote context.
- `Summary Ranking` - derived fair-value bands and action labels when the ranking row omits them.

When a run must satisfy the stock-research coverage floor, use strict mode:

```sh
python3 src/skills/stock-research-html-report/scripts/render_stock_research_html.py .stock-research/<TICKER>/<run>.json --strict-coverage
```

Strict mode still writes the HTML report, but exits non-zero if any ticker has
fewer than 10 references from the last 7 days or fewer than 5 distinct recent
domains.

For source mix, U.S.-listed tickers should prioritize U.S. IR, SEC filings,
U.S. market/news sources, and U.S. analyst coverage. Korea-listed tickers should
prioritize company IR, DART/KRX filings, Korean broker reports, and Korean
financial media; global ADR or U.S. market sources can be used as supplemental
evidence when domestic coverage is thin.

For local deterministic testing, use the fixture runner:

```sh
python3 tradingAgents/run_skill.py run-fixture AAPL "Why did it drop in March 2026?"
python3 tradingAgents/run_skill.py show <run-id>
python3 tradingAgents/run_skill.py doctor <run-id> --deep
```

## Disclaimer

This repository produces research material only. It does not provide buy, sell,
or hold recommendations.
