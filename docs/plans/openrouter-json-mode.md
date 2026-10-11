# Correct the pilot's JSON request

Date: 2026-10-10. Status: corrected request executed; candidate film published for phone feedback.

This record follows preparation through execution in order. Statements that
the corrected request is unexecuted or awaits a key apply to the intermediate
checkpoints below, not its final outcome. See [project state](../project-state.md)
for the current branch and later review output.

## Objective and decisions

The first authorized OpenRouter candidate returned HTTP 400 with no completion or
metering. Its request selected JSON-object mode but never instructed the model to
return JSON. Upstream documentation requires that instruction. This is a concrete
request defect and a likely explanation; the retained error hash alone cannot
prove the provider's specific reason. Preserve the failed immutable receipt and
leave actual cost unknown.

Reject JSON mode without a JSON mention during offline preflight, before reading
a key or creating execution evidence. Prepare a new request with an explicit JSON
instruction and object example using the same frozen evidence and editorial
direction. Keep the model, pinned provider, high reasoning and 8,192-token cap.
Omit temperature because the upstream thinking-mode guide says it has no effect.
Do not edit the original request, authorization or failed work receipt. The mobile
handoff was consumed and cleared; a future call requires a new bound authorization
and another key submission. No retry or model promotion occurs during this fix.

## Verification and next action

Verify a missing instruction cannot reach the synthetic transport and a mixed-case
JSON instruction completes one synthetic request. Retain the existing malformed
JSON response checks. Run relevant regressions and the shared offline check, then
inspect the staged diff and source guard before committing. Save the corrected
request/preflight under the private pilot workspace and show its unchanged
$0.3244032 ceiling before requesting another bounded call.

The targeted hosted suite passed all 22 tests. The shared offline check passed
149 tests, synthetic CLI smoke checks and the source guard. The corrected private
request passes preflight with the unchanged ceiling and has not executed. The
original missing-instruction request now fails preflight. Model evaluation retains
one failed hosted attempt, unknown metering and no human-approved outputs.

The human approved the corrected request and authorized a cap increase if needed.
The current request needs no increase. Bind the new work ID, prompt and rubric
versions to this authorization; preserve the first attempt. The one-shot helper
can verify these bindings offline without touching the handoff, and still refuses
any existing intent before key pickup. Reopen and privately publish the existing
mobile form for this new operation, then execute when the human resubmits the key.

Verification passed: 151 shared offline tests, two new helper binding regressions,
four encryption tests, local synthetic HTTP handoff and current phone form checks.
The production workspace's corrected work passes offline binding verification.
TypeScript/build passed; the exact Site source was privately published with its
existing runtime revision and audience. Client bundles contain no secret names.
Private native deployment/check receipts retain the current source/operation hashes.
The temporary form now awaits a new key; approval is already recorded and will
not be requested again for this corrected request.

The human resubmitted the key and the corrected request succeeded once. The
handoff's ciphertext and IV were cleared before delivery to the local process.
Session pickup access was renewed through native settings without replacing the
encryption key. Actual provider metering and the raw draft are retained; the
editorial revision and candidate handoff are tracked in
[the candidate film plan](openrouter-candidate-film.md). No extra provider call,
human quality approval or model promotion occurred.
