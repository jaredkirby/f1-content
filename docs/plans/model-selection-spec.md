# Human feedback and model-work evaluation

Status: implemented and verified offline; test boundaries confirmed by the user.
Local spec, baseline `4a30d01`. Verification is in the implementation plan.

## Problem statement

The project can produce traceable local edits, but it cannot yet connect the
user's approval or rejection to an exact output and model configuration. It
cannot honestly compare accepted quality, usage or revision effort. The desired
move to quality hosted open models needs a concrete API path and evidence before
production defaults change.

## Solution

Provide explicit workspace commands to record human feedback and preferences,
import actual subscription/hosted model work, advise a subscription-first route,
and report quality and efficiency. A hosted open-model request starts with a
no-network preflight and needs explicit execution and budget. Existing local
release checks remain distinct from human acceptance.

## User stories

1. As the user, I can approve or reject one output with comments, so quality is
   measured by my response to the work I actually reviewed.
2. As the user, I can correct prior feedback while retaining its history.
3. As the user, I can set a preference with explicit scope, so a comment on one
   edit is not silently applied to every future edit.
4. As the user, I can see that a changed or missing output is not approved by an
   earlier feedback record.
5. As a researcher, I can identify the selected exact session and source hashes
   throughout feedback, generation and evaluation records.
6. As an operator, I can import an actual Codex-authored result without making
   another provider call or repurposing subscription credentials.
7. As an operator, I can record observed model/settings, prompt/rubric versions,
   preference version, inputs, outputs and each failed or successful attempt.
8. As the user, I can distinguish unknown usage from zero cost and provider
   estimates from actual measured billing.
9. As the user, I can review acceptance/rejection and revision comments before
   comparing spending, token use or elapsed effort.
10. As an operator, I can preview a hosted request with its exact model, payload
    hash and conservative standard-tier cost bound before any credential/network use.
11. As an operator, I can explicitly execute one bounded hosted request and retain
    validated provider usage, result hashes or a safe failure record.
12. As the user, I can retain grounded storytelling, vertical phone consumption,
    single-output feedback and human decisions about model/voice promotion.

## Implementation decisions

- Separate human feedback, model-work receipts, hosted transport and CLI integration
  behind small public workflow functions.
- Use append-only private feedback with corruption detection and derived current
  views; do not claim that a local file authenticates a human or prevents tail deletion.
- Bind feedback to exact current manifest, output/companion hashes and explicit
  model receipt links. Corrections apply to the same current output; older history
  is retained without silently rebinding it.
- Preferences are explicitly human-sourced and versioned. Freeze immutable
  preference references in model work rather than mutable latest views.
- Store observed model/settings per attempt. Preserve unknown identity, usage and
  cost as null. Keep actual and estimated cost in separate fields.
- Route advice uses task/access constraints and the subscription-first policy;
  it performs no model calls and no automatic promotion.
- The report includes rejected/failed attempts and incomplete measurements.
  Cost per accepted output is undefined if there are no accepted outputs or the
  actual total is unknown. Attribution is explicit, not proof of causality.
- The initial implementation used DeepInfra and four reviewed text-model IDs.
  The subsequent [OpenRouter migration](openrouter-inference.md) replaces that
  active slice with one pinned DeepSeek text route. Historical provider receipts
  retain their original identities and rates. Execution remains bounded, with
  no redirects or silent retry/fallback.
- A conservative preflight prices the full documented context plus capped output
  at dated uncached rates. It is a bound under those rates, not a token prediction
  or promise about provider price changes or a settled bill.
- Preserve the user's phone-first brief. Technical output checks are still required;
  neither model self-scores nor absence of a response imply human acceptance.

## Testing decisions

Confirmed boundaries: public CLI/workspace workflows, and the hosted adapter's
HTTP transport boundary. Use independent worked fixtures in temporary synthetic
workspaces. Test behavior such as stale acceptance rejection and complete/unknown
cost accounting, not private helpers or mirrored calculations. Mock only external
HTTP transport, time/randomness where needed. Test authorization defaults with
credentials absent and present: neither may cause a preflight network call.

## Out of scope

No incidental paid inference, credentials, uploads, background jobs, production
renders or model/voice promotion. Do not replace actual source/phone viewing with
synthetic tests. Speech/vision-specific adapters and held-out model-quality pilots
need separate concrete inputs and human feedback. The complete open-model quality
goal is not achieved merely by building a client and evaluation ledger.
