# Model selection, output quality and efficiency

Reviewed 2026-10-10 (America/Los_Angeles). This review establishes project policy
and a proposed evaluation workflow. It does not install a model, change the global
Codex configuration, implement a router or collect feedback automatically.

The user's feedback defines output quality. Preserve factual, identity, provenance
and release gates as prerequisites, then optimize for the user's acceptance and
preferences. Optimize usage, money and elapsed time only within that quality
standard. Use Codex through the ChatGPT subscription first; move toward open models
served by an API inference provider one demonstrated capability at a time.

The confirmed brief is **grounded analysis with clear storytelling, primarily
consumed vertically on a phone**. Default feedback is one output for approval or
rejection with comments. Offer A/B only for substantially different directional
decisions. Open models should use quality hosted inference at a good price;
local model serving is not the target.

## Findings, ordered by impact

| Priority | Finding and evidence | Effect on output | Required improvement |
|---|---|---|---|
| High | `finalize()` checks technical, editorial, visual and audio receipts, but records `user_playback_acceptance` as not inferred ([code](../f1_pipeline/finalize.py)). Both inspected deliveries have that state | A local delivery can pass without knowing whether the user likes the story, voice, pacing or visuals | Record hash-bound human feedback separately. A local finalization may remain a technical milestone; user acceptance and model promotion require explicit human review |
| High | Codex research/editorial roles have no per-output model, reasoning, prompt or usage receipt ([roles](../workflows/agents.json), [decisions](../f1_pipeline/analyze_session.py), [stage receipts](../f1_pipeline/harness.py)) | Existing acceptance cannot be attributed to a model/configuration, so quality or efficiency rankings would be speculation | Capture model provenance, evidence inputs, configuration, attempts and human revision time for every comparison |
| High | Both analysis paths use researched rankings; neither reads Jev inference receipts. `prepare()` sends only the first matched event summary as `editorial_claim` for each source ([preparation](../f1_pipeline/jev.py), [Sprint](../f1_pipeline/analyze.py), [Qualifying](../f1_pipeline/analyze_session.py)) | Paying for all prepared requests would not improve the current story selection. A source-wide claim check does not cover every narration sentence | Keep Jev optional/advisory. If evaluated, make one claim-plus-evidence decision per claim; add an explicit validated consumer before using results downstream |
| Medium | Saved local configuration uses `gpt-6.1-sol` with `xhigh` reasoning; the role file has no task-specific routing | Extra-high reasoning may be spent on repeatable extraction or reformatting without demonstrated benefit | Retain this configuration as the initial reference. Compare a lower effort or Luna on bounded tasks before promoting a cheaper route |
| Medium | Narration uses `say`, Samantha and 172 words/minute, with those settings in the cache key ([renderer](../f1_pipeline/render.py)) | A text-model upgrade cannot resolve an unwanted voice, pronunciation or delivery style | Include listening comparisons and pronunciation feedback. Replacing proprietary system speech is part of the open-model goal |
| Medium | Metadata labels are keyword rules; contact sheets sample 12 frames ([catalog](../f1_pipeline/catalog.py)) | Misleading captions and unseen action require observation. Text classifiers cannot establish footage content | Evaluate vision separately on known intervals; keep full playback and sampled observations distinct |
| Medium | Jev efficiency/calibration metrics are proposed in [Jev research](jev.md), with no executed F1 evaluation | Provider prices and confidence distributions cannot establish accepted-output efficiency | Measure quality, accepted-result errors, rework, usage and latency on the same frozen cases |

These are workflow gaps, not measured claims that an existing film is poor. No
film was watched or new model inference performed during this review.

## What is implemented and what was observed

Discovery, event research and editorial choices are Codex-assisted activities.
`workflows/agents.json` is declarative: the Python runner does not launch agents,
discover the web, route models or invoke Jev. Collection, hash checks, asset
deduplication, reviewed-interval checks, arithmetic, rendering and release checks
use local code. Keep those deterministic operations in code.

The optional adapter pins Jev's host/model, validates distributions, refuses
redirects, records request/response hashes and token usage, and bounds overload
retries ([adapter](../f1_pipeline/jev_adapter.py)). Those are good provider
contracts. They test transport/integrity, not output quality. Jev is text-only;
its provider currently lists $0.042 per million input tokens and free output
tokens. That price alone is no reason to add it to production. [TypeSafe models](https://docs.typesafe.ai/models).

A bounded read-only audit inspected the retained root Sprint and explicit
`events/2026-singapore-qualifying` workspace:

| Existing local records | Sprint | Qualifying |
|---|---:|---:|
| Delivery videos | 2 | 2 |
| Recorded technical QA status | passed | passed |
| Recorded actual Jev inference | false | false |
| Prepared Jev requests | 13 | 23 |
| Total prepared JSON bytes | 141,220 | 396,971 |
| Human playback acceptance | not inferred | not inferred |

Those request sizes are bytes, not tokens or a bill estimate. All five questions
are bundled per source, but the prepared requests do not establish that any were
submitted. Delivery/QA summaries are existing receipts, not fresh film validation.
The inspected decision/delivery documents do not contain model usage or a human
preference ledger; the proposed feedback paths below are absent. This does not
establish whether feedback exists in another chat or application.

Private audit hashes and local configuration/hardware observations are retained
in `runs/model-selection-review/2026-10-10/audit.json`. The source review began at
Git revision `692049f` with a clean tracked working tree.

## Subscription-first selection policy

The [declarative model policy](../workflows/model-policy.json) records the order
and human checkpoints. It is guidance for the supervising human/Codex session,
not a runtime router.

1. Apply deterministic gates and retrieve a small, sufficient evidence packet.
   Do not spend model usage on arithmetic, hashes or exact bounds checks.
2. Use the existing ChatGPT-signed-in Codex session for synthesis, script/edit-plan
   work and revisions. Establish a reference output before optimizing the model.
3. Compare cheaper subscription configurations for bounded work. Use a hosted open
   model as a shadow candidate within an authorized provider/budget/data scope. Neither
   becomes the production default until evaluated against the reference.
4. Use another model/provider API only for a specific failed quality criterion,
   missing modality/capability, or an approved comparison. Record the reason,
   input scope and spending limit; preserve the actual provider identity.
5. If subscription access is exhausted or unavailable, preserve work and surface
   the choice to wait or use an already approved route. Never silently purchase
   credits, consume a reset, switch billing or lower quality.

`codex login status` currently reports ChatGPT sign-in. OpenAI documents separate
ChatGPT subscription access and API-key billing. Subscription use is limited and
shares account usage; it is not free/unlimited API access. Use official clients
and their supported auth paths. Do not extract subscription tokens for a generic
provider adapter. [Authentication](https://learn.chatgpt.com/docs/auth),
[subscription pricing and usage](https://learn.chatgpt.com/docs/pricing).

The following are initial comparison candidates, not a measured F1 leaderboard.
Availability must be verified in the current account/client. OpenAI describes
Sol for repeated complex work, Astra for the hardest workflows and Luna for
clear repeatable tasks. [Official OpenAI model guidance](https://learn.chatgpt.com/docs/models).

| Work | Initial subscription reference | Efficiency candidate | Escalation trigger |
|---|---|---|---|
| Evidence extraction, metadata normalization, structured summaries | Saved Sol configuration | Sol at lower effort; Luna High | Omitted citations, wrong session, incomplete records or failed schema |
| Cross-source reconciliation and research synthesis | Saved Sol configuration | Sol at lower effort on frozen cases | Unresolved contradictions requiring judgment; try Astra if available and useful |
| Angle, hook, narration, edit plan and important revisions | Saved Sol configuration plus user brief | Lower effort only after user comparison | User rejection or demonstrated difficulty; try stronger subscription capability first |
| Claim checking | Source retrieval and deterministic links, then independent review | Bounded Sol/Luna or evaluated open classifier | Contradiction or insufficient evidence routes to review, not a forced answer |
| Footage, timing and caption congruence | Reviewed actual intervals; a vision-capable review when needed | Open vision candidate on the same observed frames | Unseen action or ambiguous timing requires actual interval inspection |
| Narration voice | Current Samantha output as a listening reference | Open TTS candidate | User dislikes voice, prosody, pronunciation or intelligibility |

A model name is insufficient provenance for Codex-assisted outputs. Retain the
observed model, reasoning/speed settings and run/session reference where available;
mark unavailable fields unknown rather than infer them from the global default.

## Human checkpoints and feedback

Routine deterministic work can proceed autonomously. Bring the user concrete
choices at these points:

- **Brief:** audience, analysis depth, tone and target length. Grounded analysis,
  clear storytelling and the vertical phone experience are confirmed. Exact
  duration, audience knowledge and voice remain preferences to resolve on real work.
- **Story/voice:** a small set of hooks or outlines, and short listening samples
  before committing a voice or making a major pacing/style change.
- **Finished output:** a watchable edit with the exact version identified. Capture
  accept, revise, reject or not reviewed, plus the desired changes.
- **Default changes:** proposed model/voice promotions, changed preference weights
  and newly proposed paid/data-processing routes require an explicit human decision
  unless that exact scope is already authorized.

Present one output for approve/reject with comments by default. A rejection with
requested changes becomes a revision task; preserve the original rejection.
Offer A/B only when the options represent substantially different directions,
such as a technical explainer versus a dramatic recap. A model or small wording
change alone does not justify an A/B interruption. Optional rating dimensions and
“keep/change” comments may help, but never require a form or numeric score. Ask a
focused follow-up when a comment is ambiguous. User silence, a technical pass,
model self-scoring and audience engagement do not constitute acceptance.

Preserve exact user comments and keep any interpretation separate. Ask whether
the instruction applies to this output, this event, a format or future work. A
suggested durable preference remains pending until confirmed; an explicit user
instruction already provides that confirmation. Retain corrections/superseded
records rather than overwrite their history. Do not infer taste from clicks or
playback duration. Optional usage feedback such as device, observed segment and
revision time should be explicit and minimal; unobserved values remain null.

Proposed records, relative to the selected ignored workspace:

| Record | Required meaning |
|---|---|
| `research/event/preferences.json` | Versioned, human-confirmed brief/preferences, scope, source feedback IDs and pending suggestions separately |
| `runs/model-evaluations/<comparison-id>/` | Frozen evidence/configuration, candidate output hashes, actual model receipts, failures and comparison protocol |
| `runs/feedback.jsonl` | Append-only feedback ID/time, event/comparison ID, human role, output paths and hashes, outcome, verbatim comments, optional ratings, scope and correction reference |
| `outputs/human-feedback.json` | Current acceptance view derived from actual human records and bound to the current manifest/video hashes; absent feedback is not reviewed |

These paths are **proposed**, with no CLI, validator, storage implementation or UI
yet. Keep the ledger private in ignored operational data. Authorized capture and
use for project evaluation does not authorize uploads, analytics tracking,
fine-tuning, preference training or redistribution. Propose any such use separately.

Changing a video invalidates its previous acceptance binding. Changing a preference
does not alter what the user said about a historical version. Keep
`finalized_local_review` separate from the future `human_accepted` milestone.

## Quality evaluation before efficiency

Create a frozen development sample from approved public/evidence inputs. Start
with 12–20 representative cases to learn preferences, not to declare statistical
parity. Cover misleading captions, session/year confusion, conflicting sources,
missing evidence, transcripts, ranking, hooks, short/long scripts and narration.
Use another source/clip-grouped held-out set for promotion; do not tune on it.
Reposts and neighboring excerpts from the same source stay in the same split.

First compare one change at a time against the saved reference: model, reasoning
effort, prompt, evidence packet, voice or provider/quantization. Keep evidence and
generation conditions comparable, disclose limits, retain failed attempts, and
sample repeated runs when variation matters. Present the candidate as one output
for the user's approve/reject feedback; compare that result with the frozen
reference and prior comments internally. If a substantially different direction
needs A/B, randomize order and hide model identities when useful. Use the same
renderer to isolate text quality; also evaluate finished edits for overall experience.

Hard eligibility gates include exact identity, supported claims, current hashes,
allowed intervals, valid structure and no fabricated observations. A preference
win cannot excuse a failed evidence gate. Subjective dimensions may include story
value, clarity, tone, pacing, voice, captions and visuals; the user chooses their
importance. The 45/35/20 ranking weights in [Jev research](jev.md) are a proposal,
not accepted user preferences.

Evaluate the primary vertical output first: an understandable opening, clear
causal explanation without unsupported claims, readable captions/charts at phone
size, safe placement around player controls, suitable crop/framing and intelligible
phone audio. Playback on the user's phone supplies the experience feedback; a
desktop screenshot is insufficient. Landscape remains a secondary requested
format and must still pass its existing gates. Do not invent a duration or
shorten away necessary grounding simply to make the edit faster.

Report approve/reject and revision rates, comments by preference dimension, major
factual failures and raw sample sizes. For occasional directional A/B reviews,
also retain wins/ties/both-unacceptable outcomes. An AI reviewer
can triage but cannot become the definition of quality. Promotion requires no
known unresolved critical evidence failures, held-out results, no regression in
the user's required dimensions, and explicit approval. Any numerical tolerance
or noninferiority margin needs the user's agreement; do not invent a universal
“95% quality” threshold. Small samples support a pilot, not a parity claim.

Only after a route meets that standard compare:

| Efficiency measure | Accounting rule |
|---|---|
| Paid cost per human-accepted output | All measured generation/review/retry/escalation charges divided by accepted outputs; no accepted outputs means undefined |
| Subscription usage per accepted output | Use actual attributable usage where exposed; otherwise report unknown. Do not convert API price tables to subscription charges |
| Total time to acceptance | Preparation, inference, queue/wait, review and revision time, with machine and human time separate |
| Reliability | Schema failures, abstentions, escalations and human corrections; retain failed attempts in the denominator |
| Hosted serving cost | Exact provider/model/tier rates, billed reasoning and modality units, cache hits, queue latency and retries; use measured bills/usage, not parameter count |

Aggregate by task and format before quoting overall averages. Do not rank routes
with missing usage data as free. Usage limits are account-wide, so concurrent work
can confound before/after readings. Record that limitation.

Efficiency improvements that preserve quality are evidence-packet reuse,
hash-based deduplication, batched independent questions, prompt/rubric reuse,
targeted revision and downstream-only reruns. For proposed inference caching use
event/task identity, evidence/clip-review hashes, model revision, prompt/rubric,
preferences, sampling settings and runtime/quantization. Reuse only a validated
receipt/output pair. Keep claim-support decisions per claim and never truncate
contradictory evidence to make a request smaller. Escalate uncertainty within a
bounded attempt budget; avoid indefinite generator/judge loops.

## Hosted open-model candidates and price

Start with **DeepInfra as the proposed inference provider**: its directly listed
models cover text, vision, ASR and TTS through hosted APIs. This is a shortlist
recommendation, not proof of account access, provider reliability or F1 quality.
[Provider API documentation](https://docs.deepinfra.com/).

The following standard-tier USD rates were checked on 2026-10-10. Cached-input,
priority/flex and reasoning-token accounting can change the actual charge. Refresh
rates and verify the exact endpoint/configuration before a paid run.

| Hosted candidate | Intended first test | Input / output per 1M tokens | Listed serving precision | Price source |
|---|---|---:|---|---|
| DeepSeek-V4-Pro-0813 | Strong text research/script candidate; prioritize quality before cheaper routing | $1.30 / $2.60 | FP8 | [DeepInfra](https://deepinfra.com/deepseek-ai/DeepSeek-V4-Pro-0813) |
| Qwen3.5-397B-A17B | Grounded scripts plus vision/caption/frame review | $0.45 / $3.00 | FP8 | [DeepInfra](https://deepinfra.com/Qwen/Qwen3.5-397B-A17B) |
| DeepSeek-V3.2 | Lower-price grounded text comparison | $0.26 / $0.38 | FP4 | [DeepInfra](https://deepinfra.com/deepseek-ai/DeepSeek-V3.2) |
| gpt-oss-120b | Very low-price bounded extraction/claim triage candidate | $0.037 / $0.17 | BF16 listed | [DeepInfra](https://deepinfra.com/openai/gpt-oss-120b) |

Illustration, **not a measured edit cost**: 20,000 billed input tokens and 2,000
billed output tokens with no cache cost about $0.0312, $0.0150, $0.00596 and
$0.00108 respectively, in table order. Additional reasoning tokens, failed
attempts, other stages, media processing and revisions increase that amount.
The more expensive strong candidate is preferable if it produces the user's
accepted result with less rework. No candidate has yet been measured on this F1
workflow, and provider/upstream benchmark claims do not establish preference parity.

For a concrete provider alternative, Together lists the same Qwen model at
$0.60/$3.60 per million input/output tokens and FP4 serving. Its listed rate is
higher than DeepInfra's, but different serving configurations and reliability
must be evaluated as separate routes. [Together model page](https://www.together.ai/models/qwen3-5-397b-a17b).
Start with one provider; add another only when quality, availability or measured
cost per accepted output justifies it. Avoid an opaque automatic multi-provider
fallback that prevents attribution.

Hosted speech candidates are [Kokoro-82M](https://deepinfra.com/hexgrad/Kokoro-82M)
for narration (listed $0.99 per million characters) and
[Whisper large-v3](https://deepinfra.com/openai/whisper-large-v3) for missing captions.
The ASR rate/unit is not established in this review and must be verified before
a paid call. A voice only becomes the default after the user's listening feedback.
Keep speech and visual evaluation distinct from text-model evaluation.

## Path to open models

The goal covers text judgment/generation, vision where used, transcription and
narration. Downloads, rendering, source retrieval and rights checks remain explicit
tools/contracts. Switching the LLM does not provide browsing or playback tools by
itself. The integration must preserve those capabilities and provenance.

Use “open-weight” precisely: accessible weights and a permissive license do not
establish that all training data/processes are open. These hosted candidates have
open weights; do not claim complete training-source openness. Pin the provider,
exact model ID, endpoint, settings and observed serving configuration. Record an
upstream revision when exposed; unknown hosted build/weight hashes stay unknown.
The candidates are a bounded shortlist, not an exhaustive/latest-model ranking.

| Capability | Candidate and verified upstream basis | What must be tested |
|---|---|---|
| Research and script text | [DeepSeek-V4-Pro-0813 upstream](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro-0813) and [DeepSeek-V3.2 upstream](https://huggingface.co/deepseek-ai/DeepSeek-V3.2) list MIT | Script/source grounding, narration clarity, model settings and exact provider-specific behavior |
| Text/vision | [Qwen3.5-397B-A17B upstream](https://huggingface.co/Qwen/Qwen3.5-397B-A17B) lists Apache 2.0 | Observed-frame accuracy, caption grounding, schema success and vertical-edit preference; frame observation cannot establish an unviewed interval |
| Bounded extraction/claim triage | [gpt-oss-120b](https://developers.openai.com/api/docs/models/gpt-oss-120b), hosted at the proposed provider | Citation retention, identity errors, abstention and schema success; no inferred final acceptance from low price |
| Transcription when referenced captions are absent | [Whisper](https://github.com/openai/whisper): code and weights under MIT | F1 names, noisy clips, timestamp accuracy and hallucinations; verify against the relevant audio |
| Narration | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M): Apache-licensed open weights | User-approved voice/prosody, driver/circuit pronunciation, timing, audio QA and actual listening |

The user's hosted-inference preference means local RAM does not constrain model
size selection. Existing local storage/render limits remain applicable. No local
model runtime, weight download, GPU rental or dedicated endpoint is proposed.
Test the provider's actual schema/tool, vision/audio, timeout and usage behavior;
OpenAI-compatible API shape does not guarantee identical capabilities. Separate
external evidence processing from private user feedback, sending only the material
needed for the authorized task.

Move in stages:

1. Establish a human-approved subscription reference and private feedback ledger.
   Add portable model/input/output/usage receipts without changing source gates.
2. Shadow-test one hosted text model and one speech candidate on frozen approved inputs.
   Preserve the current outputs/defaults. User approves a voice and comparison result.
3. Promote only tasks meeting the human quality standard. Add vision/ASR where
   useful and independently evaluated; keep remaining hard tasks on subscription.
4. Test the complete hosted open-model workflow on held-out events, including real video
   listening/viewing, tools, abstention, retries and provenance. Review total cost
   per accepted edit. Retain the last approved route for an explicit rollback.
5. Declare the goal reached only when every required inference capability uses an
   approved open model and no closed-model fallback is needed for accepted output.
   Continue checking quality after upstream/runtime/prompt/quantization changes.

Jev remains an optional hosted decision model, with no official downloadable
weights verified in this review. It can be a comparison, but cannot be the final
open-model dependency. There is no reason to add a paid intermediate provider
unless it demonstrably solves a gap that subscription/open candidates do not.

## Next implementation

Implement feedback/provenance capture first, then a provider-neutral task/receipt
contract and an offline evaluation report. Keep subscription work in supported
Codex surfaces; a generic API contract must not imply that API billing is covered
by ChatGPT. Add a hosted inference adapter with explicit endpoint/model, metering,
bounded spend and no silent provider changes once the execution scope is concrete.
Model promotions and important preference changes remain explicit human decisions.
The [review plan](plans/model-selection-review.md) records verification and scope.
