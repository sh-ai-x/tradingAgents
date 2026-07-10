# Codex Shim

Use the shared `stock-research` skill manifest:

- `src/skills/stock-research/SKILL.md`
- `src/skills/stock-quality-factors/SKILL.md`
- `src/skills/stock-research-html-report/SKILL.md`

Codex uses its built-in web search path. Do not depend on
`insane-search@gptaku-plugins`; that plugin is Claude-only in this repository.

Codex plugin metadata lives in `src/.codex-plugin/plugin.json`; Codex MCP and
hook metadata lives under `src/codex/`.

Use `stock-research-html-report` only after a JSON bundle exists. It renders
HTML reports, reference coverage, and per-ticker reference tables without
changing the source research bundle facts.
