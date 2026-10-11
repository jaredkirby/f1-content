# OpenRouter editorial work and Jev judgments

Status: workflow, later live controls and opt-in story validation implemented;
human acceptance pending. Baseline: `58baa908278bd2dd2d643d2b7be56389269b538e`.

The pending-story and proposed-call statements below describe this checkpoint.
The subsequent [quality pass](credential-storage-and-quality-validation.md)
completed draft/critique/revision; the [latest film](latest-quality-review-film.md)
records the separately corrected and published review output. Human acceptance
remains pending.

Current source improvements and offline evaluation preparation are implemented in
the [remaining-work plan](remaining-implementation.md). The unfinished-story and
one-call follow-up entries below retain their historical checkpoint meaning.

## Problem Statement

Hosted story drafting exists, but Jev still uses a separate direct credential,
prepared requests cover only the first associated claim, and model outputs lack
a bounded execution workflow that carries typed judgments into story drafting.

## Solution

Use OpenRouter for both the selected DeepSeek text route and real TypeSafe Jev.
Prepare evidence-bound requests, preview a complete bounded work plan, execute
each job once in dependency order, and expose typed findings and drafts for
editorial review. Human approval remains separate from model confidence.

## User Stories

1. As an editor, I want real Jev judgments using my OpenRouter account.
2. As an operator, I want exact model/provider routing without substitution.
3. As an editor, I want each selected claim paired with independent evidence.
4. As an operator, I want previews to run without credentials or network calls.
5. As an operator, I want total call and cost ceilings before execution.
6. As an editor, I want Jev's typed answers to inform the story request.
7. As an operator, I want changed evidence to stop execution and invalidate review.
8. As an operator, I want failed/interrupted work retained without automatic retry.
9. As an editor, I want low confidence or absent evidence to create review work.
10. As an operator, I want measured charges distinct from estimates or unknowns.
11. As an editor, I want generated stories to remain candidates until reviewed.
12. As a maintainer, I want these behaviors verified without real provider calls.

## Implementation Decisions

- Retain the direct Jev adapter for historical compatibility; new workspace Jev
  commands use OpenRouter's native System One endpoint, exact Jev model and
  TypeSafe provider. Share typed contract validation, not chat substitutions.
- Reuse the existing immutable model-work receipt and explicit execute interface.
- A work plan declares unique jobs, request/evidence hash bindings, prior-job
  dependencies, comparison identity, maximum calls and total budget. Text jobs
  may consume preceding accepted typed results as untrusted evidence.
- Validate all static requests and bindings before spending. Claim job output
  cannot execute tools, select a new route or change execution policy.
- Save execution intent before the first request. A work plan is single-use;
  stop on failure, never spend again automatically after unknown outcomes.
- A review view reports judgments, unsupported/uncertain claims and text drafts.
  It does not rewrite accepted rankings, rendering plans or human preferences.
- Use claim-specific packets with primary excerpts/locators and existing reviewed
  observations. A repeated editorial claim is not its own supporting evidence.

## Testing Decisions

Use the user-confirmed public CLI/workspace and provider HTTP seams from the
model-selection specification. The user's instruction to use judgment covers
routine test and plan choices; no new seam or permission interview is needed.
Tests observe public results/receipts and inject synthetic responses only at the
HTTP boundary. Implement vertical red/green slices, then independent Standards
and Spec reviews against this pinned baseline.

## Plan review and scope

Repository readiness, provider migration, JSON repair, mobile credential handoff,
branch review and timeline presentation plans are implemented. Their historical
observations stay intact. Mobile sign-in and human film acceptance remain pending;
these cannot be inferred from new model calls. The separate in-progress timeline
guide edits belong to another task and are preserved.

This work implements the missing Jev consumer and bounded model orchestration
identified by model-selection and workflow-design. Voice/model promotion, new
multimodal providers, content publication and unattended recurring operation stay
outside this change. The user chose a private phone credential handoff, so its
existing owner-private Site was updated for this exact plan. Existing deterministic collection/render/release gates remain.

## Execution and verification

1. OpenRouter Jev preflight, single-call transport and model-work receipts.
2. Claim-specific preparation and single-use dependency-aware work plans.
3. Current-evidence review view, real-event preparation, regression checks and
   separate Standards/Spec reviews; commit only the owned source changes.

No OpenRouter credential was available in the initial process. Complete offline
implementation and real-event preflight first. Live inference needs a fresh secure
handoff; never treat preparation or synthetic tests as actual model usage.


### Verification results

- `scripts/check`: 173 offline tests passed, synthetic CLI smoke checks passed.
- Built wheel locally without dependency/network installation; its nine installed
  package tests passed and all required resources were present.
- Standards review: zero remaining findings. Spec review: zero remaining findings.
  Both identified the same phone authorization race; the approved plan SHA now
  reaches Python and blocks a changed plan before execution intent or spending.
  A public CLI regression observed red then green for this case.
- Real qualifying workspace: nine claim-specific packets prepared. A separate
  four-job plan binds primary timing records for three claim checks and one
  dependent story draft. Budget: $0.50; full-context ceiling: $0.327552.
- Private phone handoff built and deployed successfully, preserving owner-only
  access. Encryption/expiry/context tests passed. In-app browser sign-in returned
  `invalid_state`; phone sign-in and key entry remain user-side verification.
- No live provider call was made in this implementation pass. Next action: collect
  the requested fresh phone handoff once, execute the bound plan, inspect actual
  receipts and use `model-review`; retain any failed or ambiguous attempt.

Private plan, preflight, source bindings and verification details stay under the
selected workspace's ignored `runs/openrouter-jev-qualifying-v1/` directory.
The shared source commit excludes Site repositories, archives and credentials.


### Live pilot follow-through — 11 October 2026

The private one-time phone handoff was collected and cleared. All four authorized
calls executed: three native Jev responses passed the typed contract and the
DeepSeek response was rejected as unfinished. Its 4,096-token completion budget
included 3,910 reasoning tokens. Actual reported total charge: $0.0030400335.
No automatic retry occurred. Two Jev answers entered advisory confidence triage;
independent Decimal checks confirmed the supplied timing differences, without
inferring technical causes or human acceptance.

Immutable provider/model-work receipts and a hash-validated evaluation are retained
locally. A separate one-call story follow-up reuses the accepted Jev evidence and
raises the total output allowance to 16,384 tokens. Its proposed budget is $0.35
and conservative ceiling $0.3342336. It remains unexecuted pending authorization
for an additional call and a fresh one-time credential handoff. The prior attempt
is neither overwritten nor represented as a completed draft.
