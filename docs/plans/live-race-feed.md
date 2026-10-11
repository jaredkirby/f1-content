# Live race feed

Date: 2026-10-11. Status: implemented and verified at the pilot checkpoint.
Process activity is transient; this record is not proof that a collector is running.
See [project state](../project-state.md) for the later local observation.

## Objective

Backfill Singapore Grand Prix coverage, continuously collect new updates and
produce grounded editorial briefs with Codex authenticated through ChatGPT.
Preserve Sprint/Qualifying archives and existing film release contracts.

## Decisions

- A dedicated race workspace uses `config/live.json`; unavailable OpenF1 session
  metadata does not justify guessing a timing session key.
- Official F1 page binds the Monterosa event ID and publicly accessible history.
  Fetch only public article records; restricted records are excluded. OpenF1
  returned 401 and the timing archive 403. No access control bypass or paid source.
- Full history each poll backfills missed/late records and corrections. SQLite
  atomically commits current membership and immutable content revisions. Retain
  content-addressed raw snapshots and retrieval/hash receipts.
- One locked writer, bounded runtime/storage, disk reserve, visible freshness,
  failed fetch receipts, resumable state and explicit UTC stop.
- Subscription-only Codex CLI model work, bounded intervals, hash-bound evidence
  and validated source references. Failed model work never becomes a summary.
  No API fallback, automatic film approval or publishing.
- The source reported the finish at 13:46:44 UTC, before this run. This execution
  is race backfill plus continuous post-race coverage, not in-race observation.

## Current outcome

The dedicated race feed backfilled 90 public article reports and observed new
post-race arrivals, taking the current view to 92. A real ChatGPT CLI draft and
revision completed with cited source IDs and observed token usage. The first
attempt failed a field-size check; its evidence remains retained. Repeated live
polls and a process restart preserved SQLite revisions and source snapshots.

The pilot was configured for 45-second polling until 15:00 UTC on 11 October, with independent
model work on changed evidence at least 180 seconds apart. The local loopback
report displays collection freshness and earlier-evidence briefs. No separate
paid model/provider, timing subscription, publication or film release was added.

## Next action

Review the draft with the user; use the recorded live-blog binding and a new
explicit UTC deadline for a future race. Authenticated telemetry or a hosted
phone destination would be a separate integration. No editorial acceptance is
inferred from this technical completion.

## Verification

- Ten focused offline regressions: restart/late arrivals/corrections/withdrawals,
  malformed/failing sources, public-only normalization, identity, writer lock,
  source references, subscription-only auth and collection during pending model work.
- `scripts/check`: all 167 tests, synthetic smoke checks and index guard passed.
  Changed/untracked source contents also pass `repo_guard.inspect_blob`; diff
  whitespace checks pass. No event/runtime data staged or committed.
- Real public history fetch, multiple successful polls, source binding evidence,
  model input/output hashes and token usage retained in the ignored race workspace.
- Browser: source history, search, ordering, model brief and changing-evidence label
  observed; widths 320/390/768 have no horizontal overflow. Local report only;
  no actual phone acceptance or video playback claimed.
