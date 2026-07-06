# tradingAgents

Stock-research skill for Claude Code and Codex.

## Layout

- `.claude/skills/stock-research/` — Claude Code skill (SKILL.md frontmatter + workers + lib).
- `.codex/AGENTS.md` and `.codex/MANIFEST.md` — strict-subset manifest for Codex.
- `.stock-research/<TICKER>/<ISO>.json` — persisted research bundles.
- `run_skill.py` — CLI driver for `run`, `show`, `doctor`.

## Quickstart

```sh
python3 tradingAgents/run_skill.py run AAPL "Why did it drop in March 2026?"
python3 tradingAgents/run_skill.py show <run-id>
python3 tradingAgents/run_skill.py doctor <run-id> --deep
```

## Disclaimer

See `../DISCLAIMER.md` at the repo root. This is research material only.
