"""Schema for the ResearchBundle (output_schema)."""
from __future__ import annotations

LEGACY_BUNDLE_SCHEMA = {
    "type": "object",
    "required": [
        "run_id", "ticker", "generated_at", "status",
        "fair_value", "drivers", "macro_market_state", "forward_range", "user_qa",
        "decision_package", "citations", "recency_log", "halt_flags", "omitted_outputs",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "ticker": {"type": "string"},
        "generated_at": {"type": "string"},
        "status": {"enum": ["ok", "partial", "dropped"]},
        "fair_value": {
            "type": "object",
            "required": [
                "point", "band_low", "band_high", "synthesis_target",
                "mode", "tier_bracket", "conflict", "low_confidence",
                "citations", "reasoning_trace",
            ],
        },
        "drivers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "timestamp", "source", "claim", "retrieval_iso", "tier",
                    "recency_violated", "citation_format",
                ],
            },
        },
        "macro_market_state": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "indicator", "value", "source", "retrieval_iso", "tier",
                ],
            },
        },
        "forward_range": {
            "type": "object",
            "required": [
                "ranges", "mode", "modal_midpoint",
                "tier_anchor_low", "tier_anchor_high",
                "conflict", "low_confidence",
                "outliers", "reasoning_trace",
            ],
        },
        "user_qa": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "question", "answer", "sources",
                    "tier_summary", "recency_budget_type",
                    "evidence_tier", "citation_format",
                ],
            },
        },
        "decision_package": {
            "type": "object",
            "required": [
                "forecastable_claims", "lifecycle_assumptions",
                "contrary_evidence", "owner_roles",
                "follow_up", "postmortem_required",
            ],
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "url", "retrieval_iso", "source_title",
                    "tier", "claim_class", "capability",
                ],
            },
        },
        "recency_log": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "age_days", "budget_days", "tier", "action"],
            },
        },
        "halt_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["output", "flag", "reason"],
            },
        },
        "omitted_outputs": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}

MULTI_BUNDLE_SCHEMA = {
    "type": "object",
    "required": [
        "run_id", "status", "retrieval_iso", "tickers", "current_prices",
        "evidence_coverage", "fair_value", "forward_range",
        "band_probability_table", "quality_factors", "comparative_ranking",
        "action_guidance", "reference_confidence_table",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "status": {"enum": ["complete", "partial", "halted"]},
        "retrieval_iso": {"type": "string"},
        "tickers": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "current_prices": {"type": "object"},
        "evidence_coverage": {"type": "object"},
        "fair_value": {"type": "object"},
        "forward_range": {"type": "object"},
        "band_probability_table": {"type": "array"},
        "quality_factors": {"type": "object"},
        "comparative_ranking": {"type": "array"},
        "action_guidance": {"type": "array"},
        "reference_confidence_table": {
            "type": "array",
            "items": {"type": "object", "required": [
                "ticker", "url", "domain", "source_title", "published_iso",
                "tier", "used_in", "reference_confidence_score", "confidence_grade",
            ]},
        },
    },
}

BUNDLE_SCHEMA = {"anyOf": [LEGACY_BUNDLE_SCHEMA, MULTI_BUNDLE_SCHEMA]}
