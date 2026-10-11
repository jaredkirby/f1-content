# OpenRouter work plans

Use OpenRouter for native Jev decisions and DeepSeek story drafts in one explicit,
bounded workflow. Model results remain advisory until editorial review.
The [contract research](openrouter-jev-integration-research.md) records primary
sources, exact model identities and rate assumptions checked on 10 October 2026.

## Routes and boundaries

| Work | Model | Endpoint | Serving provider |
|---|---|---|---|
| Typed choices, scores, probabilities | `typesafe/jev-1.13` | `/api/v1/systemone` | `typesafe` only |
| Grounded story draft | `deepseek/deepseek-v4.1-flash` | `/api/v1/chat/completions` | `deepseek` only |

Neither route allows provider fallback or automatic retry. Jev is the actual
TypeSafe model, not an LLM emulation or the Jev Router product. It is text-only;
transcripts and reviewed observations must precede it. No downloadable open Jev
weights were verified. This integration does not satisfy the separate open-model
quality-promotion goal, add vision/voice providers or approve a finished film.

## Prepare and preview

```sh
./scripts/f1 --workspace /absolute/path/to/event prepare-jev
./scripts/f1 --workspace /absolute/path/to/event jev-infer --request requests/claim.json
./scripts/f1 --workspace /absolute/path/to/event model-run --request requests/plan.json
```

Preparation writes content-addressed packets and an index under
`data/processed/jev_requests/`. Each matched timeline claim gets a separate packet;
it is not a full sentence-by-sentence script audit. The packet contains primary
excerpts/locators and available transcript/observed-frame evidence. Missing evidence
must produce abstention, not confidence inferred from the repeated claim.
Older index contents are retained in `history/`.

All request, evidence and plan paths resolve inside the selected workspace.
The plan schema is `f1.model_plan.v1`, with `event_id`, unique `plan_id` and
`comparison_id`, `event_binding`, `max_calls`, positive `budget_usd`, and `jobs`.
Bindings are `{ "path": "event-relative/path", "sha256": "64 lowercase hex digits" }`.
`event_binding` must bind `config/event.json` exactly.

Each job declares `id`, `kind` (`jev` or `text`), a request binding, one or more
evidence bindings, `task`, `format`, `prompt_version`, `rubric_version` and optional
`depends_on`. Dependencies must name earlier jobs; only text jobs consume them.
Use a new identity for each deliberately approved run. The runnable synthetic
fixture in [the CLI tests](../tests/test_model_jobs.py) demonstrates the complete
shape, execution, stale-evidence rejection and review.

Preview validates every input without a credential, network call or execution
directory. There are at most 64 jobs, and the total budget must cover the sum of
their conservative full-context cost ceilings. Byte limits are not token counts.

## Execute once and review

After saving a key in [macOS Keychain](credentials.md), or configuring
`OPENROUTER_API_KEY` securely in the executing process:

```sh
./scripts/f1 --workspace /absolute/path/to/event model-run \
  --request requests/plan.json --execute --timeout-seconds 300
./scripts/f1 --workspace /absolute/path/to/event model-review --request requests/plan.json
./scripts/f1 --workspace /absolute/path/to/event model-evaluate --comparison-id qualifying-claims-v1
```

Keep credentials out of arguments, committed files and chat. The optional phone
helper supports `verify-plan` and `execute-plan` through hidden stdin; its private
Site operation binds the plan hash, budget and maximum calls. The helper passes
`--expected-plan-sha256` to Python so replacement after key pickup cannot change
the authorized work. When persistent storage is selected, both sides must agree and the helper saves
the key to login Keychain before execution. Otherwise the key remains transient.
The encrypted handoff is cleared when consumed. See [credential storage](credentials.md).

The runner saves intent before calling the provider, carries prior accepted
results into the draft as untrusted advisory data, and saves immutable model-work
receipts. A failed Jev call stops the dependent draft. An existing execution cannot
be rerun automatically, including when billing or completion is uncertain.
Inspect retained evidence before authorizing a new identity.

`model-review` checks current plan, evidence and model-work hashes before exposing
typed answers, drafts and a review queue. Its 0.8 confidence threshold is an
uncalibrated triage aid, never a release or acceptance rule. Local Jev acceptance
requires distributions/confidence and matching score legends even where OpenRouter's
wire schema permits their omission. A billed response can therefore be unusable.

Charges reported by OpenRouter, token-based estimates and unknown costs stay
separate. A partial bill is not reported as a complete run total. Technical success
and model confidence do not record human approval or trigger a render/publication.


Reasoning models share `max_tokens` between reasoning and visible output. In the
live pilot, 3,910 reasoning tokens consumed most of a 4,096-token allowance and the
story was unfinished. Preserve the failed receipt and its charge; increasing the
allowance requires a new reviewed request and budget. Reuse accepted Jev receipts
as bound evidence rather than spending on the same claim judgments again.

## Optional story ledger gate

For draft/critique/revision work, an explicit plan can bind one immutable
`story_contract` ledger and label every text job's `contract_stage`. The
[story contract guide](story-contract.md) defines exact event/source/claim/numeric
bindings, Decimal arithmetic, unresolved facts, bounded segment timing and the
constrained critique schema. The same ledger reaches all text stages.

A structurally invalid story stops dependent generation even when the provider
successfully produced and billed JSON. Separate bound validation receipts retain
the failure and original provider output; observed charges and unknown billing
remain distinct. `model-review` rechecks the gate and exposes structured results
only for a current completed plan. Existing plans remain backward compatible.
This gate does not prove narration truth or supply human acceptance.
