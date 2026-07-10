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
/stock-research MU SNDK NVDA "Compare 6-month upside, downside risk, and evidence quality."
```

Expected output is table-first and includes summary ranking, probability bands,
implied return ranges, return/risk ratio, citations, and recency/conflict flags.

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
