# Move hosted text inference to OpenRouter

Date: 2026-10-10. Status: complete; verified offline and prepared for authorized execution.

The preparation and next-action statements below are historical. The
[JSON correction](openrouter-json-mode.md) subsequently executed once and led to
the [candidate film](openrouter-candidate-film.md); see
[project state](../project-state.md) for later `main` work.

## Objective and decisions

Replace the active DeepInfra text adapter with OpenRouter and the user-selected
`deepseek/deepseek-v4.1-flash`. Codex subscription access remains first; this is an
explicit candidate route, not a quality promotion. Human phone feedback, exact
evidence/version bindings and the mobile review gate remain authoritative.

Pin the initial route to OpenRouter's `deepseek` provider slug. Disable fallbacks,
require supported parameters and cap provider prices at the verified peak rates.
This avoids changing serving providers or quantization between quality samples.
Keep one bounded nonstreaming request; no automatic retries, model fallback,
media upload, tool execution or paid test. Read `OPENROUTER_API_KEY` only on execution.

Record valid request-charge observations separately from dated rate estimates.
BYOK fees do not establish the full upstream cost. Preserve failure metering and
unknowns. Keep historical DeepInfra receipts and event/Site archives unchanged.

## Verification

Refresh official model/catalog/routing/billing facts with public read-only GETs.
Test the real HTTP and CLI boundaries using synthetic OpenRouter responses:
endpoint/auth/body, exact model/provider, fallback rejection, reasoning controls,
charge versus estimate/BYOK, stale settings, resource/budget failures and no-network
preflight. Run relevant regressions then `scripts/check`. Inspect staged diff and
index guard before a local commit. No parent push or Site deployment is needed.

## Next action

Use the prepared OpenRouter candidate after the required credential and explicit
budget are available, preserving the frozen prompt/evidence and the reference's
human review. Any finished candidate edit needs its own tested mobile destination
and approve/reject feedback. No promotion follows from this infrastructure change.

## Delivered evidence

- Verified the exact alias/canonical catalog identity, reasoning support, native
  provider parameters, peak/time-window rates and upstream MIT license using
  current primary sources. Public metadata receipts remain in private `runs/`.
- Active adapter uses OpenRouter and only the selected DeepSeek candidate, with
  explicit high reasoning, pinned provider, no fallback/compression, one bounded
  nonstreaming call and execution-only `OPENROUTER_API_KEY` lookup.
- Effective settings and observed route/generation metadata join usage and raw
  byte hashes. Credits charges, peak estimates and unknown BYOK totals remain
  distinct, including failures and interrupted-work observations.
- Targeted regressions passed: 21 hosted transport, six CLI and 23 evaluation.
- Shared `scripts/check` passed: 147 offline tests, synthetic CLI smoke and index
  guard. Local documentation links and diff checks passed. No live inference ran.
- Prepared a separate unexecuted pilot request at 8,192 output tokens with a
  $0.3244032 conservative ceiling. The original candidate request and reference
  video/manifest hashes remain unchanged. No new budget, paid run, model promotion,
  voice change or Site deployment was implied by this migration.
