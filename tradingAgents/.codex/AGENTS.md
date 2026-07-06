# Codex Manifest — strict subset of SKILL.md (Claude Code skill)

This manifest describes the same `stock-research` skill for Codex harnesses.
The contract is the same; only the loader shape differs (Codex uses an
`AGENTS.md` sibling instead of `SKILL.md`).

## Capability

- `read` — read sources and prior bundles.
- `compute` — synthesize fair_value / forward_range.
- `write-confirm` — write to `.stock-research/` only after the head_manager
  approves the bundle (status != `dropped`).

## Claim Classes

- `factual` — cited numeric or factual statements (price, earnings, macro data).
- `interpretive` — synthesized judgments about what the data means
  (drivers, fair-value band rationale).
- `advisory` — presentational framing that is NOT investment advice
  (see DISCLAIMER.md).

## Tier Definitions (deterministic)

| Tier | Class                                            | Display? |
|------|--------------------------------------------------|----------|
| A    | Peer/primary: broker research, regulator filings, primary newswires, company IR/SEC filings | Yes |
| B    | Aggregators: Yahoo, Reuters, MarketWatch, MarketBeat, Bloomberg public mirror | Yes (secondary) |
| C    | Blogs, social, forums                            | No — suppressed |

## Recency Budgets (days)

| Data type      | Budget |
|----------------|--------|
| price          | 7      |
| drivers        | 7      |
| fundamentals   | 90     |
| fair_value     | 90     |
| forward_range  | 90     |
| macro          | 30     |

Tier-graded enforcement: tier-A over budget -> keep + flag
`[recency_violated: Nd over budget]` + tier downgrade to C. tier-B/C over
budget -> drop + log to `recency_log`.

## Citation Format

`[URL | retrieval_iso | source_title | tier]`

Every claim in every worker output bears this format. Tier-C citations are
recorded for audit but never displayed as supporting evidence.

## Conflict Resolution

±10% consensus threshold on the synthesis target. Within threshold -> recency
+ independence-weighted synthesis with reasoning_trace. Beyond threshold ->
tier-anchored bracket `[min(tier-A), max(tier-A)]` with `conflict: true`,
probabilities suppressed, outliers annotated `[outlier: ...]`.

## low_confidence

`low_confidence: true` is emitted when tier-A count == 0 for an output. The
output falls back to min/max of cited sources; never synthesized.

## Halt Conditions

Bundle is emitted as `status: "partial"` with `halt_flags` and
`omitted_outputs` populated. The skill never refuses outright.

## Stops

- No write outside `.stock-research/` without explicit user authorization.
- No tier-C as supporting evidence.
- No single-source major claim asserted as fact.
- No synthesis when tier-A disagreement > ±10%; bracket only.
- No advice (see DISCLAIMER.md).

## Commands (Codex invocation)

```
stock-research run <TICKER> [questions...]
stock-research show <run-id>
stock-research doctor <run-id> [--deep]
```

## Workers

`head_manager`, `fair_value`, `forward_range`, `drivers`, `macro`, `user_qa`,
`evidence_synthesizer`, `recency_checker`, `doctor`.

## Decision Package Fields

`forecastable_claims`, `lifecycle_assumptions`, `contrary_evidence`,
`owner_roles`, `follow_up`, `postmortem_required`. All six required.

## Cross-Run Accumulation

`follow_up` and `postmortem_required` accumulate across runs of the same
ticker. The head_manager reads prior bundles in `.stock-research/<TICKER>/`
and merges them.
