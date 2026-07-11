#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN_ROOT="$REPO_ROOT/src"
MARKETPLACE_JSON="$REPO_ROOT/../.agents/plugins/marketplace.json"
PLUGIN_CREATOR_ROOT="${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator"
MANIFEST="$PLUGIN_ROOT/.codex-plugin/plugin.json"
BACKUP="$(mktemp "${TMPDIR:-/tmp}/trading-agents-plugin.XXXXXX.json")"

cleanup() {
  cp "$BACKUP" "$MANIFEST"
  rm -f "$BACKUP"
}
trap cleanup EXIT

for required in \
  "$PLUGIN_CREATOR_ROOT/scripts/update_plugin_cachebuster.py" \
  "$PLUGIN_CREATOR_ROOT/scripts/validate_plugin.py" \
  "$PLUGIN_CREATOR_ROOT/scripts/read_marketplace_name.py" \
  "$MARKETPLACE_JSON" \
  "$MANIFEST"; do
  if [[ ! -e "$required" ]]; then
    echo "Missing required file: $required" >&2
    exit 1
  fi
done

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found in PATH" >&2
  exit 1
fi

cp "$MANIFEST" "$BACKUP"
python3 "$PLUGIN_CREATOR_ROOT/scripts/update_plugin_cachebuster.py" "$PLUGIN_ROOT"
python3 "$PLUGIN_CREATOR_ROOT/scripts/validate_plugin.py" "$PLUGIN_ROOT"

PLUGIN_NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$MANIFEST")"
PLUGIN_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$MANIFEST")"
MARKETPLACE_NAME="$(python3 "$PLUGIN_CREATOR_ROOT/scripts/read_marketplace_name.py" --marketplace-path "$MARKETPLACE_JSON")"

codex plugin add "$PLUGIN_NAME@$MARKETPLACE_NAME"
echo "Updated $PLUGIN_NAME@$MARKETPLACE_NAME to $PLUGIN_VERSION"
echo "Start a new Codex thread to load the updated plugin."
