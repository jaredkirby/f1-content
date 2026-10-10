# Independent implementation review

Historical development evidence. Counts and run status describe the original production run; use the current README and `scripts/check` for source-development verification. Private archives are intentionally absent from a clone.

Reviewed `f1_pipeline/core.py`, `collect.py`, `catalog.py`, `analyze.py`, and `render.py` on 10 October 2026. The parent agent applied fixes during this review. This report separates the initial findings from their verified current status. No production implementation files were edited by the reviewer.

## Must-fix findings and current status

| Finding | Concrete failure | Current status |
|---|---|---|
| Original media hashes were not checked against acquisition records | `catalog()` recomputed a new digest and accepted changed source bytes as a new asset, losing the integrity link to acquisition | Fixed: current catalog rejects a missing/mismatched acquisition SHA-256. Regression passed |
| Cached proxies were accepted solely because a path existed | An interrupted FFmpeg write left a partial proxy; rerunning catalog skipped it and reported a derivative hash without probing it | Fixed for proxies: current catalog requires source/proxy digest receipt and probes newly created proxy duration. Regression passed |
| Analysis read raw files even when collection had rejected them | A failed refresh or cross-session response remained on disk; analysis ignored the successful-receipt set and could publish stale/invalid data as insights | Fixed: current analysis checks manifest event identity, each successful receipt/hash/session, required endpoint presence, and restricts optional telemetry to verified files. Regression passed |
| Render accepted stale editorial/catalog input from another event | The original guard checked only `config.id`; directly running render could use unrelated stored inputs and still label output Singapore | Fixed: render validates both input event IDs and source hashes. Regression passed |
| Final output was overwritten before successful completion | `ffmpeg -y` wrote straight to the delivered MP4 while an old manifest still referred to its previous bytes | Fixed for the final MP4: render writes a pending file, probes it and atomically replaces the delivered path. This is code-inspected, not fault-injection tested |
| Caption/EDL offsets accumulated raw speech time while scene concatenation included codec timing | Each scene's AAC priming/tail altered the final timeline, producing cumulative disagreement with the SRT and EDL | Fixed structurally: MOV intermediates now contain PCM audio, scene duration is quantized to 24 fps, AAC is encoded once. Independent synthetic measurement below confirms removal of accumulated video drift |
| Existing output manifests are not checked for event identity | Correct current inputs plus a stale `outputs/manifest.json` or `edit-plan.json` can retain the wrong `event_id` and another event's unrequested format | Fixed by parent: both documents are rejected if mismatched before rendering. All five review regressions passed with bundled Python |

The last issue is reproducible without media: provide matching current editorial/catalog IDs, put `event_id: wrong-event` in the existing manifest, and stub `render_one` to return a successful vertical record. The unchecked implementation then preserves the wrong manifest identity. The fix should cover both manifest and edit plan.

## Caption and audio timing experiment

The experiment generated nine short synthetic color/sine scenes in a temporary directory using the same FFmpeg codec/concat/loudness pattern, then removed the directory. These were diagnostic fixtures, not race media or playback acceptance.

| Pipeline | Planned duration | Final video duration | Final container/audio behavior |
|---|---:|---:|---|
| Original 0.503-second scenes, AAC per scene | 4.527 s | Not separately recorded | Container 4.721333 s |
| Duration quantized to 13/24 s, AAC per scene | 4.875 s | Not separately recorded | Container 5.021333 s |
| Duration quantized to 13/24 s, PCM in MOV, AAC only at final encode | 4.875 s | 4.875 s | Container/audio 4.900 s |

The corrected pipeline has a single 25 ms final audio tail in this experiment, not accumulating scene drift. Final QA should compare the actual video's timebase/duration and the EDL end, inspect subtitle changes near scene boundaries, and allow a documented small final audio-padding tolerance. Burned caption overlays are rendered from image durations and remain frame-quantized; they are not sample-accurate word alignment.

## Remaining improvements after current-run acceptance

These are tied to real code paths, but do not establish that the current inputs or renders are wrong.

- **Transform recipe identity:** Proxy receipts bind source and output hashes but not the scaling/codec recipe. A later change to transform settings can reuse an older valid proxy. Store a recipe version/hash before changing the transform. Contact sheets are still reused by existence; a partial/stale sheet can compromise visual review even if the proxy is sound.
- **Output-set transaction:** The MP4 is atomic, but captions, script, thumbnail, EDL, manifest and QA are separate writes. Failure after MP4 promotion can leave the old manifest or sidecars. Hash companion files, commit a run version together, and require QA's input hashes to match before reusing a previous pass.
- **Explicit reviewed source ranges:** `MATCHES` records approximate reviewed in/out ranges, while `render_one` chooses source out from narration duration and the full original duration. Current sources are incident-specific clips, but a longer narration can run beyond the catalog match's reviewed out point. Before generalizing, make exact allowed ranges part of the selected edit plan and validate them before rendering.
- **Stricter record identity:** Collection and analysis currently default a missing `session_key` to the configured key. Missing keys therefore pass the session test. Reject absent keys for endpoints that document them; resolve driver IDs from the successfully validated driver dataset before telemetry sampling.
- **Set completeness in result reconciliation:** `reconcile_results` uses a dictionary keyed by driver number, silently overwriting duplicate API records and not flagging extra drivers. Current final classification was crosschecked separately. A reusable reconciler should reject duplicate IDs and compare the complete driver sets.
- **Persisted visual review:** Catalog assigns `contact_sheet_pending` again on every run, while the matching code says clips were manually reviewed. Preserve review receipts keyed by source hash and time range so a rerun can distinguish unchanged reviewed footage from a new asset.
- **Estimate versus hard storage cap:** `render_one` preflights 350 MiB once; PCM scene intermediates, overlays and final output can collectively exceed that estimate. The current 8 GiB reserve is ample for this run, but per-stage estimates should use measured narration length and raster dimensions, with reserve checks between scenes for sustained runs.

## Regression tests

`tests/test_review.py` contains isolated temporary-file tests for source-hash mismatch, corrupt cached proxy, analysis of rejected cross-session data, stale editorial input, and an output manifest from another event. Network calls, real source files and active renders are untouched. Use the bundled Python with Pillow to execute the render tests; a plain Python without Pillow skips those two tests.

```sh
.venv/bin/python -m unittest discover -s tests -p test_review.py -v
```

This review does not certify factual narration, media reuse permission, visual layout or audible playback; those require the separately recorded output QA and viewing checks.

## Follow-up review: reusable qualifying release gates

Reviewed `analyze_session.py`, `render.py`, `validate.py`, `finalize.py`, `harness.py`, `__main__.py`, and `tests/test_session_pipeline.py` during the qualifying integration. This is an inspection snapshot before the parent's follow-up fixes. The eight added temporary-fixture regressions are in `tests/test_release_gates.py`; six failed at the reviewed snapshot. Existing 32 tests passed.

| Priority | Reproduced defect | Required correction |
|---|---|---|
| P1 | Finalization accepts an old render after its script changes, provided editorial review is updated to the new script. QA only binds catalog/editorial/manifest, and finalization never rechecks the videos' retained render input hashes | Require complete current-input bindings and verify them again immediately before finalization, including script, research, configuration and review receipts |
| P1 | Technical validation returns `passed` when render `input_hashes` and `companion_sha256` are absent. Finalization also accepts QA without `input_hashes` | Require the expected hash keys rather than iterating an optional empty dictionary; separate any intentional legacy compatibility from new release acceptance |
| P1 | Qualifying analysis accepts the catalog's stale reviewed ranges after `clip_review.json` changes, then stamps the new receipt hash onto those old ranges | Compare catalog review receipt hashes to the current review before using ranges. Do not replace provenance with a hash for a review that was never applied to that catalog |
| P1 | Rendering accepts an event-to-footage match whose `source_sha256` refers to an older asset. It then writes the current source hash into the EDL, hiding the stale association | Require the selected match's source hash/asset identity and review receipt to agree with the current catalog before reading footage |
| P2 | Qualifying reconciliation accepts an API `NaN` phase time as equal to the official finite time because `abs(expected - NaN) > tolerance` is false | Require finite positive numeric times on both sides before comparing; reject booleans as times |

Two new regression gates passed: a failure rendering the second requested format leaves the previous authoritative manifest and versioned EDL byte-for-byte intact, and finalization refuses a missing requested format. The manifest is now the authoritative commit point for versioned media and sidecars, which addresses the earlier output-set transaction finding.

The transform-recipe, original-hash, reviewed-range persistence, exact session identity and duplicate-driver improvements described earlier in this report are now implemented and covered by `test_hardening.py`/`test_session_pipeline.py`; the earlier improvement list describes the prior snapshot, not their latest state.

Additional non-blocking observations: harness receipts use `passed` for a successful collection operation even when its result is explicitly `partial`; the stage result should preserve that distinction for operators. The classification-lap lookup selects the latest lap with a matching official duration rather than checking a session-part time window, so it should label this association as duration-matched inference unless phase boundaries are verified. Neither observation proves that the retained qualifying dataset is incorrectly classified.

### Fix verification

The parent subsequently delegated these four implementation files to the reviewer. All six reproduced release failures are now fixed in `analyze_session.py`, `render.py`, `validate.py`, and `finalize.py`. New renders require hashes for config, current clip review, script, event research, catalog, editorial, original files, and optional retained mapping/data/sector manifests. QA verifies every captured input and all three companion files; finalization repeats those checks, requires the QA receipt to contain the same inputs, and checks the exact versioned EDL. A concurrent input change prevents render's manifest commit. Source matches and EDL scenes retain both original and review hashes.

Compatibility is explicitly limited to the pre-versioned `2026-singapore-sprint` delivery with its original output filenames. This exception does not apply to qualifying or new versioned output. Existing Sprint files were neither regenerated nor changed during these fixes.

Verification: **44 pipeline tests passed**, including positive technical-QA and repeat-finalization fixtures, interrupted-render preservation, changed config/review/additional-input rejection, and incomplete hash/format rejection. **Nine separate Jev adapter tests passed**. These tests use temporary synthetic fixtures and mocked codec calls where appropriate; real qualifying render, decode, visual and playback acceptance remain separate integration steps.

### Sprint compatibility, timeline and harness follow-up

Sprint analysis now binds event-media associations to both the acquired original SHA-256 and the current catalog review receipt. Historical selections are intersected with separately reviewed intervals, excluding unreviewed lead-in frames and gaps; adjacent intervals are not silently widened. Five tests cover those bounds, strict-render compatibility, stale originals/reviews and missing acquisition hashes. Existing Sprint outputs remain untouched. A future complete Sprint reprocess still needs explicit normalization of its historical review endpoints, some of which exceed the retained original durations by approximately one frame; strict catalog correctly rejects those old endpoints.

The parent corrected timeline issues identified in review: finalized labels require current release inputs, complete formats, QA and actual EDL hashes; publisher captions require downloaded status and matching hashes; cached posters require their own matching digest. Six independent temporary-fixture timeline tests pass. The page is deliberately curated for Singapore Main Qualifying and now rejects another event ID.

The harness now checks required inputs before executing a stage, records explicitly missing optional Sprint mapping/script inputs and package-code fallbacks, preserves a `partial` collection result without aborting on optional source failures, requires declared outputs, distinguishes unchanged output files, and follows the manifest's authoritative versioned EDL. Eight harness regressions cover these behaviors and reject escaped EDL paths. Current suite: **63 pipeline tests and nine Jev adapter tests passed**. No active event outputs were mutated by these tests.
