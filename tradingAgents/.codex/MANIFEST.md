# Codex Shim

Use the shared `stock-research` skill manifest:

- `src/skills/stock-research/SKILL.md`

Codex uses built-in web search. Do not depend on
`insane-search@gptaku-plugins`; that plugin is Claude-only in this repository.

Codex plugin metadata lives in `src/.codex-plugin/plugin.json`; Codex MCP and
hook metadata lives under `src/codex/`.
