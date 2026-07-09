"""Deterministic tier classification of a source URL/domain (tier-A/B/C)."""
from __future__ import annotations
import re
from urllib.parse import urlparse

# Tier-A primary domains (brokers / regulators / primary newswires / IR / SEC).
TIER_A_DOMAINS = {
    "sec.gov", "edgar.sec.gov",
    "bloomberg.com", "reuters.com", "wsj.com", "ft.com",
    "cnbc.com", "ap.org", "apnews.com",
    "nasdaq.com", "nyse.com",
    "blackrock.com", "goldmansachs.com", "morganstanley.com", "jpmorgan.com",
    "berkshirehathaway.com", "berkshirehathawayinc.com",
    "investor.apple.com", "investor.microsoft.com",
    "prnewswire.com", "businesswire.com", "globenewswire.com",
}

# Tier-B aggregators.
TIER_B_DOMAINS = {
    "finance.yahoo.com", "yahoo.com",
    "marketwatch.com", "marketbeat.com",
    "investopedia.com", "morningstar.com",
    "seekingalpha.com", "fool.com",
    "barrons.com", "investing.com", "stockanalysis.com",
}

# Tier-C — blogs / social / forums.
TIER_C_DOMAINS = {
    "reddit.com", "twitter.com", "x.com", "facebook.com",
    "substack.com", "medium.com", "wordpress.com",
    "stocktwits.com", "tipranks.com",
    "fintwit.com",
}

def classify(url: str) -> str:
    """Return the tier for a URL. Deterministic — same URL always returns the
    same tier. Falls back to tier-C (most conservative) when unknown."""
    host = urlparse(url).hostname or ""
    host = host.lower().lstrip("www.")
    # Exact domain match.
    if host in TIER_A_DOMAINS:
        return "A"
    if host in TIER_B_DOMAINS:
        return "B"
    if host in TIER_C_DOMAINS:
        return "C"
    # Suffix match (handles country TLDs and subdomains).
    for d in TIER_A_DOMAINS:
        if host.endswith("." + d):
            return "A"
    for d in TIER_B_DOMAINS:
        if host.endswith("." + d):
            return "B"
    for d in TIER_C_DOMAINS:
        if host.endswith("." + d):
            return "C"
    return "C"  # unknown -> tier-C (conservative)
