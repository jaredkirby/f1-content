# Model selection and human quality review

Date: 2026-10-10. Status: review complete; runtime changes not implemented.

Follow-up: the [implementation plan](model-selection-implementation.md) records
the subsequent explicit workflow commands; the status above describes this review's
original scope, not the latest runtime capabilities.

## Objective

Review actual model use, output quality controls and efficiency. Establish a
subscription-first workflow whose quality standard comes from the user's feedback,
with a measured path to hosted open models across text, vision and speech.

## Decisions

- Preserve event archives and release contracts. This task changes documentation
  and declarative policy; runtime model routing and feedback storage are proposed
  follow-up work, not implemented by this review.
- Quality takes precedence over usage, cost and latency. Technical/factual gates
  remain prerequisites; model scores cannot substitute for human acceptance.
- Use Codex through ChatGPT subscription access first. Other providers require a
  specific quality or capability reason and an authorized budget/data scope.
- Keep important editorial preferences and model promotions under human review.
  Feedback stays in the selected ignored event workspace and is not training data
  unless the user separately authorizes that use.
- Confirmed brief: grounded analysis and clear storytelling for primary vertical
  phone consumption. Review one output with approve/reject comments; A/B only for
  substantially different directions. Use quality hosted open-model inference at
  a good price; local model capacity is not the selection constraint.

## Next action

Implement private feedback/model provenance capture as the first follow-up, then
evaluate the subscription reference against a hosted open-model candidate. Build
an API adapter only with a concrete provider, credentials, budget and input scope.
This review does not claim that live quality comparisons or API integration ran.

## Verification

- Reviewed source contracts, optional Jev preparation/adapter, analysis, narration
  and finalization. Inspected bounded receipt summaries in the explicit Sprint and
  Qualifying workspaces; existing QA status does not substitute for fresh playback.
- Verified ChatGPT CLI sign-in and observed saved Sol/extra-high configuration.
  Verified official OpenAI guidance, provider-specific hosted prices and upstream
  open-weight licenses. Actual F1 quality, accepted-output cost and latency remain
  unmeasured.
- Added `docs/model-selection.md`, `workflows/model-policy.json`, workflow links
  and agent instructions. Confirmed vertical-phone, single-output feedback and
  hosted-inference preferences are recorded; event feedback paths remain proposed.
- Eight changed/new source documents passed direct source-guard inspection;
  31 relative documentation links resolved. Policy JSON parsed and checked for
  declarative scope, confirmed preferences and no silent paid fallback.
- `git diff --check`, `git diff --cached --check` and
  `.venv/bin/python scripts/repo_guard.py` passed. No Python runtime code changed;
  no new tests were needed for this documentation/declarative-policy review.
- Private audit and verification evidence is under ignored
  `runs/model-selection-review/2026-10-10/`. No paid inference, model downloads,
  production renders, uploads, background jobs or global configuration changes.
