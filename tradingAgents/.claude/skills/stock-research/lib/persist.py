"""Persistence: write/read bundles to .stock-research/<TICKER>/<ISO>.json."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def iso_filename_stem(dt: datetime | None = None) -> str:
    """Filesystem-safe ISO datetime stem, e.g. 2026-07-07T10-15-00Z."""
    dt = (dt or datetime.now(timezone.utc)).replace(microsecond=0)
    s = dt.strftime("%Y-%m-%dT%H-%M-%SZ")
    return s

def bundle_path(root: Path, ticker: str, run_id: str | None = None,
                dt: datetime | None = None) -> Path:
    """Resolve the bundle path for a ticker (or for an existing run_id)."""
    ticker = ticker.upper()
    if run_id:
        return root / ticker / f"{run_id}.json"
    return root / ticker / f"{iso_filename_stem(dt)}.json"

def write_bundle(root: Path, ticker: str, bundle: dict[str, Any]) -> Path:
    """Write the bundle to disk. Creates directories as needed."""
    ticker = ticker.upper()
    path = bundle_path(root, ticker, bundle.get("run_id"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=False))
    return path

def read_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())

def list_runs(root: Path, ticker: str) -> list[Path]:
    """Return all bundle files for a ticker, oldest first."""
    ticker = ticker.upper()
    d = root / ticker
    if not d.exists():
        return []
    return sorted(p for p in d.glob("*.json") if p.is_file())

def accumulate(root: Path, ticker: str, fields: list[str]) -> dict[str, list[Any]]:
    """Merge the named fields across all prior bundles for this ticker.

    Used for follow_up and postmortem_required accumulation.
    """
    merged: dict[str, list[Any]] = {f: [] for f in fields}
    for path in list_runs(root, ticker):
        try:
            b = read_bundle(path)
        except Exception:
            continue
        dp = b.get("decision_package", {}) or {}
        for f in fields:
            v = dp.get(f)
            if isinstance(v, list):
                merged[f].extend(v)
    # Dedup strings while preserving order.
    for f in fields:
        seen: set = set()
        out: list[Any] = []
        for x in merged[f]:
            key = json.dumps(x, sort_keys=True) if not isinstance(x, str) else x
            if key in seen:
                continue
            seen.add(key)
            out.append(x)
        merged[f] = out
    return merged
