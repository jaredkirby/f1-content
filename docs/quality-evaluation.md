# Freeze a source-grouped quality protocol

The offline protocol commands prepare the development/held-out sample proposed
by [model selection](model-selection.md). They validate explicit sample membership,
current evidence hashes and a versioned rubric. They do not run models, import
human labels, measure parity, or promote a model. Existing
[model-evaluate](model-workflows.md#compare-quality-before-efficiency) remains the
feedback/cost ledger; this protocol does not replace it.

Use one selected event workspace. A protocol must match its exact event identity
and include at least one development and one held-out case. These minimum counts
check structure; they do not establish a representative or adequate evaluation.
All request and bound evidence files must be local to that workspace. Relative
`--request` paths resolve from the selected workspace; absolute paths within it
are also accepted. Commands read no credential and make no provider call.

```sh
./scripts/f1 --workspace examples/synthetic quality-preview \
  --request quality-protocol.json
```

The [fictional protocol](../examples/synthetic/quality-protocol.json) demonstrates
the complete schema. Its source groups, assignments and rubric are synthetic;
the example cannot supply production labels or approval. Preview is read-only.
To freeze an actual operator-reviewed protocol in a durable event workspace:

```sh
./scripts/f1 --workspace /absolute/path/to/event quality-freeze \
  --request research/evaluation/protocol.json
./scripts/f1 --workspace /absolute/path/to/event quality-check \
  --request runs/quality-protocols/ACTUAL_PROTOCOL_ID.json
```

`quality-freeze` saves a new exclusive receipt under
`runs/quality-protocols/<protocol_id>.json`. Its complete snapshot binds original
request bytes, `config/event.json`, rubric bytes and every case evidence file.
An existing ID cannot be overwritten or reused, including when its receipt is
stale or corrupt. Use a new ID for a changed protocol and retain the old evidence.
The save checks available storage reserve and rechecks bindings before publishing
complete receipt bytes. `--execute` is refused.

`quality-check` verifies the receipt's internal hash, canonical receipt location,
original request contents, selected config and all current evidence bindings.
Changed, missing or corrupt inputs fail closed. A frozen protocol becoming stale
does not authorize changing its receipt to pass. Hashes detect accidental changes;
local files cannot authenticate an operator or prevent deliberate replacement of
the whole receipt and its hashes.

## Schema and split decisions

The protocol uses `schema_version: "f1.quality_protocol.v1"`, a unique lowercase
`protocol_id`, exact `event_identity`, `rubric: {version, path, sha256}`,
`split_assignment: {kind: "operator_declared", reference: "..."}`, and `cases`.
Each case has a unique `case_id`, explicit `split` (`development` or `held_out`),
nonempty `source_group_ids`, and nonempty `evidence` path/SHA-256 bindings.
Versions describe the rubric the operator selected; the tool verifies its bytes,
not whether its criteria are useful. The declaration reference identifies the
operator's assignment decision; it is not an authenticated human approval.

Keep reposts, neighboring excerpts and derived observations from the same source
in one source group, even when their bytes differ. Multi-source cases list every
related group. Shared groups cannot cross splits. The validator also rejects
cross-split reuse of an evidence path or identical evidence content under different
filenames/groups. It cannot discover that two edited excerpts came from the same
source: the operator must declare that relationship accurately. Common protocol
rubric and selected config are bound separately from case evidence.

Unknown fields, duplicate JSON keys, nonfinite values, duplicated case IDs,
noncanonical paths and symlink evidence aliases are rejected. `label`, `outcome`,
human-review provenance and acceptance fields are intentionally unsupported in this
first protocol schema: they cannot be silently imported as approval. This slice
does not assess whether real human evidence already exists elsewhere; status is
`human_evidence_status: "not_assessed"` and `human_acceptance: "not_inferred"`.

## Remaining evaluation work

Freeze a real representative source-grouped sample after agreeing its rubric and
conditions. Obtain actual human-reviewed labels/preferences with source and reviewer
provenance, retain the reference and candidate model-work receipts, and execute
the agreed held-out evaluation without tuning on that set. Objective calibration,
accepted-result error rates and subjective editorial comparisons require those
real observations. This implementation supplies no label ingestion, evaluation
executor, parity thresholds, cross-event aggregation or promotion decision.
Important voice/model/default changes stay in the explicit human review loop.
