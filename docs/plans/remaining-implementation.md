# Remaining implementation and delivery: first offline wave

Date: 2026-10-11. Status: complete for this offline implementation/preparation
wave; external delivery and human evaluation gates below remain pending.
Baseline: `043aa03`.

## Objective

Implement the concrete source gaps found by the [plan reconciliation](README.md),
prepare safe Site updates, and make held-out evaluation preparation executable offline.
Preserve archives, immutable model receipts, current films, styling and voice.

## Decisions and boundaries

- Root owns plan reconciliation, shared CLI integration, final review and checks.
- Independent Python edits use managed source-only worktrees. Delegates own the
  paths below and return patches/check results without staging or committing.
- The Site delegate owns only the existing independent phone Site checkout and
  ignored preparation evidence. Credential entry stays disabled. Preserve Site
  identity, audience, media, feedback and runtime configuration.
- Paid calls, uploads, automatic pushes/deployments, credential pickup and
  background jobs are outside this implementation pass. Prepare and verify source
  updates before a publication handoff under the repository's deployment rules.
- Human acceptance, voice changes, parity and model promotion require actual
  human evidence. Synthetic records cannot establish them.
- Vision, ASR and open-model narration remain later scoped work: concrete inputs,
  provider contracts and listening/viewing criteria precede adapter selection.

## Assignments and acceptance

| Owner | Owned paths | Completion criterion |
| --- | --- | --- |
| Story-contract delegate | `f1_pipeline/story_contract.py`, `f1_pipeline/model_jobs.py`, `tests/test_story_contract.py`, `tests/test_model_jobs.py`, `docs/story-contract.md`, `docs/openrouter-workflow.md`, `examples/synthetic/story-*` | Opt-in hash-bound shared claim/numeric ledger for text stages; source-bound timed draft/revision outputs validated before dependent work; stale/malformed/overlong results fail closed with immutable evidence |
| Quality-protocol delegate | `f1_pipeline/quality_protocol.py`, `tests/test_quality_protocol.py`, `docs/quality-evaluation.md`, `examples/synthetic/quality-protocol*` | Offline frozen protocol validates source-grouped development/held-out separation and current bindings; no invented labels, approval, parity or inference |
| Phone-Site delegate | Existing independent `sites/phone-quality-review` source; private `runs/remaining-implementation/site/` | Apply current consent templates, preserve disabled operation/media/data, pass synthetic route/encryption/type/build checks; report exact deployable source and hosted sign-in limits |
| Root | `docs/plans/`, shared CLI wiring if needed, integration and private verification | Review returned diffs, run focused regressions plus `scripts/check`, validate packaging for added modules/resources, and report actual results |

## Other open delivery gates

1. Capture real phone feedback for latest version `d8ee4efbde62`; import only the
   actual decision with matching output/model bindings.
2. Freeze a real evaluation sample and obtain human-reviewed labels/preferences
   before live held-out execution or model promotion. Offline tooling is only
   preparation, not the evaluation itself.

The revised workflow guide is already published: its successful deployment
receipt matches current HTML and independent Site commit `8931015`. No guide
publication remains in this wave.

Root's current hosted browser follow-through passed: the feedback UI loaded,
41.3-second video played beyond 30 seconds without error, pause and Home-key seek
to zero succeeded. No production feedback was submitted. New version-bound
operator evidence retains earlier local interaction checks and original private
deployment bindings; `review-site-status` reports ready for human review. Actual
phone/editorial acceptance stays `not_reviewed`.

## Next action and verification

All three bounded tasks produced implemented work. Root integrated the two Python
implementations and reviewed the independent Site diff. Story plans now support
the opt-in shared ledger and deterministic output gates; protocol commands support
offline preview, exclusive freeze and current-evidence checks. Source placement,
explicit command ownership, preserved receipts and human quality gates remain.

Independent standards review found no actionable story integrity defect. Spec
review reproduced one exact-identity type mismatch; root added strict field types
and a regression. Independent float/bool reproductions now reject the malformed
identity. No review finding remains open in this bounded source scope.

Verification: 220 shared offline tests ran (219 passed, one opt-in native Keychain
test skipped), synthetic CLI checks passed, and all 20 actual-wheel checks passed.
The wheel contains both new modules. All 36 changed/untracked source files passed
direct guard inspection, documentation links resolve, and index/diff checks passed.
Phone preparation passed six crypto/storage tests, five synthetic real-handler
contracts, TypeScript and production build with protected media/style/config hashes
preserved. No provider calls, production feedback writes, main-branch commits, pushes or
deployments were performed. Private receipts are in `runs/remaining-implementation/`.

Next delivery: publish the reviewed consent rollout through the existing private
Site workflow when authorized, preserving disabled credential entry; collect real
latest-film phone feedback; prepare a real frozen sample/rubric and human labels
for later evaluation. Vision/ASR/narration adapters and cross-event evaluation
execution are separate future scoped implementation, not delivered by this wave.

Subsequent follow-through: [evaluation results](quality-evaluation-results.md) now
provide offline human-label/result reporting and are integrated into main. The
[narration integration](robot-voice-lab-integration.md) implements import/preparation,
explicit ElevenLabs generation and optional vocoder processing. Vision/ASR,
open-model narration, real held-out evaluation and human promotion remain pending.
