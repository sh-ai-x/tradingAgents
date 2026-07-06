"""Citation formatting and validation (citation_format)."""
from __future__ import annotations
import re
from typing import Any, Iterable

CITATION_RE = re.compile(
    r"^\[(?P<url>https?://[^\s|]+)\s*\|\s*"
    r"(?P<iso>\d{4}-\d{2}-\d{2})\s*\|\s*"
    r"(?P<title>.+?)\s*\|\s*"
    r"(?P<tier>[ABC])\]$"
)

def format_citation(url: str, retrieval_iso: str, source_title: str, tier: str) -> str:
    """Render the canonical citation string."""
    assert tier in {"A", "B", "C"}, f"invalid tier: {tier}"
    return f"[{url} | {retrieval_iso} | {source_title} | {tier}]"

def parse_citation(s: str) -> dict[str, str] | None:
    """Parse a citation string. Returns None if malformed.

    Keys are normalized to {url, retrieval_iso, source_title, tier}."""
    m = CITATION_RE.match(s.strip())
    if not m:
        return None
    g = m.groupdict()
    return {"url": g["url"], "retrieval_iso": g["iso"],
            "source_title": g["title"], "tier": g["tier"]}

def validate_all(claims: Iterable[Any]) -> list[str]:
    """Validate that every claim has a parseable citation. Returns list of errors."""
    errors: list[str] = []
    for i, claim in enumerate(claims):
        if isinstance(claim, str):
            if parse_citation(claim) is None:
                errors.append(f"claim[{i}] not in citation format: {claim!r}")
        elif isinstance(claim, dict) and "citation" in claim:
            if parse_citation(claim["citation"]) is None:
                errors.append(f"claim[{i}] bad citation: {claim['citation']!r}")
    return errors
