"""SEC EDGAR retrieval helpers backed by the optional ``secedgar`` package.

The skill treats SEC filings as Tier-A fundamentals evidence. This module keeps
network/download concerns separate from the fundamentals worker, which only
normalizes already-extracted filing metrics.
"""
from __future__ import annotations
from datetime import date
from typing import Any


class SecEdgarUnavailable(RuntimeError):
    """Raised when ``secedgar`` is not installed in the runtime."""


def _filing_type(form_type: str):
    try:
        from secedgar import FilingType
    except ModuleNotFoundError as exc:
        raise SecEdgarUnavailable(
            "Install secedgar from https://github.com/sec-edgar/sec-edgar "
            "to fetch SEC filings for fundamentals."
        ) from exc

    normalized = form_type.upper().replace("-", "")
    mapping = {
        "10Q": FilingType.FILING_10Q,
        "10K": FilingType.FILING_10K,
    }
    if normalized not in mapping:
        raise ValueError(f"unsupported SEC filing type: {form_type}")
    return mapping[normalized]


def company_filing_urls(
    ticker: str,
    form_type: str,
    user_agent: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[str]:
    """Return SEC EDGAR filing URLs for a ticker and filing type.

    SEC requires a descriptive user agent. Callers should pass a name and email
    controlled by the deployment, not a generic placeholder.
    """
    if not user_agent or "@" not in user_agent:
        raise ValueError("SEC EDGAR requests require a descriptive user_agent with contact email")

    try:
        from secedgar import filings
    except ModuleNotFoundError as exc:
        raise SecEdgarUnavailable(
            "Install secedgar from https://github.com/sec-edgar/sec-edgar "
            "to fetch SEC filings for fundamentals."
        ) from exc

    request: dict[str, Any] = {
        "cik_lookup": ticker.lower(),
        "filing_type": _filing_type(form_type),
        "user_agent": user_agent,
    }
    if start_date is not None:
        request["start_date"] = start_date
    if end_date is not None:
        request["end_date"] = end_date
    return list(filings(**request).get_urls())
