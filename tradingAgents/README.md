# tradingAgents

Evidence-backed stock research skill for Claude Code and Codex.

## What it does

`tradingAgents` collects current stock evidence, classifies source quality,
applies recency and conflict rules, and emits table-first research bundles.
It is research material only, not investment advice.

## Repository Layout

- `src/skills/stock-research/` - shared skill manifest, workers, lib, and fixtures.
- `src/skills/stock-quality-factors/` - companion scoring framework for reliability, moat, stability, growth quality, and risk-adjusted score.
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

For local deterministic testing, use the fixture runner:

```sh
python3 tradingAgents/run_skill.py run-fixture AAPL "Why did it drop in March 2026?"
python3 tradingAgents/run_skill.py show <run-id>
python3 tradingAgents/run_skill.py doctor <run-id> --deep
```

## Disclaimer

This repository produces research material only. It does not provide buy, sell,
or hold recommendations.
