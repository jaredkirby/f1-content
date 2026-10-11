# Correct the pilot's JSON request

Date: 2026-10-10. Status: implementation complete; corrected candidate awaits another authorized call.

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
