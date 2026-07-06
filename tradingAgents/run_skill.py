#!/usr/bin/env python3
"""CLI driver for /stock-research commands.

Usage:
    python3 tradingAgents/run_skill.py run AAPL "Why did it drop in March 2026?"
    python3 tradingAgents/run_skill.py show <run-id>
    python3 tradingAgents/run_skill.py doctor <run-id> [--deep]

In a real harness this is invoked by the Claude Code or Codex loader. Here it
is driven against an in-fixture evidence set so the full pipeline can be
exercised end-to-end.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".stock-research"
FIXTURES = ROOT / ".claude" / "skills" / "stock-research" / "fixtures"

sys.path.insert(0, str(ROOT))
# Also expose the parent dir so `tradingAgents` resolves whether invoked from
# inside this folder (most common) or from the repo root.
sys.path.insert(0, str(ROOT.parent))
try:
    from tradingAgents import _impl  # noqa: E402  (the actual runner)
except ModuleNotFoundError:
    # When run from inside tradingAgents/, `tradingAgents` is the current
    # directory — load _impl as a top-level module instead.
    import importlib.util
    _spec = importlib.util.spec_from_file_location("_impl", ROOT / "_impl.py")
    _impl = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_impl)

def main(argv=None):
    p = argparse.ArgumentParser(prog="stock-research")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run")
    pr.add_argument("ticker")
    pr.add_argument("questions", nargs="*")

    ps = sub.add_parser("show")
    ps.add_argument("run_id")

    pd = sub.add_parser("doctor")
    pd.add_argument("run_id")
    pd.add_argument("--deep", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "run":
        bundle = _impl.run(args.ticker.upper(), args.questions, FIXTURES, RUNTIME)
        out = {
            "ticker": bundle["ticker"],
            "run_id": bundle["run_id"],
            "path": str(_impl.last_path()),
            "status": bundle["status"],
        }
        print(json.dumps(out, indent=2))
    elif args.cmd == "show":
        bundle = _impl.show(args.run_id, RUNTIME)
        print(json.dumps(bundle, indent=2))
    elif args.cmd == "doctor":
        result = _impl.doctor(args.run_id, RUNTIME, deep=args.deep)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
