# Explicit story contracts

A model plan can opt into a shared, hash-bound event/claim/numeric ledger. This is
an offline structural and arithmetic gate on explicit hosted text work. It does
not route models, perform inference implicitly, establish factual truth from
prose, approve a film, or change existing uncontracted plans.

## Plan and ledger

Add `story_contract` to an `f1.model_plan.v1` plan as a canonical workspace-relative
path/SHA-256 binding. Every text job in that plan must declare `contract_stage` as
`draft`, `critique` or `revision`, and its request must use
`response_format: {"type": "json_object"}`. Jev jobs keep their existing schema;
only text jobs receive the story contract. Critiques must depend on an earlier
contracted draft/revision. Explicit dependencies determine execution order.

The runnable [synthetic plan](../examples/synthetic/story-plan.json) binds a
[ledger](../examples/synthetic/story-ledger.json), a fictional source and a text
request. Preview it from the source checkout without inference:

```sh
./scripts/f1 --workspace examples/synthetic model-run --request story-plan.json
```

The ledger has these exact keys:

| Key | Meaning |
| --- | --- |
| `schema_version` | `f1.story_ledger.v1` |
| `event_id`, `event_binding` | Selected event ID and exact `config/event.json` binding |
| `event_identity` | Exact config fields `id`, `year`, `country_name`, `session_name`, `event_date`, `session_key`, `meeting_key` |
| `max_duration_seconds` | Finite JSON number, greater than zero and at most 300 |
| `sources` | 1–128 records with `id`, current file `binding`, nonempty `locator` |
| `numbers` | 0–256 records with `id`, `value`, `unit`, `source_ids`, optional `derivation` |
| `claims` | 1–256 records with `id`, `text`, `status`, `source_ids`, `numeric_ids` |

Identifiers are lowercase bounded slugs. Numeric values are decimal strings
with at most 18 integer digits and nine fractional digits, or `null` for unknown.
No exponent, floating-point coercion, rounding tolerance or nonfinite value is
allowed. Known numbers require source IDs. A derivation names an `operation`
(`add`, `subtract`, `multiply`, `divide`) and exactly two prior known number IDs
in `operands`. Decimal arithmetic must equal the recorded value exactly, and
operand source IDs must be retained. Addition/subtraction require matching units.
Division by zero and nonterminating results that do not exactly match the bounded
recorded decimal are rejected. Multiply/divide units require operator review.

Claim status is explicitly `supported`, `unknown` or `contradicted`. Supported
claims require current sources and known referenced numbers. Numeric source IDs
must also appear in their claim sources. These statuses are supplied, reviewed
ledger assertions; the validator cannot prove that a locator supports the prose.
Do not mark a claim supported merely because a model says so.

All source/event/ledger bytes are checked before transport and between jobs.
The same complete ledger, including unknowns, reaches draft, critique and revision
as untrusted evidence data. Prior accepted model results remain advisory data.
The actual expanded requests and ledger/source bindings are retained in model-work
evidence. Preview includes contract instructions in request size validation;
dependency expansion is checked again before its own provider call.

## Structured outputs

All stages return JSON with exact common keys: `schema_version` equal to
`f1.story_output.v1`, selected `event_id`, current `ledger_sha256`, exact `stage`,
and `unresolved`. `unresolved` is the sorted list of `claim:<id>` for every unknown
or contradicted claim and `number:<id>` for every unknown number. Missing or
invented unresolved IDs fail; unknowns cannot silently become narration support.
Duplicate JSON keys, unknown fields and stale identities are rejected.

Draft/revision additionally require `title` (up to 200 characters), `hook` (500),
and 1–32 `segments`. Every segment has exact keys:

```json
{
  "id": "segment-1",
  "start_seconds": 0,
  "end_seconds": 12,
  "narration": "In this fictional fixture, A beat B by 0.200 seconds.",
  "claim_ids": ["result"],
  "source_ids": ["classification"],
  "numeric_values": {"gap": "0.200"}
}
```

Timings must be finite, positive-length, contiguous from zero, within the ledger's
duration limit. Each segment must bind at least one supported claim. Its sources
must equal the union of those claims' source IDs; `numeric_values` must match the
exact union of their numeric IDs and original decimal strings. Narration is
bounded to 4,000 characters per segment. These timing checks validate the proposed
outline, not actual spoken duration or renderer compatibility. Title/hook remain
editorial framing and need factual review when they assert a fact.

Critiques additionally require `verdict` (`pass`, `revise`,
`insufficient_evidence`) and up to 64 `issues`. Each issue has `claim_id` (current
ID or null), `segment_id` (an accepted directly dependent draft/revision segment
ID or null), `category` (`factual`, `timing`, `source_binding`, `narrative`) and
`comment` (up to 4,000 characters). A `pass` cannot contain issues. All verdicts
remain advisory; a revision may proceed after a structurally valid critique and
must meet its own draft contract. Non-passing critiques appear in the review queue.

## Failure and review

After a provider result passes the hosted adapter, the runner saves a separate
`<job-id>-story-validation.json` receipt under `runs/model-plans/<plan-id>/`.
It binds job/stage, ledger, provider receipt and output hash. A failed story gate
marks the execution job `story_contract_failed`, stops dependencies and retains
the provider's complete `output_text`, model-work result file, observed usage and
known charge. The raw provider receipt is unchanged: successful paid generation
and structural eligibility are separate facts. Provider-level failures retain
existing provider receipts/hashes and stop as before; this layer does not add raw
HTTP-body capture or retries. Unknown billing stays unknown.

Every plan/work ID stays single-use, including failed or interrupted work.
`model-review` requires completed current evidence, revalidates the story outputs
and verifies attached validation receipts before exposing structured outputs.
It never infers human acceptance. Satisfying these constraints does not prove
that free prose matches a source, the film has been watched, a voice is wanted,
a model meets held-out quality standards, or publication is authorized. Keep
[factual release gates](workflow-design.md), [mobile checks](mobile-review.md) and
[human feedback](model-workflows.md) separate.
