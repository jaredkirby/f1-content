# Credential consent and branch integration

Status: complete for source and merge; independent Site rollout pending.

The 11 October reconciliation found the retained phone Site at `12fe749` still
uses the earlier credential handlers and lacks the storage-operation helper.
Credential entry is disabled. The [remaining-work plan](remaining-implementation.md)
records the subsequently prepared template synchronization: six crypto/storage
tests, five synthetic real-handler contracts, TypeScript and production build
passed; media/configuration/style preservation passed. Publication remains
pending and the source merge does not establish a Site deployment.

## Objective

Fix the two non-live branch review findings, verify the complete branch chain,
and merge into main. Preserve Live and its working changes and all local archives.

## Decisions

Bind explicit storage choice into a versioned operation identity and authenticated
handoff metadata. Reject stale pages, legacy unbound operations, pending handoffs
under changed storage settings, and collector mismatches before storage/inference.
No database migration is needed: the operation ID carries the immutable choice.
Existing pending handoffs need a fresh submission after template upgrade.
Keep agent policy and runtime at 64 jobs, with budget/accounting gates intact.

## Verification and next action

Use the agreed synthetic credential-handoff and CLI/workspace seams. Reproduce
failures before fixing, then run offline and wheel checks. Open a PR for remote
CI and merge only after its checks pass. No Site deployment or provider calls.

Local verification passed: 183 Python tests (182 passed, one opt-in native Keychain
test skipped); eight Node tests covering real route handlers over synthetic SQLite
and encrypted handoffs; changed templates type-checked with synthetic deployment
configuration; nine installed-wheel review tests passed. Both review failures were
reproduced before implementation. CI now runs the mobile contracts on Node 22.22.0.
Independent Standards and Spec reviews found no findings.
The follow-up merged through pull request #1 into `main` at `10cef3f`.
The later [live integration](live-main-integration.md) preserves these consent
contracts while adding the live feed; no Site deployment is implied by that merge.
