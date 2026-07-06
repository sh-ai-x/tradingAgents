---
name: stock-research
description: |
  Evidence-backed stock research. Takes a ticker + optional research questions
  and emits a five-output research bundle (fair value, drivers, macro snapshot,
  6-month forward range, user Q&A) with inline citations, tier-classified
  sources (A/B/C), recency budgets, and conflict-resolution rules. Persisted
  as JSON for cross-date comparability. No investment advice — research only.
version: 1.0.0
capability: [read, compute, write-confirm]
claim_class: [factual, interpretive, advisory]
tier_definitions:
  A: "Peer/primary — broker research, regulator filings, primary newswires, company IR/SEC filings."
  B: "Aggregators — Yahoo Finance, Reuters, MarketWatch, MarketBeat, Bloomberg public mirror."
  C: "Blogs, social media, forums — never displayed as supporting evidence; always suppressed."
recency_budget_days:
  price: 7
  drivers: 7
  fundamentals: 90
  fair_value: 90
  forward_range: 90
  macro: 30
citation_format: "[URL | retrieval_iso | source_title | tier]"
tier_a_disagreement_threshold_pct: 10
bundle_root: ".stock-research"
bundle_path_template: ".stock-research/{ticker}/{iso_datetime}.json"
stops_before:
  - "Acting on the bundle as investment advice (DISCLAIMER.md)."
  - "Modifying files outside .stock-research/ unless the user explicitly authorizes."
  - "Citing tier-C sources as supporting evidence (always suppressed)."
  - "Asserting a major claim with fewer than two independent sources without [single_source] flag."
  - "Synthesizing fair_value or forward_range when tier-A disagreement exceeds +/-10% -- emit bracket only."
required_outputs:
  - fair_value
  - drivers
  - macro_market_state
  - forward_range
  - user_qa
commands:
  - name: run
    pattern: "/stock-research <TICKER> [questions...]"
    description: "Execute a new research run for a ticker."
  - name: show
    pattern: "/stock-research show <run-id>"
    description: "Re-render a prior bundle from disk without re-execution."
  - name: doctor
    pattern: "/stock-research doctor <run-id> [--deep]"
    description: "Validate a prior bundle; default fast mechanical, --deep = full audit."
---

# Stock Research Skill

The skill runs an Ouroboros-style elicitation interview, then orchestrates
worker outputs to produce a persisted ResearchBundle.

## Invocation

```
/stock-research AAPL "Why did it drop in March 2026?"
/stock-research show 2026-07-07T10-15-00Z_AAPL
/stock-research doctor 2026-07-07T10-15-00Z_AAPL
```

## Doctrine (read first)

1. **No invented numbers.** Every figure is cited with `[URL | retrieval_iso |
   source_title | tier]`. If a figure cannot be cited, the worker returns
   `not_found_in_budget` with the search terms attempted.
2. **Recency budgets are hard.** A claim about price older than 7 days, drivers
   older than 7 days, fundamentals / fair value / forward range older than 90
   days, or macro older than 30 days must be either flagged
   `[recency_violated: Nd over budget]` (tier-A -> keep + downgrade display to C)
   or dropped (tier-B/C -> drop + log to `recency_log`).
3. **Independence.** Major claims require >= 2 independent sources. A single-
   source major claim is `[single_source]` and never asserted as fact.
4. **Conflict resolution.** When tier-A sources disagree on a synthesis target
   by more than +/-10%, do not synthesize. Emit a tier-anchored bracket
   `[min(tier-A), max(tier-A)]`, set `conflict: true`, suppress probabilities,
   annotate outliers `[outlier: ...]`. The bracket is the output.
5. **Tier-C is invisible.** Tier-C sources are never displayed as supporting
   evidence. If a claim has only tier-C support, it is suppressed and the
   user is told `not_found_in_budget`.
6. **low_confidence** = true when tier-A count for the output == 0. Fall back
   to min/max of all cited sources; never pretend to synthesize.
7. **user_qa is its own worker.** It is never fed into fair_value or
   forward_range synthesis. The user_qa worker decides its own confidence per
   question.

## Stops

- Never write outside `.stock-research/` without explicit user authorization.
- Never cite tier-C as supporting evidence.
- Never assert a single-source major claim as fact.
- Never synthesize when tier-A disagreement > +/-10%; bracket only.
- Never refuse outright on partial-data -- emit a partial bundle with
  `halt_flags` and `omitted_outputs` populated.

## Workers

- `head_manager` -- elicitation interview, halt checks, bundle composition.
- `fair_value` -- point + +/- band, independent computation, cross-checked vs
  forward-range midpoint.
- `drivers` -- structured event list (timestamp/source/claim/tier), no prose.
- `macro` -- flat snapshot table rows, no prose.
- `forward_range` -- 6-month ranges summing to 1.0, evidence-backed.
- `user_qa` -- answers to user research questions, own confidence.
- `evidence_synthesizer` -- recency + independence weighting, conflict detection.
- `recency_checker` -- applies tier-graded recency budget enforcement.
- `doctor` -- mechanical (default, <= seconds) and `--deep` (full audit) modes.

## Halt Conditions

If any worker returns `halted` with a reason, the bundle is emitted as
`status: "partial"` with the dropped outputs listed in `omitted_outputs` and
each dropped output recorded in `halt_flags` with a flag string
(e.g. `[macro_stale]`). The skill never refuses; it degrades explicitly.

## Doctor

`/stock-research doctor <run-id>` resolves the run file
(`.stock-research/<TICKER>/<ISO>.json`) and validates:

- Mechanical (default, <= seconds): tier classification present, recency
  budgets met, >=2 sources per major claim, citation format, schema.
- `--deep`: above + Decision Package field validity + cross-output rule
  application. Shows progress as it walks each rule.

Doctor never re-executes workers. It reads the persisted bundle only.

## Persistence

Every run writes to `.stock-research/<TICKER>/<ISO_DATETIME>.json`. The
ISO datetime uses `:` replaced by `-` for filesystem safety. Stdout shows a
compact summary pointer only. `/stock-research show <run-id>` re-renders from
file. `follow_up` and `postmortem_required` accumulate across runs of the
same ticker -- the head manager reads prior bundles in
`.stock-research/<TICKER>/` and merges them.
