#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse


TICKER_ALIASES = {
    "MU": ["MU", "Micron"],
    "SNDK": ["SNDK", "Sandisk", "SanDisk"],
    "WDC": ["WDC", "Western Digital"],
    "LITE": ["LITE", "Lumentum"],
    "000660.KS": ["000660.KS", "SK Hynix", "SK hynix", "Hynix"],
    "402340.KS": ["402340.KS", "SK Square", "Palliser"],
}


def esc(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:,.2f}"
    return html.escape(str(value))


def money(price, currency):
    if price is None:
        return "n/a"
    if currency == "USD":
        return f"${float(price):,.2f}"
    if currency == "KRW":
        return f"KRW {float(price):,.0f}"
    return f"{float(price):,.2f} {currency or ''}".strip()


def grade(score):
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "unknown"
    if score >= 85:
        return "very_high"
    if score >= 70:
        return "high"
    if score >= 55:
        return "medium"
    if score >= 40:
        return "low"
    return "very_low"


def citation_parts(ref):
    if not isinstance(ref, str):
        return None
    parts = [p.strip() for p in ref.split("|")]
    if len(parts) < 4:
        return None
    url, published, title, tier = parts[:4]
    return {
        "url": url,
        "domain": urlparse(url).netloc,
        "published": published,
        "title": title,
        "tier": tier,
    }


def normalize_reference(ref):
    if isinstance(ref, dict):
        url = ref.get("url", "")
        return {
            "url": url,
            "title": ref.get("source_title", ref.get("title", "")),
            "domain": ref.get("domain", urlparse(url).netloc),
            "published": ref.get("published_iso", ref.get("published", "")),
            "tier": ref.get("tier", ""),
            "score": ref.get("reference_confidence_score", ""),
            "used_in": ", ".join(ref.get("used_in", [])) if isinstance(ref.get("used_in"), list) else ref.get("used_in", ""),
            "tickers": ref.get("tickers", ref.get("ticker", ref.get("symbols", []))),
        }
    parsed = citation_parts(ref)
    if not parsed:
        return None
    return {
        "url": parsed["url"],
        "title": parsed["title"],
        "domain": parsed["domain"],
        "published": parsed["published"],
        "tier": parsed["tier"],
        "score": "",
        "used_in": "synthesis",
        "tickers": [],
    }


def reference_tickers(ref, known_tickers):
    explicit = ref.get("tickers", [])
    if isinstance(explicit, str):
        explicit = [explicit]
    matched = {ticker for ticker in explicit if ticker in known_tickers}
    searchable = " ".join([ref.get("url", ""), ref.get("title", ""), ref.get("used_in", "")]).lower()
    for ticker in known_tickers:
        aliases = TICKER_ALIASES.get(ticker, [ticker])
        if any(alias.lower() in searchable for alias in aliases):
            matched.add(ticker)
    return sorted(matched, key=lambda value: known_tickers.index(value) if value in known_tickers else 999)


def all_references(data):
    refs = data.get("reference_confidence_table") or data.get("source_refs") or []
    normalized = []
    for ref in refs:
        item = normalize_reference(ref)
        if item:
            normalized.append(item)
    return normalized


def parse_iso_date(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text[:10] + "T00:00:00+00:00")
    except ValueError:
        return None


def reference_is_recent(ref, retrieval_dt, max_age_days=7):
    published = parse_iso_date(ref.get("published"))
    if not published or not retrieval_dt:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    if retrieval_dt.tzinfo is None:
        retrieval_dt = retrieval_dt.replace(tzinfo=timezone.utc)
    age_days = (retrieval_dt - published).total_seconds() / 86400
    return 0 <= age_days <= max_age_days


def group_references(data):
    known_tickers = data.get("tickers", [])
    grouped = {ticker: [] for ticker in known_tickers}
    shared = []
    for ref in all_references(data):
        matched = reference_tickers(ref, known_tickers)
        targets = matched or ["Shared market/macro"]
        for ticker in targets:
            if ticker == "Shared market/macro":
                shared.append(ref)
            else:
                grouped.setdefault(ticker, []).append(ref)
    return grouped, shared


def table(headers, rows, empty="Not found in bundle."):
    if not rows:
        return f"<p class='empty'>{esc(empty)}</p>"
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        body.append(f"<tr>{cells}</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def prose(value):
    """Render nested narrative data without losing detail; link explicit URLs."""
    if value in (None, "", [], {}):
        return "<p class='empty'>Not found in bundle.</p>"
    if isinstance(value, dict):
        blocks = []
        for key, child in value.items():
            title = str(key).replace("_", " ").title()
            blocks.append(f"<div class='narrative-block'><h4>{esc(title)}</h4>{prose(child)}</div>")
        return "".join(blocks)
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{prose(item)}</li>" for item in value) + "</ul>"
    safe = esc(value)
    safe = re.sub(
        r"(https?://[^\s&lt;&gt;]+)",
        lambda match: f"<a href='{match.group(1)}'>{match.group(1)}</a>",
        safe,
    )
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", safe) if part.strip()]
    return "".join(f"<p>{part.replace(chr(10), '<br>')}</p>" for part in paragraphs)


def build_detailed_analysis(data):
    detail = data.get("detailed_analysis")
    if not isinstance(detail, dict):
        return "<p class='empty'>Not found in bundle. Detailed analysis is required for a full report.</p>"
    sections = []
    ordered = [
        ("executive_summary", "Executive Summary"),
        ("methodology", "Research Methodology"),
        ("ticker_analyses", "Ticker-by-Ticker Analysis"),
        ("comparative_analysis", "Comparative Analysis"),
        ("scenario_methodology", "Scenario and Probability Methodology"),
        ("limitations", "Limitations and Evidence Gaps"),
    ]
    for key, title in ordered:
        sections.append(f"<section class='narrative'><h2>{title}</h2>{prose(detail.get(key))}</section>")
    return "".join(sections)


def build_summary_rows(data):
    prices = current_price_map(data)
    fair_values = fair_value_map(data)
    actions = action_guidance_map(data)
    rows = []
    for item in data.get("comparative_ranking", []):
        ticker = item.get("ticker", "")
        price = prices.get(ticker, {})
        rows.append([
            esc(ticker),
            esc(item.get("rank")),
            esc(money(price.get("price"), price.get("currency"))),
            esc(format_fair_value_band(item.get("fair_value_band"), fair_values.get(ticker))),
            esc(item.get("risk_adjusted_score")),
            esc(item.get("analysis_confidence_score")),
            esc(item.get("research_action", actions.get(ticker, "not found"))),
        ])
    return rows


def current_price_map(data):
    prices = {}
    raw_map = data.get("current_prices")
    if isinstance(raw_map, dict):
        for ticker, payload in raw_map.items():
            if isinstance(payload, dict):
                prices[ticker] = payload
    raw_single = data.get("current_price")
    if isinstance(raw_single, dict):
        ticker = raw_single.get("ticker_used") or data.get("ticker")
        if ticker and ticker not in prices:
            prices[ticker] = raw_single
    return prices


def fair_value_map(data):
    values = {}
    raw = data.get("per_ticker_results")
    if isinstance(raw, dict):
        for ticker, payload in raw.items():
            if isinstance(payload, dict):
                values[ticker] = payload
    fv = data.get("fair_value")
    if isinstance(fv, dict):
        ticker = data.get("ticker")
        if ticker and ticker not in values:
            values[ticker] = fv
    return values


def format_fair_value_band(explicit_band, payload):
    if explicit_band not in (None, "", [], {}):
        if isinstance(explicit_band, (list, tuple)) and len(explicit_band) >= 2:
            return f"{money(explicit_band[0], 'USD' if isinstance(explicit_band[0], (int, float)) else '')} - {money(explicit_band[1], 'USD' if isinstance(explicit_band[1], (int, float)) else '')}"
        return explicit_band
    if not isinstance(payload, dict):
        return "not found"
    band = payload.get("fair_value_band")
    currency = payload.get("currency", "")
    if isinstance(band, (list, tuple)) and len(band) >= 2:
        return f"{money(band[0], currency)} - {money(band[1], currency)}"
    if payload.get("band_low") is not None and payload.get("band_high") is not None:
        return f"{money(payload.get('band_low'), currency)} - {money(payload.get('band_high'), currency)}"
    if payload.get("point") is not None:
        return money(payload.get("point"), currency)
    return "not found"


def action_guidance_map(data):
    mapping = {}
    for row in data.get("action_guidance", []):
        if not isinstance(row, dict):
            continue
        ticker = row.get("ticker")
        label = row.get("label")
        if ticker and label:
            mapping[ticker] = label
    return mapping


def build_current_price_rows(data):
    rows = []
    for ticker, price in current_price_map(data).items():
        rows.append([
            esc(ticker),
            esc(price.get("status", "not found")),
            esc(money(price.get("price"), price.get("currency"))),
            esc(price.get("asof_iso", "not found")),
            esc(price.get("source", "not found")),
            esc(price.get("reason", price.get("price_type", "latest quote from yfinance"))),
        ])
    return rows


def build_indicator_rows(data):
    rows = []
    for item in data.get("comparative_ranking", []):
        ticker = item.get("ticker", "")
        q = item.get("quality_factors", {})
        rows.append([
            esc(ticker),
            esc(q.get("reliability", item.get("reliability", "not found"))),
            esc(q.get("economic_moat", item.get("economic_moat", "not found"))),
            esc(q.get("structural_stability", item.get("structural_stability", "not found"))),
            esc(q.get("growth_quality", item.get("growth_quality", "not found"))),
            esc(item.get("risk_adjusted_score")),
            esc(item.get("analysis_confidence_score")),
        ])
    return rows


def build_band_rows(data):
    rows = []
    bands = data.get("band_probability_table") or []
    if isinstance(bands, dict):
        bands = [
            {"ticker": ticker, "bands": value if isinstance(value, list) else [value]}
            for ticker, value in bands.items()
        ]
    def format_price_range(entry, currency_hint=""):
        if not isinstance(entry, dict):
            return "not found"
        if entry.get("price_range"):
            return entry.get("price_range")
        low = entry.get("low")
        high = entry.get("high")
        if low is None or high is None:
            return "not found"
        currency = entry.get("currency", currency_hint)
        if currency == "USD":
            return f"USD {float(low):,.0f}-{float(high):,.0f}"
        if currency == "KRW":
            return f"KRW {float(low):,.0f}-{float(high):,.0f}"
        return f"{float(low):,.0f}-{float(high):,.0f}" + (f" {currency}" if currency else "")

    for ticker_entry in bands:
        if not isinstance(ticker_entry, dict):
            continue
        ticker = ticker_entry.get("ticker", "")
        ticker_bands = ticker_entry.get("bands")
        if ticker_bands is None:
            # Backward compatibility for legacy fixed downside/neutral/upside bundles.
            legacy_names = ("downside_band", "neutral_band", "upside_band")
            ticker_bands = []
            for name in legacy_names:
                value = ticker_entry.get(name)
                if isinstance(value, dict):
                    ticker_bands.append({"band_id": name, **value})
        normalized_bands = []
        if isinstance(ticker_bands, list):
            for idx, band in enumerate(ticker_bands, start=1):
                if isinstance(band, dict):
                    normalized_bands.append(band)
                    continue
                if isinstance(band, (list, tuple)) and len(band) >= 3:
                    low, high, probability = band[:3]
                    normalized_bands.append({
                        "band_id": f"price_band_{idx}",
                        "price_range": format_price_range({"low": low, "high": high}, ticker_entry.get("currency", "")),
                        "probability": probability,
                        "scenario_source": ticker_entry.get("scenario_source", "not found"),
                        "rationale": ticker_entry.get("rationale", "not found"),
                        "currency": ticker_entry.get("currency", ""),
                    })
                elif band is not None:
                    normalized_bands.append({"band_id": f"price_band_{idx}", "price_range": "not found", "probability": "not found"})
        elif isinstance(ticker_bands, dict):
            normalized_bands.append(ticker_bands)

        for band in normalized_bands:
            if not isinstance(band, dict):
                continue
            rows.append([
                esc(ticker),
                esc(band.get("band_id", band.get("band", "not found"))),
                esc(format_price_range(band, ticker_entry.get("currency", ""))),
                esc(band.get("probability", "not found")),
                esc(band.get("scenario_source", "not found")),
                esc(band.get("implied_return_range", "not found")),
                esc(band.get("return_risk_ratio", "not found")),
                esc(band.get("rationale", "not found")),
            ])
    return rows


def build_reference_rows(data):
    rows = []
    for ref in all_references(data):
        link = f"<a href='{esc(ref['url'])}'>{esc(ref['title'])}</a>" if ref["url"] else esc(ref["title"])
        rows.append([link, esc(ref["domain"]), esc(ref["published"]), esc(ref["tier"]), esc(ref["score"]), esc(grade(ref["score"])), esc(ref["used_in"])])
    return rows


def build_references_by_ticker(data):
    known_tickers = data.get("tickers", [])
    grouped, shared = group_references(data)
    sections = []
    for ticker in known_tickers:
        rows = []
        for ref in grouped.get(ticker, []) + shared:
            link = f"<a href='{esc(ref['url'])}'>{esc(ref['title'])}</a>" if ref["url"] else esc(ref["title"])
            rows.append([
                link,
                esc(ref["domain"]),
                esc(ref["published"]),
                esc(ref["tier"]),
                esc(ref["score"]),
                esc(grade(ref["score"])),
                esc(ref["used_in"]),
            ])
        sections.append(f"<div class='ref-group'><h3>{esc(ticker)}</h3>{table(['Source', 'Domain', 'Published', 'Tier', 'Ref. confidence', 'Grade', 'Used in'], rows, 'No references found in bundle.')}</div>")

    if shared:
        rows = []
        for ref in shared:
            link = f"<a href='{esc(ref['url'])}'>{esc(ref['title'])}</a>" if ref["url"] else esc(ref["title"])
            rows.append([
                link,
                esc(ref["domain"]),
                esc(ref["published"]),
                esc(ref["tier"]),
                esc(ref["score"]),
                esc(grade(ref["score"])),
                esc(ref["used_in"]),
            ])
        sections.append(f"<div class='ref-group'><h3>Shared Market/Macro</h3>{table(['Source', 'Domain', 'Published', 'Tier', 'Ref. confidence', 'Grade', 'Used in'], rows)}</div>")
    return "".join(sections) or "<p class='empty'>Not found in bundle.</p>"


def build_reference_coverage_rows(data):
    grouped, _shared = group_references(data)
    retrieval_dt = parse_iso_date(data.get("retrieval_iso"))
    rows = []
    for ticker in data.get("tickers", []):
        refs = grouped.get(ticker, [])
        recent_refs = [ref for ref in refs if reference_is_recent(ref, retrieval_dt, 7)]
        domains = sorted({ref.get("domain") for ref in recent_refs if ref.get("domain")})
        count_ok = len(recent_refs) >= 10
        domain_ok = len(domains) >= 5
        status = "PASS" if count_ok and domain_ok else "FAIL"
        missing = []
        if not count_ok:
            missing.append(f"{10 - len(recent_refs)} more refs")
        if not domain_ok:
            missing.append(f"{5 - len(domains)} more domains")
        rows.append([
            esc(ticker),
            esc(len(recent_refs)),
            esc(len(domains)),
            esc(", ".join(domains) or "none"),
            f"<span class='status {'pass' if status == 'PASS' else 'fail'}'>{status}</span>",
            esc("; ".join(missing) or "meets floor"),
        ])
    return rows


def coverage_failures(data):
    grouped, _shared = group_references(data)
    retrieval_dt = parse_iso_date(data.get("retrieval_iso"))
    failures = []
    for ticker in data.get("tickers", []):
        refs = grouped.get(ticker, [])
        recent_refs = [ref for ref in refs if reference_is_recent(ref, retrieval_dt, 7)]
        domains = {ref.get("domain") for ref in recent_refs if ref.get("domain")}
        if len(recent_refs) < 10 or len(domains) < 5:
            failures.append({
                "ticker": ticker,
                "recent_refs": len(recent_refs),
                "distinct_domains": len(domains),
            })
    return failures


def narrative_failures(data):
    detail = data.get("detailed_analysis")
    required_top = [
        "executive_summary", "methodology", "ticker_analyses",
        "comparative_analysis", "scenario_methodology", "limitations",
    ]
    required_ticker = [
        "business_and_market_context", "current_setup", "bull_case", "base_case",
        "bear_case", "fair_value_reasoning", "price_band_reasoning",
        "quality_factor_reasoning", "positive_evidence",
        "negative_and_contrary_evidence", "key_risks",
        "catalysts_and_checkpoints", "evidence_gaps", "research_action_reasoning",
    ]
    if not isinstance(detail, dict):
        return [{"field": "detailed_analysis", "reason": "missing"}]
    failures = [
        {"field": f"detailed_analysis.{key}", "reason": "missing_or_empty"}
        for key in required_top if not detail.get(key)
    ]
    ticker_analyses = detail.get("ticker_analyses") or {}
    known_urls = {
        ref.get("url") for ref in (data.get("reference_confidence_table") or [])
        if isinstance(ref, dict) and ref.get("url")
    }

    def validate_evidence_block(value, path):
        block_failures = []
        if not isinstance(value, dict):
            return [{"field": path, "reason": "must_be_evidence_block"}]
        if not value.get("text"):
            block_failures.append({"field": f"{path}.text", "reason": "missing_or_empty"})
        evidence = value.get("cited_evidence")
        if not isinstance(evidence, list) or not evidence:
            block_failures.append({"field": f"{path}.cited_evidence", "reason": "missing_or_empty"})
        else:
            for index, item in enumerate(evidence):
                if not isinstance(item, dict):
                    block_failures.append({"field": f"{path}.cited_evidence[{index}]", "reason": "must_be_object"})
                    continue
                url = item.get("url")
                if not url:
                    block_failures.append({"field": f"{path}.cited_evidence[{index}].url", "reason": "missing"})
                elif url not in known_urls:
                    block_failures.append({"field": f"{path}.cited_evidence[{index}].url", "reason": "not_in_reference_confidence_table"})
                for key in ("published_iso", "source_title", "tier", "claim_supported"):
                    if not item.get(key):
                        block_failures.append({"field": f"{path}.cited_evidence[{index}].{key}", "reason": "missing"})
        return block_failures

    for ticker in data.get("tickers", []):
        section = ticker_analyses.get(ticker)
        if not isinstance(section, dict):
            failures.append({"ticker": ticker, "field": "ticker_analyses", "reason": "missing"})
            continue
        for key in required_ticker:
            if not section.get(key):
                failures.append({"ticker": ticker, "field": key, "reason": "missing_or_empty"})
                continue
            value = section[key]
            path = f"detailed_analysis.ticker_analyses.{ticker}.{key}"
            if key == "quality_factor_reasoning":
                if not isinstance(value, dict) or not value:
                    failures.append({"ticker": ticker, "field": key, "reason": "missing_or_empty"})
                else:
                    for factor, explanation in value.items():
                        failures.extend(validate_evidence_block(explanation, f"{path}.{factor}"))
            else:
                failures.extend(validate_evidence_block(value, path))
    for key in ("comparative_analysis", "scenario_methodology"):
        if detail.get(key):
            failures.extend(validate_evidence_block(detail[key], f"detailed_analysis.{key}"))
    return failures


def render(data, source_path):
    title = data.get("title") or "Stock Research HTML Report"
    tickers = ", ".join(data.get("tickers", []))
    halt_flags = ", ".join(data.get("halt_flags", [])) or "none"
    summary = table(
        ["Ticker", "Rank", "Current price", "Fair value band", "Risk score", "Confidence", "Action"],
        build_summary_rows(data),
    )
    current_prices = table(
        ["Ticker", "Status", "Price", "As of", "Source", "Reason"],
        build_current_price_rows(data),
    )
    bands = table(
        ["Ticker", "Price band", "Price range", "Probability", "Scenario source", "Implied return", "Return/risk", "Rationale"],
        build_band_rows(data),
    )
    indicators = table(
        ["Ticker", "Reliability", "Economic moat", "Structural stability", "Growth quality", "Risk score", "Confidence"],
        build_indicator_rows(data),
    )
    reference_coverage = table(
        ["Ticker", "Recent refs", "Distinct domains", "Domains", "Coverage", "Shortfall"],
        build_reference_coverage_rows(data),
    )
    references = table(
        ["Source", "Domain", "Published", "Tier", "Ref. confidence", "Grade", "Used in"],
        build_reference_rows(data),
    )
    references_by_ticker = build_references_by_ticker(data)
    action_rows = []
    for row in data.get("action_guidance", []):
        action_rows.append([
            esc(row.get("ticker")),
            esc(row.get("label")),
            esc(row.get("why")),
            esc(row.get("trigger_to_upgrade")),
            esc(row.get("trigger_to_downgrade")),
            esc(row.get("evidence_to_check_next")),
        ])
    actions = table(
        ["Ticker", "Action", "Why", "Upgrade trigger", "Downgrade trigger", "Evidence to check"],
        action_rows,
    )
    analysis = data.get("analysis") or data.get("coverage_note") or "Research-only output. Not investment advice."
    detailed_analysis = build_detailed_analysis(data)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17202a; --muted:#5d6673; --line:#d9dee7; --bg:#f7f8fa; --panel:#ffffff; --accent:#155eef; --warn:#9a6700; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--bg); }}
    main {{ max-width:1180px; margin:0 auto; padding:28px 20px 48px; }}
    header {{ margin-bottom:22px; }}
    h1 {{ margin:0 0 8px; font-size:28px; line-height:1.2; letter-spacing:0; }}
    h2 {{ margin:28px 0 10px; font-size:18px; }}
    h3 {{ margin:16px 0 8px; font-size:15px; }}
    h4 {{ margin:14px 0 6px; font-size:14px; color:#27364a; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px; color:var(--muted); }}
    .pill {{ border:1px solid var(--line); background:var(--panel); border-radius:999px; padding:4px 10px; }}
    .warn {{ color:var(--warn); border-color:#e8c16a; background:#fff8e6; }}
    .status {{ display:inline-block; font-weight:700; border-radius:999px; padding:2px 8px; }}
    .status.pass {{ color:#116329; background:#dafbe1; }}
    .status.fail {{ color:#82071e; background:#ffebe9; }}
    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }}
    .ref-group {{ margin:0 0 16px; }}
    .narrative {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:18px 20px; margin-top:20px; }}
    .narrative h2 {{ margin-top:0; }}
    .narrative-block {{ margin:12px 0 18px; padding-left:14px; border-left:3px solid #dbe7ff; }}
    .narrative p {{ margin:7px 0 12px; line-height:1.72; }}
    .narrative ul {{ margin:6px 0 12px; padding-left:24px; }}
    .narrative li {{ margin:5px 0; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:8px; background:var(--panel); }}
    table {{ width:100%; border-collapse:collapse; min-width:760px; }}
    th, td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ font-size:12px; text-transform:uppercase; color:var(--muted); background:#f0f3f7; }}
    tr:last-child td {{ border-bottom:0; }}
    a {{ color:var(--accent); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .empty {{ margin:0; color:var(--muted); }}
    footer {{ margin-top:28px; color:var(--muted); font-size:12px; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{esc(title)}</h1>
      <div class="meta">
        <span class="pill">Source: {esc(source_path)}</span>
        <span class="pill">Status: {esc(data.get("status", "unknown"))}</span>
        <span class="pill">Retrieval: {esc(data.get("retrieval_iso", "unknown"))}</span>
        <span class="pill">Tickers: {esc(tickers or "unknown")}</span>
        <span class="pill warn">Halt flags: {esc(halt_flags)}</span>
      </div>
    </header>
    <section><h2>Current Price</h2>{current_prices}</section>
    <section><h2>Summary Ranking</h2>{summary}</section>
    <section><h2>Price-Band Probabilities</h2>{bands}</section>
    <section><h2>Indicator Scores</h2>{indicators}</section>
    <section><h2>Reference Coverage</h2>{reference_coverage}</section>
    <section><h2>Reference Confidence</h2>{references}</section>
    <section><h2>References By Ticker</h2>{references_by_ticker}</section>
    <section><h2>Action Guidance</h2>{actions}</section>
    <section><h2>Analysis</h2><div class="panel">{esc(analysis)}</div></section>
    {detailed_analysis}
    <footer>Research only. Not investment advice.</footer>
  </main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict-coverage", action="store_true")
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    output = args.output or args.input.with_suffix(".html")
    failures = coverage_failures(data)
    narrative = narrative_failures(data)
    if failures and not args.allow_incomplete:
        print(json.dumps({
            "coverage_failures": failures,
            "detailed_analysis_failures": narrative,
        }, indent=2), flush=True)
        raise SystemExit(2)
    output.write_text(render(data, args.input), encoding="utf-8")
    if narrative and not args.allow_incomplete:
        print(json.dumps({
            "coverage_failures": failures,
            "detailed_analysis_failures": narrative,
        }, indent=2), flush=True)
        print(output)
        raise SystemExit(2)
    print(output)


if __name__ == "__main__":
    main()
