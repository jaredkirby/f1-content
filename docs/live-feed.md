# Live race feed

The explicit `live` command collects a pinned official F1 live blog, backfills its
complete available public article history, retains corrections and creates one
sourced editorial draft through Codex CLI's saved ChatGPT login. It never calls an
API-key model provider or guesses an unavailable OpenF1 session key.

## Workspace and run

Use a separate durable event workspace. `config/live.json` deliberately differs
from `config/event.json`: a live-blog event UUID is not an OpenF1 timing key.

```json
{
  "event_id": "2026-singapore-race",
  "name": "Singapore Grand Prix 2026",
  "event_date": "2026-10-11",
  "session_name": "Race",
  "source_page": "https://www.formula1.com/en/latest/article/live-coverage-formula-1-singapore-airlines-singapore-grand-prix-2026.64UBFhKsSsN0V9RoD8JQqx",
  "source_event_id": "ca06b2a8-6d7f-4f6e-a8fb-7d7c6d00e607",
  "history_url": "https://cdn.monterosa.cloud/events/ca/ca06b2a8-6d7f-4f6e-a8fb-7d7c6d00e607/history.json",
  "stop_at": "2026-10-11T15:00:00Z",
  "poll_seconds": 45,
  "model_seconds": 180,
  "reserve_bytes": 8589934592,
  "storage_budget_bytes": 134217728
}
```

Verify the source page's exact year, Race identity and embedded event ID before
configuring it. All network destinations are fixed to the supported public source;
redirects are refused. For another event supply its verified binding and deadline.
The example is a real historical binding; do not treat it as a current live race.

```sh
./scripts/f1 --workspace /absolute/event live --once --no-model
./scripts/f1 --workspace /absolute/event live
.venv/bin/python scripts/live_feed.py --workspace /absolute/event --port 8766
```

The helper serves only `/`, `/index.html` and `/feed.json` on `127.0.0.1` while the
collector runs. Open `http://127.0.0.1:8766`. This address is local to this Mac;
it is not accessible from a phone or a hosted review destination. Ctrl-C or SIGTERM
stops polling. The runner waits for any active model request to finish or reach
its timeout before writing the final stopped report and releasing its lock. The
report stays on disk. The server stops after that cleanup.
The writer PID is recorded in `runs/live/writer.lock` and the feed status. Before
signaling a PID, verify it still belongs to this exact workspace/process.

Each invocation stops starting polling cycles at the configured UTC deadline or
three hours after launch, whichever comes first. A started source retrieval or
model request may finish after that deadline; it is not a hard process deadline. `--once` intentionally executes one catch-up cycle even if
the deadline has passed. No login is created, no persistent scheduler is installed,
and no source/media publication occurs. Explicitly renew `stop_at` to run another
race. A second writer refuses the lock rather than racing an existing collector.

## Evidence and freshness

`runs/live/feed.sqlite3` retains every normalized public article content revision,
current snapshot membership and successful/failed polls. Snapshot hashes bind
revisions to complete raw responses under `runs/live/snapshots/`. Unchanged raw
responses reuse content-addressed bytes. `latest-receipt.json` records the last
retrieval URL, time, byte count and hash. Full snapshots catch late arrivals and
corrections on restart; there is no cursor that can skip a late report. Withdrawn
records leave the current view while older revisions remain recoverable.

Non-article records (social posts, external articles, audio, video) and records
without explicit public access are excluded from editorial claims. Their original
metadata remain in the raw snapshot, not proof that their linked contents were
acquired or watched. Backfill covers this source's available history, not all
possible race data. The collector does not download race footage, radio or paid
telemetry. OpenF1 live timing requires separate authenticated access; see the
[official documentation](https://openf1.org/docs/).

Malformed, empty, oversized and mismatched-date snapshots preserve previous data.
Network failures leave the view stale, retain a failed poll, and retry on the next
configured polling cycle (45 seconds by default). This bounded cadence does not hammer failed endpoints. Responses
are capped at 8 MiB. Before each retrieval, the runner checks the existing
`runs/live/` size plus an 8 MiB response allowance against a 128 MiB default
budget, and checks an 8 GiB default free-space reserve. This is a retrieval gate,
not a hard workspace quota: SQLite growth, failed-poll records, model artifacts
and `outputs/live/` are not all reserved by that allowance. A failed gate leaves
previous data visible with an error. The prototype has no automatic retention
or deletion; monitor disk use and stop explicitly when needed.

`outputs/live/feed.json` and `index.html` form the local read model. The browser
refreshes every 15 seconds and computes stale age locally, including when the
writer dies. It supports driver/moment search, oldest/newest order, expandable
source reports and links from editorial moments to their exact source entries.
Source publication time, update time and observation time remain separate.

## Subscription model work

The supported [Codex non-interactive interface](https://learn.chatgpt.com/docs/non-interactive-mode)
reuses saved authentication. The adapter checks `codex login status`, requires
ChatGPT login, removes API key variables, forces OpenAI/ChatGPT authentication and
disables shell/delegation and runs read-only, ephemeral, schema-constrained model work with a 240-second timeout.
It ignores user provider configuration to avoid accidental alternative billing.
No API or other-provider fallback exists. Collection continues in the main thread
while one model task runs independently. New briefs are requested only on changed
evidence and at least `model_seconds` between attempts (180 seconds by default).
The first changed-evidence request can start immediately, regardless of host
uptime. A restart resets the in-process interval; a matching saved brief is reused.

`runs/live/model/<work-id>/` retains the exact evidence, schema, response, CLI
execution events and started/failed/complete receipt. Input/output hashes and observed token usage bind
model work; unexposed model identity remains unknown; moments must cite current source IDs and pass shape/size checks.
Unknown cost and human acceptance stay unknown. Model output is a draft: reference
validation is not independent factual or editorial approval. A brief built on an
older snapshot is labeled with its earlier evidence version while a new one runs.
A changed or withdrawn source invalidates current binding; it never inherits
human acceptance. Model failures retain the last successful brief and an error.

## Integration boundary

This prototype adds an explicit feed entrypoint, not an automatic router to `run`.
Its source IDs/revisions can later support researched timeline segments, ranked
ideas and an event bundle, but automatic video assembly must still wait for
reviewed footage, exact intervals and all existing release gates. No film manifest,
clip review, review destination or existing event bundle is rewritten. A future
video pilot still needs the [mobile review](mobile-review.md) contract, including a
verified private HTTPS destination and actual human feedback.

The 11 October pilot began after the source's 13:46:44 UTC finish report. Its
receipts establish race-history catch-up and live post-race polling, not observation
of the race as it happened or final FIA classification.
