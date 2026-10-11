# Review of local and remote branches

Status: review and fixes complete in this changeset. Date: 2026-10-10.

## Scope

The requested "wall branches" is interpreted as all branches. GitHub and the local
checkout expose only `main`; there are no open pull requests. The published
baseline is `692049fb2591e4af22dd73f1a52ac77f1d4e4b93` and the reviewed local tip is
`376f58a43a689cab7b5d91e0c98917e9d90517dd`, comprising nine unpushed commits. The
working tree was clean before review. Source review does not authorize another
provider call, media upload, Site deployment or branch merge.

Three retained detached agent worktrees (`hosted-inference`, `model-feedback`,
`model-provenance`) contain eight draft files. Every file matches its version in
commit `466acb75` byte for byte; all work was already integrated in the reviewed
history. Their working files are preserved and no additional merge is needed.

## Method

Review the pinned three-dot diff independently against repository standards and
the relevant model-work, mobile review, credential handoff and OpenRouter specs.
Later plans supersede earlier provider details. The integrating reviewer checks
packaging and execution boundaries and validates actionable findings with synthetic
fixtures. Preserve existing event archives, immutable receipts and Site checkouts.

## Standards

Two hard violations, both P2; zero heuristic findings. Both are fixed and the
independent reviewer confirmed zero remaining hard violations in the fixes.

- The mobile helper exempted `openrouter-candidate-v1` from authorization identity
  checks. Changing the comparison and work ID could reuse a single-call approval.
  [Mobile review rules](../mobile-review.md) require authorization to bind the work,
  comparison, prompt and rubric. The helper now requires those bindings for every
  execution, including older IDs. Historical unbound approvals remain evidence.
- Mobile preparation read templates from a checkout-only `workflows/` path.
  An actual wheel returned success while omitting the review component and API
  routes. This violated [package verification](../agent-development.md#package-verification)
  and the Site-copy contract. All 17 unchanged templates now live in package
  resources; missing files stop preparation before destination writes. Wheel
  checks exercise the public CLI outside the checkout.

## Spec

Two implemented-but-wrong findings, worst P1; zero separate missing requirements
or unrequested-scope findings. Both are fixed and independently re-reviewed.

- P1: the authorization exemption above violated the exact execution bindings in
  [the corrected-request plan](openrouter-json-mode.md). Synthetic regressions
  reject both the original bypass and historical approvals missing identity fields
  before credential pickup.
- P2: preparation and readiness ignored `edit_plan_sha256`, allowing changed edit
  plans to remain ready for human review after finalization would reject them.
  The [mobile destination contract](../mobile-review.md) requires current technical
  evidence. Both paths now share validation of render inputs, mandatory QA hashes
  and the exact edit-plan hash in the manifest and QA. Package-code input bindings
  also use the existing resolver when the event lives outside the checkout.

There are three distinct defects across the two axes; authorization appears in
both. A socket inactivity timeout was also examined. The documentation calls it a
transport timeout, so this was not classified as an elapsed-deadline violation.

## Verification and continuation

- Baseline and final `scripts/check` passed; the final suite has 157 passing tests,
  plus the synthetic doctor/Jev CLI checks.
- All 13 focused authorization/mobile regressions passed independently. All nine
  mobile destination tests also passed against the actual unpacked wheel outside
  the checkout, including stale/missing QA and incomplete-template cases.
- All 17 moved template files match their committed originals byte for byte.
  All four local Node credential/body-limit tests passed after relocation.
- The exact staged diff and index guard are reviewed before the local commit.
  No provider request, deployment, archive copy or push is part of this review.

Detailed output stays in ignored `runs/repository-readiness/branch-review-*.txt`
and the wheel reproduction receipt. These are synthetic technical checks, not
evidence of human film acceptance or a fresh hosted-site test. Continue development
from this reviewed `main`; no review finding remains open.
