# Offline evaluation results

Date: 2026-10-11. Status: complete; source integrated into main and combined
offline/package verification passed. Baseline: `034ed1c`.

## Objective

Continue the [first wave](remaining-implementation.md) with an offline workflow
for source-bound categorical evaluation results. Join real, explicitly supplied
human labels to immutable model work and a frozen protocol; report observed
counts and accuracy without performing inference or promoting a model.

## Decisions and acceptance

- Preview is read-only. Explicit save creates a complete exclusive immutable
  evaluation receipt; report rechecks the protocol, model work, outputs and original
  request. Changed evidence invalidates evaluation rather than rebinding it.
- Begin with native Jev categorical outputs already represented by existing
  provider/model-work contracts. Read prediction/question choices from current
  validated output/provenance, rather than accepting a caller's claimed prediction.
- Each assessment names one protocol case, exact model work and attempt, question,
  expected categorical label and explicit human reviewer/source reference. Reject
  duplicate assessments, incompatible labels and missing case/protocol bindings.
- Native request `state.evaluation_case` must explicitly bind the exact protocol
  receipt, case ID, rubric and case evidence. Additive model-work metadata is not
  enough to associate a prediction. Reusing one work/attempt/question answer for
  another assessment is rejected, including across development/held-out splits.
- Commands are `quality-results-preview`, `quality-results-save` and
  `quality-results-report`, using existing `--request`. Only the save command
  writes an immutable evaluation snapshot; no command executes a model.
- Keep development/held-out and model/settings groups separate; report raw sample
  counts, confusion counts, correct/incorrect counts and observed accuracy. Partial
  coverage stays visible. No parity/calibration or statistical adequacy claims.
- Label references are operator-supplied human evidence declarations, not local
  authentication. Synthetic tests remain fictional; real labels stay pending.
- Existing feedback/model-evaluate own film acceptance and cost accounting. This
  workflow cannot create human film approval, thresholds, preferences or promotion.
- No provider call, credential access, media upload, background run, push or deploy.

## Ownership

The evaluation-results delegate owns new `f1_pipeline/quality_results.py`,
`tests/test_quality_results.py` and `docs/quality-results.md` in a source-only
managed worktree. Root owns shared CLI/wheel wiring, plans and integration.
A separate read-only sample inventory delegate owns only ignored
`runs/quality-evaluation-next/`; source archives remain in their durable workspaces.
No two writers own the same event workspace or source files.

## Next action and verification

The workflow is implemented and committed as `53b082e` on the isolated
`codex/quality-evaluation-results` branch. It provides preview/save/report commands,
native request-bound case attribution, explicit human label declarations, immutable
receipts and observed accuracy/confusion/coverage by model/question/split. It does
not perform inference, create film approval or establish parity/calibration.

After the user confirmed voice work was finished, root committed its exact verified
source as `314dff9` and merged this branch into main. Shared CLI and wheel-check
conflicts preserve both speech and evaluation commands, required resources and
test suites. All other voice source hashes and the four new evaluation source/test/
guide files remain identical to their verified originals. Human labels, live
held-out execution, calibration and listening/promotion remain later gates.
Private integration evidence is under `runs/quality-evaluation-integration/`.

The first-wave source is committed as `034ed1c`; phone consent source is committed
locally as `38caf16`. Our staged changes are committed; a concurrent unrelated
voice-lab implementation is preserved outside this task's ownership and staging
scope.

## Real evidence inventory

The read-only inventory checked all 112 retained model-work artifact bindings for
the eight prior Jev controls, plus source registry hashes. All match their saved
evidence. Every case is already exposed and connected to the same qualifying
source groups, so none is eligible as a genuine unseen held-out case. Proposed
development assignment remains an operator decision, not a frozen protocol.
Selected-event and candidate configurations have equal identity but different
hashes; old receipts must retain their original workspace/configuration binding.
The private inventory states concrete source locators, grouping and reviewer needs.

## Review checkpoint

Both independent review axes reproduced a case-attribution defect: additive work
metadata could reassign one development prediction to held-out cases and inflate
counts. The delegate fixed request-bound exact association and prediction identity
deduplication; both independent attacks now fail. Adversarial regressions observed
red then green. The initial green run is retained as a pre-fix checkpoint.

Final isolated verification: 243 offline tests ran, 242 passed and one opt-in native
Keychain test was skipped. Synthetic CLI checks and all 21 actual-wheel tests
passed. Exact staged diff, source guard and whitespace checks passed before commit;
the worktree is clean. These results apply to `034ed1c` plus the isolated
evaluation-results changes, not the concurrent unfinished voice implementation.
No provider calls, real labels, credential access, push or deployment occurred.

Combined main verification: 264 offline tests ran, 263 passed and one opt-in
Keychain test was skipped; synthetic CLI checks, index and diff checks passed.
All 41 actual-wheel checks passed with both feature sets in the same package.
No archive, narration default, provider authorization or private Site was changed
by integration. This closes the source integration task, not human quality review.
