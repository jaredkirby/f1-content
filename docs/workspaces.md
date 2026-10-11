# Event workspaces

Shared Python code operates on one selected event directory. Runtime JSON paths
are relative to that directory; stored manifests must not repeat its outer path.
Use an absolute external directory or an ignored `workspaces/<event-id>/` directory
for new work. Existing local Singapore archives remain where they were created.

For official live-blog collection, use the separate [live feed](live-feed.md)
workspace contract with `config/live.json`; those records are not film inputs
until explicitly researched and reviewed. [Project state](project-state.md)
identifies which newer `main` commands are absent from this checkout.

## Prepare inputs

Copy the *shape* of `examples/synthetic/config/event.json`, replace every fictional
identity with verified year, country, exact session name, date and pinned OpenF1
meeting/session keys, then review resource limits. An empty `telemetry_samples`
requests no car-data samples. Do not run collection against the fictional example.

| Required input | How it is produced |
|---|---|
| `config/event.json` | Explicit verified event identity, formats and resource bounds |
| `research/media/sources.json` | Bounded discovery inventory with publisher URLs, relevance and rights status; downloaded rows carry relative file path, bytes and SHA-256 |
| `research/media/downloads/` | Preserved authorized source files, separate from derived proxies |
| `research/media/clip_review.json` | Actual visual/caption observations, current source hashes and finite reviewed intervals |
| `research/event/event_bundle.json` | Researched timeline, results, ideas, evidence locators and gaps |
| `research/event/media_matches.json` | Reviewed, hash-bound event-to-footage associations for the session path |
| `research/event/video_plan.json` | Reviewed event-specific narrative and edit instructions |

The [workflow contract](workflow-design.md) and
`tests/test_release_gates.py` provide field-level examples. Tests use synthetic
bytes to exercise contracts; they do not create valid film assets. There is no
one-command generic event authoring scaffold yet.

## Execute and review

```sh
./scripts/f1 --workspace /absolute/path/to/event doctor
./scripts/f1 --workspace /absolute/path/to/event collect
./scripts/f1 --workspace /absolute/path/to/event catalog
./scripts/f1 --workspace /absolute/path/to/event analyze
./scripts/f1 --workspace /absolute/path/to/event prepare-jev
./scripts/f1 --workspace /absolute/path/to/event render --format both
./scripts/f1 --workspace /absolute/path/to/event validate
```

`collect` obtains configured OpenF1 data. It does not discover or download arbitrary
social video. `catalog` processes an existing reviewed media inventory. One-off
discovery/research scripts from the original sessions remain in their local
archives; they are not a reusable public crawler. `prepare-jev` writes validated
requests only. `run` chains collection, catalog, analysis, render, validation and
report; it does not perform missing research or finalize a release.

The renderer uses macOS `say`, the Samantha voice, system fonts, FFmpeg and ffprobe.
Linux can run offline tests and supported data stages; native narration rendering
has not been ported. `doctor` reports tool paths and validates config, but is not a
render acceptance check. Install external tools separately and honor the reserve.

Inspect the films, representative frames, captions and audio. The local helper
`scripts/audit_outputs.py` accepts absolute `F1_WORKSPACE` and creates frame sheets
and loudness measurements; its output still requires review. Record current
editorial, visual and audio reviews, then run `finalize`. Do not fabricate review
receipts to make a gate pass. Finalization binds the authoritative versioned
manifest; top-level convenience files may not be current.

The qualifying `timeline` builder intentionally accepts the curated Singapore
main Qualifying identity. The legacy Sprint page builders under `scripts/` assume
the original root archive. Supporting another event's presentation requires a
deliberate change and tests. Building HTML, registering hosting and deploying it
are separate actions. Source code licensing does not clear embedded footage.

## Recover or rerun

Read `runs/stages/` and `data/processed/data_manifest.json` for actual failures or
partial coverage. Fix the failed input and rerun that stage. Verified derivatives
may be reused only when source, recipe and output hashes match. Changed inputs
invalidate downstream review; do not relabel old QA as current. Keep failed
receipts and originals. Historical Sprint review endpoints need normalization
before strict reprocessing, as documented in the hardening history.
