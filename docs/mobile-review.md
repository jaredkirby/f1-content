# Test the mobile destination with every early pilot

The finished video and its mobile web destination are one review surface at this
stage. Human feedback defines quality. Passing browser checks makes an output
ready to review; it does not approve the story, voice, style or model.

## Prepare one bound output

Use a separate private Sites Vinext checkout, preserving its project ID, starter
auth/build integration and independent Git history. Select one event workspace:

```sh
./scripts/f1 --workspace /absolute/path/to/event prepare-review-site \
  --site-directory /absolute/path/to/independent/site
```

Preparation requires a current passed technical QA receipt, exact event identity
and unchanged video/companion/evidence hashes. It copies only the bound video,
poster, narration and captions plus reusable [Site source](../workflows/mobile-review-site/README.md).
Generated media and private run receipts stay ignored. Preparation never deploys,
contacts a model provider, uploads an archive or records approval.

For a new checkout, install the starter's locked dependencies, generate and review
schema-only Drizzle migrations, build and apply each pending migration to local
D1 as documented by the Sites starter. Preserve immutable applied migration
history. Type-check with `tsc --noEmit`; test the actual supplied preview. Publish
through the Sites workflow only when authorized, keeping the private audience.
Local synthetic feedback is separate from production D1 and human acceptance.

## Required review checks

Every early pilot handoff includes a current private HTTPS destination and real
browser checks for phone layout, video loading/play/pause/seek, unobscured captions,
timestamp capture, saved annotations after reload, approval/rejection history,
copy-for-chat, stale version rejection and authenticated storage. Include a small
phone, normal phone, tablet and desktop viewport. Browser emulation is technical
evidence; real phone consumption and editorial acceptance remain the user's call.
Use `node scripts/verify-feedback.mjs http://127.0.0.1:5173` inside the independent
Site for bounded local API checks. It refuses hosted origins.

Store operator browser evidence in `runs/pilot/mobile-web-checks.json`: exact
manifest/video hashes, project ID, URL, pushed `site_commit_sha`, tested dimensions,
observations and `checks` entries with `check` and `status`. Required check names
are `mobile_layout`, `video_playback`, `video_seek`, `captions_unobscured`,
`annotation_persistence`, `decision_history`, `chat_copy`, `version_rejection`,
`authentication`, and `hosted_page_and_media`. Status `passed` describes observed
behavior only; identify local versus hosted evidence and retain limitations.

Keep the native successful private deployment response in a separate private
receipt, with the pushed `commit_sha` and known `audience: "owner_private"`.
Update `runs/pilot/review-destination.json` with the literal native URL and
`browser_checks`/`deployment_receipt` path/SHA-256 links. Then run:

```sh
./scripts/f1 --workspace /absolute/path/to/event review-site-status
```

This returns exit 2 until current evidence, Site source version and successful
private deployment agree. Re-preparation resets the handoff status. Do not hand
off a local HTML placeholder as a tested mobile destination. Do not manufacture
browser results, user decisions or native publication evidence.

## Bring feedback into the next edit

The page offers one output with approve/reject comments and timestamped notes;
A/B remains reserved for substantially different editorial directions. Submitted
records are append-only, user-scoped and bound to the exact manifest/video/model
receipts. Changing a decision keeps its history. Notes do not reset a decision.
No passive viewing analytics, device guesses or inferred taste are collected.

Website feedback can be read through authenticated `/api/feedback` or the Sites
database tools: inspect the database overview first, then read bounded rows from
the exact returned table. Preserve the actual user text, timestamp and record ID
in private run evidence. Bring the latest explicit human decision into
`feedback-record` using the same current manifest and model receipts, with a
source reference to the Site URL/row ID. An annotation alone is not approval or
rejection. Do not import local test records as human feedback. Chat feedback uses
the same [feedback workflow](model-workflows.md), referencing the actual message.

General taste, voice changes, important user-facing preferences and model
promotions stay in the human loop. Ask when scope is unclear; a comment on one
version does not silently become a project-wide preference. Do not schedule
unattended reads or create recurring jobs unless requested.

## Supply an OpenRouter key from a phone

The private Site's `/connect` page accepts a key for the already authorized
candidate run. The password field stays in memory, clears after acknowledgement,
and never uses browser storage or URLs. D1 stores only an AES-GCM encrypted,
user/operation-bound handoff with a 30-minute retrieval window. Collected or
expired ciphertext is cleared on access; no cleanup background job is created.
Feedback and credentials use separate tables.

Configure `MOBILE_CREDENTIAL_ENCRYPTION_KEY` and
`MOBILE_CREDENTIAL_OPERATOR_TOKEN` as native Sites runtime secrets, then deploy
the saved source to apply the environment revision. Do not put their values in
source, local files, summaries or browser bundles. The owner-private platform
boundary and separate operation token both protect pickup. Store the operator
token in session memory and pass it through hidden stdin to
`scripts/run_mobile_candidate.mjs`, along with the native Site service credential,
exact operation/request hash, event workspace and approved budget. The helper
verifies current authorization/output bindings and refuses existing run evidence
before consuming a key. It sets the inference child's environment directly and
redacts the key from output; it never writes a credential file.

A corrected request uses a new work ID and authorization bound to that work ID,
comparison, prompt/rubric versions and request bytes. `verify-execution` mode checks
those bindings offline without reading the handoff or calling a provider. Keep
prior failed/interrupted work intact; creating a new ID does not itself authorize
another call. Record the actual human approval first.

If an operator session loses its token, renew that operation token through native
runtime settings for the actual authorized pickup, preserving the encryption key
and deploying the existing private version. Do not rotate merely to inspect state.
The user may submit a replacement handoff. Credential submission is not proof that
inference happened and never supplies editorial approval.

Local checks use synthetic secrets and keys only: Node's credential-box tests,
`scripts/verify-credential.mjs` against loopback and browser input/acknowledgement
checks. The shared pickup helper's verify-local mode accepts only its explicit
synthetic key fixture and cannot execute against a hosted origin. Inspect SQL and
Drizzle history; never copy local D1 test data into production.
