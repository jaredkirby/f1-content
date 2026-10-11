# Durable credentials and practical quality validation

Status: implementation and live validation complete; corrected script awaits editorial review. Baseline: `91f2a3f`.

## Objective and decisions

The user authorized persistent safe storage on the next phone entry, broader limits
and a full quality validation pass. Use this Mac's login Keychain with one named
OpenRouter item and a dedicated native helper. Never pass the key in process
arguments, persist plaintext, expose a print-key command or broaden item access to
all applications. Keep the temporary private Site handoff single-use and encrypted.
Fail closed if Keychain is locked or denied; do not silently save to a file.

Use a $10 validation budget with a finite declared job list, rather than approval
for penny-sized calls. Increase local output allowance to 65,536 tokens, request
timeouts to 300 seconds and plans to 64 jobs. Use 32,768 tokens for the next story.
Preserve provider context/rate constraints, exact session/hash checks, disk reserve,
single-use receipts and no retry after ambiguous outcomes. These are integrity
boundaries, not spending friction. No automatic account purchase or provider-side
key-limit change is implied.

## Acceptance and test seams

Continue the user's delegated judgment and Matt Pocock TDD/implement/review flow.
Test public CLI/workspace, provider HTTP, and the new native Keychain process
boundary. A separate opt-in native test creates only a uniquely named synthetic
Keychain item, verifies store/read/update/delete, then removes that test item.
Ordinary offline tests must never read the user's real saved key.

Verify generous requests remain bounded, missing/locked credentials fail without
leaking content, previews never read Keychain, and both Jev/text routes can reuse
the saved key. Review stale/replaced plans, failure accounting and key persistence
before the paid call. Run focused regressions, full offline suite, installed-wheel
checks and separate Standards/Spec reviews. Validate the private phone handoff.

After the fresh entry, execute a source-bound story and meaningful Jev control
cases (supported, contradicted, wrong session and insufficient evidence). Keep
evaluation labels separate from prompts. Review factual/narrative quality and
retain both known costs and limitations. Model scores and tests cannot establish
human approval of a finished film.

## Verification and next action

- Full offline check: 181 tests, 180 passed and one opt-in native test skipped;
  synthetic CLI checks, diff checks and source guard passed.
- Separate native synthetic store/read/update/delete test passed on this Mac.
- Installed wheel: all nine resource/CLI tests passed.
- Phone Site: TypeScript and four encrypted-handoff tests passed; production build
  and owner-private publication succeeded.
- Standards review: no findings. Spec review found one persistence-choice mismatch;
  a failing regression reproduced it, and the fix rejects disagreement in either
  direction before storage or inference. All seven phone-helper tests passed.

The prepared local quality pass declares eight Jev factual/adversarial controls
and a three-stage story draft, critique and revision. Its $10 budget covers the
$1.0831872 conservative preflight ceiling. The user's fresh phone entry was saved to login Keychain and reused by both
provider routes. All 11 calls completed; OpenRouter reported $0.0180556416 total.
All eight Jev controls matched their labels, including missing evidence, wrong
session, counterfactual facts and source-injected instructions. These are one-event
smoke controls, not a held-out calibration or model-promotion result.

Draft, critique and revision completed without output truncation. Editorial review
found that the draft confused the pole margin with a sector swing. The critique
caught that title error but omitted sector one from its stated net arithmetic;
the revision repeated that error in change notes and produced overlong segment
timings without source bindings. The raw story remains in need of revision.
A separate Codex correction retains all three sector differences, bound data,
a 121-word narration and a 60-second segment outline. Original model receipts
remain immutable. Private control results, cost evidence, editorial findings and
the corrected script are retained in the event's `runs/` archive. No new video
render, human acceptance or model promotion is claimed.

Next quality improvement: supply each model stage the same explicit event/claim
and numeric ledger, and require duration plus source bindings in the output schema.
Keep deterministic arithmetic and independent editorial review as separate gates.

Work is isolated in a managed worktree because the shared checkout moved to main
while this task was active. Event archives and the private Site remain in their
original durable local locations; no archive or credential enters this commit.
