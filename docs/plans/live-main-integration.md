# Integrate reviewed live work into main

Date: 2026-10-11. Status: complete; combined source verified for the authorized main push.

Final follow-through: merge `331ce66` was pushed and followed by repair `043aa03`.
The [preservation audit](branch-preservation-audit.md) has the final successful
five-job CI receipt. Publication instructions below are historical completed work.

## Objective and decisions

The user clarified that the intended push destination is `main`. Preserve newer
`main` work at `10cef3f` and merge the reviewed `Live` commit `d5e2197` with both
histories intact. Fetch confirmed the remote baseline before integration.

Resolve the workflow-document conflict by retaining explicit OpenRouter model
plans and the reviewed deployment-evidence wording. Update branch-specific copy
and chronological follow-ups to describe the combined implementation. Preserve
Keychain consent, 64-job/output/timeout limits, CI mobile tests, shared timeline
styling and all live feature bytes. Do not alter credentials or any ignored
archive, rerender a film, call a provider or deploy a Site.

## Verification and next action

Run combined Python checks, synthetic Node mobile routes and actual-wheel tests.
Review the staged integration diff and index guard; compare protected file hashes
and all four independent Site HEAD/status snapshots. Commit the merge, push
`main` without force, and confirm the remote revision and clean checkout.

## Verified result

- Shared `scripts/check`: 193 tests run, 192 passed, one opt-in native Keychain
  integration test skipped; synthetic CLI, index and whitespace checks passed.
- All eight Node mobile route/encryption/consent contracts passed. npm registry
  resolution was unavailable, so the existing synthetic test dependencies were
  reused from the credential worktree after exact lockfile/version verification.
- Wheel built offline; all 19 actual-wheel mobile/live regressions passed. Fresh
  installed doctor, Jev validation and a synthetic live CLI cycle passed outside
  the checkout with Keychain access disabled.
- Both independent review axes found no material remaining issues.
- Nine protected live-source/film-manifest hashes and all four independent Site
  HEAD/status snapshots are unchanged. All 87 existing main implementation/test/
  workflow/CI files outside the deliberate CLI and wheel-check changes match
  `10cef3f` byte for byte.
- All 49 Markdown documents and 120 relative links resolve. The staged source
  index guard and diff checks pass; no runtime data is staged.

The publication handoff is the user-authorized merge commit and normal push to
`origin/main`, followed by a remote-revision and clean-tree check. Private logs
stay in ignored `runs/main-integration/`. Hosted CI remains a separate check; no
real provider, credential or media operation occurred during this integration.
