# Enter the pilot credential from a phone

Date: 2026-10-10. Status: complete; private mobile handoff used for the authorized run.

## Objective and decisions

Provide a private mobile form on the existing review Site so the user can supply
the OpenRouter key without putting it in chat or using a desktop terminal. Preserve
the authorized single candidate call and exact $0.3244032 ceiling. The local Python
adapter remains the inference owner; this is a temporary credential handoff.

Use Sites ChatGPT identity and the existing owner-private audience. Keep the key
out of URLs, logs, model context, browser storage, source and receipts. Encrypt a
short-lived handoff in D1 using a native Sites runtime secret. A separate native
runtime operator token protects one-time retrieval, in addition to the private
platform boundary. Retrieval clears the ciphertext atomically before returning
the key over HTTPS to a local process; the process sets the child's environment
and never prints the key. Expired handoffs cannot be retrieved. No unattended job,
model retry, model promotion or new audience is introduced.

The mobile page states the purpose, provider, spending cap and temporary handling.
The user submits the key themselves. Native runtime secrets stay in session memory
and Sites; do not write them to local source/env files or include them in a summary.

## Verification and next action

Test encryption/tamper/expiry boundaries and anonymous, stale, oversized and
unauthorized HTTP requests offline. Test the mobile password field, submission,
clearing, persisted acknowledgement and one-time retrieval using a synthetic key
in the local database; no provider request occurs in those tests. Inspect the
schema-only migration, type-check/build, run relevant regressions then scripts/check.
Publish the exact source privately and return the mobile form URL. Actual inference
waits for a real submitted key, then uses the existing bounded CLI and receipts.

## Evidence

Local synthetic tests passed for AES-GCM encryption, tamper/expiry/context refusal,
bounded request bodies, authenticated submission, idempotency, secret-free
acknowledgement and atomic one-time pickup/clearing. The mobile browser verified
mask/reveal controls, acknowledgement after reload, empty key field on replacement
and no horizontal overflow at 320/390/768/1280 widths. No provider request ran.
TypeScript/build and 148 shared offline tests passed. Native runtime secrets are
masked and absent from client bundles. Local synthetic configuration was removed
before the exact source was packaged and privately published at environment
revision 1. Native schema verification found no synthetic production handoffs.
The hosted page remains identity-protected; the pickup API rejects a platform
service caller without its additional operator token. An authorized one-shot
pickup returned awaiting_key without making a provider call. The human then supplied
the key through `/connect`; collection cleared both ciphertext and IV in production.
The single authorized provider request returned HTTP 400 with no completion or
metering. Its immutable failed model-work receipt is retained. Do not retry that
work ID or infer zero cost from absent metering. Prepare any corrected request
before requesting another bounded call. Private deployment/check receipts stay in runs.
