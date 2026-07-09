# Source Layout

This directory is split by responsibility:

- `common/` contains files shared by Claude Code and Codex.
- `claude/` contains Claude-only settings such as `insane-search@gptaku-plugins`.
- `codex/` contains Codex-only shims, MCP, hooks, and metadata. Codex uses built-in web search.
