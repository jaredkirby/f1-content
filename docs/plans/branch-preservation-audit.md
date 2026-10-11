# All-branch preservation audit

Date: 2026-10-11. Status: complete; preservation and local CI repair verified.

## Objective

Verify all local and remote branch work is integrated, main before the push
misunderstanding is preserved, and no changes or local drafts were dropped.
Resolve any confirmed integration failure and verify current remote main.

## Branch and worktree findings

After fetching all remotes and querying GitHub's branch heads directly, every
local and remote branch tip is an ancestor of `main` at `331ce66`. No open pull
requests exist at the audit checkpoint.

| Branch | Local tip | Remote tip | Finding |
|---|---|---|---|
| `main` | `331ce66` | `331ce66` | Synchronized combined merge |
| `Live` | `d5e2197` | `d5e2197` | Fully merged; historical branch tip |
| `codex/keychain-quality` | `0ce90c4` | `0ce90c4` | Fully merged; clean associated worktree |
| `experiment/good-css-timelines` | `91f2a3f` | `5188ea8` | Local is four commits ahead of its remote; all four are already in main |

Older branch pointers need not move to main to establish integration. No branch
was deleted, reset or force-pushed. Main is clean at the inspection checkpoint.

Three detached worktrees retain drafts at base `4a30d01`. Their eight changed/
untracked files all have exact versions in main history. Model-feedback's three
files match current main; model-provenance's two files have subsequent additive
provenance and regression changes; hosted-inference's three DeepInfra drafts were
superseded by the explicit OpenRouter migration. All drafts remain untouched.
Their dirty status is retained history, not missing branch work.

## Preservation evidence

The combined merge has exact parents `10cef3f` and `d5e2197`; neither parent's
tracked path set lost a file. All 87 previous-main implementation/test/workflow/CI
files outside the deliberate CLI and wheel-check additions match byte for byte.
Credential consent, Keychain, native Jev/job workflows, higher resource limits,
shared timeline styling and mobile CI remain intact. All Live implementation
files match the reviewed branch at the initial audit checkpoint.

Nine saved source/manifest hashes and all four independent Site HEAD/status
snapshots still match the pre-integration evidence. Git connectivity checks pass.
Two fresh read-only review axes found no dropped committed or draft work and no
preservation violation. Runtime integrity and human acceptance remain separate.

## CI finding and repair

GitHub run `38150582983` passed macOS and mobile contracts but failed all three
Linux jobs in the live pending-model regression. Initial `model_attempt = 0.0`
made the first model request depend on host uptime exceeding `model_seconds`.
Fresh runners could therefore collect without starting the expected first draft.

A synthetic monotonic clock fixed at five seconds reproduces the exact failure.
Use `None` for no prior attempt and apply elapsed-time spacing only after an
actual submission. The first request can start immediately on changed evidence;
subsequent requests retain the configured interval. No route, billing, credentials,
provider calls or unrelated main source changes are introduced.

## Verification and next action

The short-uptime regression failed before the fix, then all ten live regressions
passed. Shared `scripts/check` ran 193 tests: 192 passed and one opt-in native
Keychain test was skipped. All 19 actual-wheel tests passed. Independent review
found no remaining issue in the repair. Protected archive/Site evidence still
matches; only the deliberate scheduling source/regression changes differ.
Commit and push the repair to main, then verify hosted CI and direct remote heads.
Retain old branch/worktree pointers and drafts.

Private branch inventory, source/manifest/Site evidence and CI logs stay under
ignored `runs/branch-preservation-audit/`. Verification is still pending for the
repair's hosted matrix at this pre-push checkpoint. The post-push result belongs
in the final private verification receipt; local passes alone do not establish
remote health.
