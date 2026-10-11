# Record human quality and model work

These commands implement the first steps of the [model-selection policy](model-selection.md):
explicit feedback, provenance, route advice, offline evaluation and a hosted text
adapter. The [OpenRouter work-plan guide](openrouter-workflow.md) adds native Jev
judgments and dependent story drafting with explicit budgets. They preserve the distinction between local release and human acceptance.
Run every command against one explicit event workspace. Private records stay there.

These commands describe the combined `main` checkout. Native OpenRouter Jev,
bounded job plans and consent-bound macOS Keychain storage are documented in
the [work-plan guide](openrouter-workflow.md) and [credentials guide](credentials.md).
See [project state](project-state.md) for implemented capabilities and acceptance gaps. The explicit [live feed](live-feed.md)
is a separate subscription-backed path, not the hosted API adapter below.

## Start with the subscription reference

```sh
./scripts/f1 --workspace /absolute/path/to/event model-route \
  --task story_script --subscription-status available
```

The availability flag reports what the operator observed; the command does not
check authentication or contact a provider. Deterministic operations route to
local code. Model work routes to Codex subscription advice when available;
limited, unknown or unavailable access asks for a human decision. It does not
change a model picker, consume a reset or call a model.

Create the reference script/edit through the supported signed-in Codex session.
Keep its actual output in the selected workspace. Record observed model/settings
and a session reference where available; unknown values remain null. Import an
operator-authored model-work JSON document:

```sh
./scripts/f1 --workspace /absolute/path/to/event model-import \
  --request /absolute/path/to/event/work-request.json
```

The document uses `schema_version: "f1.model_work.v1"`, unique lowercase
`comparison_id`/`work_id`, task and format, exact `event_identity`, explicit
`prompt_version`/`rubric_version`, preference version/binding, and path/SHA-256
arrays for inputs and evidence. Each actual attempt has its own status, observed
model/access/settings, output/provenance bindings, declared eligibility and usage.
The complete worked shape appears in [the CLI regressions](../tests/test_model_cli.py).
Requests for import must be inside the selected workspace. Immutable receipts
are saved under `runs/model-evaluations/<comparison>/<work>.json` and cannot be
overwritten. Changing referenced bytes makes their evidence stale.

Usage requires explicit actual-or-null values for input/output/reasoning tokens,
actual and estimated USD cost, machine seconds and human revision seconds.
`token_scope` is attributable, account_shared or unknown; `cost_source` describes
actual cost, with unknown used when actual cost is null. Provider estimates belong
in `estimated_cost_usd`. Account-wide usage is not an attributable task charge.
An operator declaration is retained as such; import is not independent proof of
provider execution or factual eligibility.

## Record preferences and review one finished output

Use `preference-record --request PATH` for an explicit instruction, then
`preference-status` to read its current version. The request shape is:

```json
{
  "event_id": "REPLACE_WITH_SELECTED_EVENT",
  "source": {"kind": "human", "reviewer": "user", "reference": "REPLACE_WITH_EXPLICIT_INSTRUCTION_REFERENCE"},
  "key": "primary-experience",
  "instruction": "REPLACE_WITH_VERBATIM_HUMAN_INSTRUCTION",
  "scope": {"kind": "project", "target": "f1-content"},
  "source_feedback_ids": []
}
```

The placeholders are not valid operational feedback. Supply actual event/source
values and exact user text. Scope may be project, event, format or one output.
Only an explicit human instruction becomes a confirmed preference. The current
project brief already calls for grounded storytelling, vertical phone consumption
and single-output approve/reject feedback; capture only instructions actually given
when creating a private workspace preference record.

Before showing an edit, capture its current `outputs/manifest.json` SHA-256 and
the exact version. Present one output for approve/reject comments; A/B is reserved
for substantially different directions. Record the actual response:

At the early pilot stage, include the version-bound mobile web destination in
testing and handoff, following [mobile review](mobile-review.md). Timestamped Site
notes and feedback in the existing chat are equally valid human input. Technical
browser success is not a quality approval.

```json
{
  "event_id": "REPLACE_WITH_SELECTED_EVENT",
  "manifest_sha256": "REPLACE_WITH_OBSERVED_MANIFEST_SHA256",
  "source": {"kind": "human", "reviewer": "user", "reference": "REPLACE_WITH_EXPLICIT_FEEDBACK_REFERENCE"},
  "outcome": "approved",
  "comments": "REPLACE_WITH_VERBATIM_HUMAN_COMMENTS",
  "scope": {"kind": "output", "target": "REPLACE_WITH_SAME_MANIFEST_SHA256"},
  "model_runs": [],
  "usage": {"device": "phone", "observed_segment": null, "revision_minutes": null}
}
```

Use `rejected` when rejected, or `not_reviewed` when explicitly recorded that way.
Device/segment/revision context is optional and must reflect actual feedback.
`model_runs` may link immutable model receipts as `{path, sha256}`. This is explicit
attribution, not proof that a particular model caused the final quality. Omit
`preference_version` to capture the current confirmed version, or supply that exact
version. An explicit stale version is rejected.

```sh
./scripts/f1 --workspace /absolute/path/to/event feedback-record --request PATH
./scripts/f1 --workspace /absolute/path/to/event feedback-status
```

Capture verifies current manifest bytes, event identity, videos, companions and
EDL. The ledger at `runs/feedback.jsonl` retains original comments, preferences and
corrections; the current view is `outputs/human-feedback.json`. A changed/missing
file, stale model link, invalid ledger or absent feedback supplies no approval.
`correction_of` may name an earlier feedback ID for the same current output set;
historical versions stay intact. Correcting a historical version after the current
set changed is not supported by this first slice.

The retained pre-versioned Sprint can capture observed companion/EDL hashes under
its controlled compatibility rule. That records human experience without claiming
new release gates passed. All other new manifests require declared versioned
output/companion/EDL bindings. The ledger detects accidental edits; a local file
cannot authenticate a human or prevent replacement/truncation of all history.

`report` now displays current human-review status beside the local films,
separately from technical QA. It derives the status from current evidence rather
than trusting a cached view. `finalize` continues to perform local release checks;
it does not infer or require subjective approval.

## Compare quality before efficiency

```sh
./scripts/f1 --workspace /absolute/path/to/event model-evaluate --comparison-id pilot
```

The report joins immutable model work and explicit human review. It preserves
comments, failed/rejected attempts, unknowns and stale/corrupt evidence, and groups
by task, format, model and settings. Distinct reviewed output versions supply the
acceptance denominator; several linked model attempts do not inflate it. Legacy
observed companion changes are distinguished even if their manifest text is unchanged.

The latest human decision for an exact output governs every comparison previously
attributed to it, even if the new comment omits model links. Historical operator
attribution is flagged explicitly. A later rejection cannot leave an earlier
comparison approval active. Interrupted execution intents/raw provider evidence
without a final work receipt are reported separately as incomplete execution
evidence; they make headline totals unknown and do not fabricate attempts.

Actual total/cost per accepted output is null when cost is incomplete, and cost per
accepted output is null with zero acceptances. Known subtotals and provider estimates
are shown separately. Time totals are recorded effort sums, not observed wall time
to acceptance. Eligibility declarations stay separate from human approval. The
report performs no model promotion and cannot establish quality parity from a
small or synthetic sample.

## Preview a hosted open-model request

The [provider research](hosted-provider-research.md) describes exact model IDs,
the official endpoint, dated rates and response limits. The first adapter supports
text requests to OpenRouter with `deepseek/deepseek-v4.1-flash`;
video/image/audio uploads and tool execution are outside
this contract. Inputs and model text remain untrusted data.

This fictional example performs no inference and writes no result:

```sh
./scripts/f1 --workspace examples/synthetic model-infer \
  --request examples/synthetic/hosted-request.json
```

Default reasoning is explicitly high, and received reasoning text is excluded.
Verified effort choices are low/high/max, or reasoning may be explicitly disabled.
Unsupported settings and conflicting reasoning forms fail before a call.
The request disables context compression; observed fallback or transformations
fail the output contract.

Preview reports the sent-payload hash and a conservative cost ceiling: full listed
context at the dated uncached input rate plus capped output. It is not a predicted
token count or settled bill. Review current provider prices and account/input scope
before a real execution. Its API is separately billed from the Codex subscription.

An explicitly authorized execution requires a unique comparison/work ID, one
format, actual prompt/rubric versions, referenced event evidence and a budget that
covers the displayed ceiling:

```sh
./scripts/f1 --workspace /absolute/path/to/event model-infer --request PATH \
  --execute --budget-usd AUTHORIZED_BUDGET --comparison-id pilot --work-id candidate-1 \
  --format vertical --task story_script --prompt-version ACTUAL_VERSION \
  --rubric-version ACTUAL_VERSION --evidence research/event/event_bundle.json
```

An explicit `OPENROUTER_API_KEY` takes precedence; macOS execution can otherwise
read the dedicated [login-Keychain item](credentials.md). Previews read neither; credentials are not CLI values or receipt fields. One request is sent
to OpenRouter’s fixed HTTPS Chat Completions endpoint. The initial route is pinned
to the `deepseek` serving provider, with provider fallbacks disabled and supported
parameters required. Redirects, model fallback and client retries are refused.
The output-token, byte, time and preflight-budget limits remain bounded;
local checks cannot prevent an unexpected provider billing error or price change.

For mobile key entry, use the private [temporary handoff](mobile-review.md#supply-an-openrouter-key-from-a-phone).
It hands a key to the local process without exposing it in chat. An authorized
longer request may use `--timeout-seconds 300`; the CLI default is 120 and values outside
0.001–300 seconds fail before execution. Intent and model-work settings record the
transport timeout; it does not authorize retries or an additional charge.

Before the request, the CLI checks storage reserve and saves input/evidence hashes
and execution intent. It saves provider success/failure evidence, validated usage,
raw request/response hashes and any generated text in a unique `.assets` directory,
then imports a provider-neutral receipt. A saved intent without a final receipt is
an interrupted operation with unknown execution/charging state. Inspect it before
retrying; reuse of that work ID is refused. Successful transport starts with
eligibility `not_reviewed` and no human approval.

Valid `usage.cost` is retained as an OpenRouter-reported USD-credit charge. It
becomes actual request cost only when `is_byok` is explicitly false; BYOK or
missing billing scope leaves the full actual cost unknown. Dated peak-rate
estimates stay separate. Credit-purchase fees are outside the inference charge.
If inputs change during execution, the raw
provider evidence remains but a valid model-work import cannot be claimed.

## Verification and next quality decision

The regressions use fictional files and synthetic HTTP responses. They establish
workflow behavior, not live model quality, real phone playback or provider reliability.
The next production decision is a bounded reference/candidate pilot on the same
approved evidence, followed by the user's review of a vertical edit. Voice and
model promotion remain explicit human decisions; the all-open-model quality goal
is still gated by those results.
