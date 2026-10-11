# Implement human-led model quality decisions

Date: 2026-10-10. Status: complete; explicit workflows implemented and verified offline.
Baseline: `4a30d01`.

## Objective

Make the model-selection recommendations usable: capture human feedback for exact
outputs, retain actual model provenance and measured usage, compare quality before
efficiency, and provide explicit hosted open-model inference without incidental
spending or automatic changes to production defaults.

## Reasoning and decisions

| Decision | Why | Alternative and trade-off |
|---|---|---|
| Human approval is separate from local release | Existing technical gates cannot establish taste or actual phone viewing | Adding approval to `finalize` would alter historical release behavior and block technical delivery |
| Feedback binds exact output and receipt hashes | An approval of one version must not approve a revision or another event | Loose comments/model IDs lose attribution and permit stale acceptance |
| Preserve verbatim comments and explicit preference scope | A request about one edit does not necessarily define future style | Automatically inferred preferences reduce interruptions but can misrepresent the user |
| Import subscription-authored model work offline | Subscription access is the first route and uses supported Codex surfaces | Treating ChatGPT credentials as generic API credentials mixes authorization and billing |
| Keep model identity and measurements unknown when unavailable | Current defaults do not identify historical work; account totals can be confounded | Estimated or fabricated attribution creates a false efficiency leaderboard |
| Hosted inference defaults to preflight | The requested API client can be built and tested without submitting evidence or spending | Automatic fallback on a missing subscription hides costs and can lower quality |
| Use a fixed provider/model and one bounded request | Provider precision, usage and failure behavior affect quality and cost | Silent multi-provider retry obscures attribution and risks duplicate charges |
| Report actual cost separately from provider estimates | The provider reports an estimate, not a settled invoice | Treating estimates as actual cost makes accepted-output economics misleading |
| Promote models only after human-reviewed evidence | Prices and generic benchmarks cannot establish the user's quality standard | A cheaper route can save tokens while increasing human revision work |

## Skill application

Downloaded Matt Pocock's official `mattpocock/skills` at
`49dd158d1076134a641b33efb035946536778336`. Installed the planning, implementation,
research and review subset via the Codex Skill Installer. Use `to-spec` to synthesize
the settled conversation, `implement`/`tdd` for behavior at agreed boundaries, and
`code-review` for separate standards/spec reviews. Project instructions govern
local plan placement; no external issue publication is needed. Skills remain
outside the source repository; no upstream scripts are executed by the project.

## Bounded assignments

| Owner | Worktree / files | Observable result |
|---|---|---|
| Feedback subagent | `model-feedback`: new feedback module and focused regressions | Record human approval/rejection/preferences and derive current acceptance |
| Provenance subagent | `model-provenance`: model evaluation module and focused regressions | Import actual model work, advise subscription-first routing, report human quality and complete/unknown costs |
| Provider subagent | `hosted-inference`: hosted adapter, transport regressions and provider research | Preview a concrete request; execute only with explicit opt-in and budget; retain honest success/failure evidence |
| Integrator | CLI, integration tests, examples, docs and policy state | Public workspace commands, realistic synthetic smoke flow, final checks and commit |

Subagents do not share writable files or stage/commit. Managed worktrees contain
source only. The integrator reviews and integrates source changes; event archives
and secrets stay in the durable workspace.

## Verification

The user confirmed the recommended boundaries on 2026-10-10: public CLI/workspace
workflows and the hosted-provider HTTP adapter using synthetic responses. Cover stale/cross-event hashes,
corrections, missing feedback, unknown usage, rejected/failed attempts, no-network
preflight, provider identity/usage errors, redirects and ambiguous failures. Run
relevant regressions, then `scripts/check` once. Keep private run receipts in
`runs/`. Offline tests cannot establish actual model quality or playback acceptance.

## Next action

Run a bounded reference/candidate quality pilot on approved evidence, then present
one vertical edit for the user's approve/reject comments. Live model/voice promotion
requires those results; no promotion is inferred from synthetic tests.

## Delivered and verified

- Explicit CLI feedback/preferences, immutable model-work import, subscription-first
  route advice and quality/efficiency reports; current human review shown separately
  beside local films. Existing technical finalization stays intact.
- Hosted text inference defaults to offline preflight. Explicit execution uses
  one pinned endpoint/model request, budget/resource/storage checks, honest provider
  metering and retained success/failure/interrupt evidence.
- Three code worktrees with disjoint ownership; two independent review axes.
  Standards review: no remaining findings. Spec review: no remaining findings.
- Review repairs prevent later unlinked rejection from preserving approval,
  malformed provider identity from hiding failed work, and comparison filtering
  from bypassing the latest decision's full receipt/input/provenance bindings.
  Interrupted operations make headline totals unknown. Storage is checked before
  a billable request.
- Targeted red/green regressions: 15 feedback, 22 model evaluation, 15 provider
  transport and 6 integrated CLI tests. Existing release/Sprint regressions pass.
- Final `scripts/check`: **136 tests passed**, synthetic CLI/Jev smoke checks and
  exact-index guard passed. Rechecked after the review identified new code fixes;
  the earlier 134-test pass remains a separate receipt, not final verification.
- Python syntax, JSON, documentation links and staged/working diff checks pass.
  The 16 inspected production archive documents retain their original hashes.
- Private skill/source, review and test evidence remains under ignored
  `runs/model-selection-implementation/`. No real provider inference, signup,
  credential changes, media upload/render, deployment or human playback claim.
