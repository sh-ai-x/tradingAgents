#!/usr/bin/env python3
"""Fetch current or latest regular-session prices via yfinance.

Outputs JSON only. This script never installs dependencies; if yfinance is not
available, it returns a structured unavailable status so the skill can continue
without price-relative outputs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Any


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_from_unix(ts: Any) -> str | None:
    if ts is None:
        return None
    try:
        return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return None


def _latest_history_close(yf: Any, ticker: str) -> dict[str, Any] | None:
    hist = yf.Ticker(ticker).history(period="7d", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        return None
    row = hist.dropna(subset=["Close"]).tail(1)
    if row.empty:
        return None
    idx = row.index[-1]
    close = float(row["Close"].iloc[-1])
    if hasattr(idx, "to_pydatetime"):
        asof = idx.to_pydatetime()
        if asof.tzinfo is None:
            asof = asof.replace(tzinfo=dt.timezone.utc)
        asof_iso = asof.astimezone(dt.timezone.utc).date().isoformat()
    else:
        asof_iso = str(idx)[:10]
    return {
        "price": close,
        "price_type": "historical_regular_close",
        "asof_iso": asof_iso,
    }


def fetch_price(ticker: str) -> dict[str, Any]:
    retrieval_iso = _utc_now()
    try:
        import yfinance as yf  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local env
        return {
            "status": "unavailable",
            "ticker_used": ticker,
            "source": "yfinance",
            "retrieval_iso": retrieval_iso,
            "reason": f"yfinance_import_failed: {exc.__class__.__name__}: {exc}",
        }

    try:
        t = yf.Ticker(ticker)
        info = getattr(t, "fast_info", None) or {}
        market_state = None
        currency = None
        price = None
        price_type = None
        asof_iso = None

        # fast_info uses property access and may lazily fetch network data.
        for key in ("currency",):
            try:
                currency = getattr(info, key, None) or (info.get(key) if hasattr(info, "get") else None)
            except Exception:
                currency = None

        try:
            price = getattr(info, "last_price", None) or (info.get("last_price") if hasattr(info, "get") else None)
        except Exception:
            price = None
        if price is not None:
            price = float(price)
            price_type = "regular_market_price"

        try:
            meta = t.get_history_metadata() or {}
        except Exception:
            meta = {}
        market_state = meta.get("marketState") or meta.get("exchangeTimezoneName")
        currency = currency or meta.get("currency")
        asof_iso = _iso_from_unix(meta.get("regularMarketTime") or meta.get("firstTradeDate"))

        if price is None or asof_iso is None:
            hist_close = _latest_history_close(yf, ticker)
            if hist_close:
                price = hist_close["price"]
                price_type = hist_close["price_type"]
                asof_iso = hist_close["asof_iso"]

        if price is None or asof_iso is None:
            return {
                "status": "unavailable",
                "ticker_used": ticker,
                "source": "yfinance",
                "retrieval_iso": retrieval_iso,
                "reason": "no_price_or_asof_from_yfinance",
            }

        return {
            "status": "ok",
            "ticker_used": ticker,
            "price": price,
            "currency": currency,
            "price_type": price_type,
            "market_state": market_state,
            "asof_iso": asof_iso,
            "source": "yfinance",
            "retrieval_iso": retrieval_iso,
        }
    except Exception as exc:  # pragma: no cover - network/provider dependent
        return {
            "status": "unavailable",
            "ticker_used": ticker,
            "source": "yfinance",
            "retrieval_iso": retrieval_iso,
            "reason": f"yfinance_fetch_failed: {exc.__class__.__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch yfinance current prices as JSON.")
    parser.add_argument("tickers", nargs="+", help="Exchange-native tickers, e.g. MU SNDK 000660.KS")
    args = parser.parse_args()
    payload = {
        "retrieval_iso": _utc_now(),
        "source": "yfinance",
        "prices": {ticker: fetch_price(ticker) for ticker in args.tickers},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
