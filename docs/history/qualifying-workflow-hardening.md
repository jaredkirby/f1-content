# From the Sprint prototype to an isolated qualifying workflow

Historical development evidence. Counts and run status describe the original production run; use the current README and `scripts/check` for source-development verification. Private archives are intentionally absent from a clone.

The Singapore main Qualifying repeat run completed local production and release QA on **10 October 2026**, session **11384**. Both videos reached the end in the browser, technical and measured-audio checks passed, and finalization accepted current hash-bound reviews. The private qualifying timeline (private deployment; local receipt only) is deployed and ready to open on a phone with the same ChatGPT account. The root Sprint workspace retains its event identity and delivery history.

The Sprint run established the research-to-video path, but some of its implementation and documentation assumed one event, one collection recipe and fixed editorial scripts. Qualifying required explicit phase handling and stronger checks against stale reviews, stale inputs and incomplete output sets. The current code implements the contracts below; the earlier findings in [code-review.md](code-review.md) describe their historical snapshots.

## Implemented contracts

| Earlier limitation or failure mode | Current implementation | Relevant checks |
|---|---|---|
| Workspace rooted in the package; changing event configuration could mix Sprint files with a new session | `F1_WORKSPACE` requires an absolute resolved directory. `scripts/f1 --workspace` selects it explicitly. Exact event/date/session/meeting identity is required; path traversal and escaping symlinks are rejected | `test_hardening.py`: workspace, configuration, session and record identity tests |
| Race-specific collection assumptions and implicit telemetry selection | Qualifying omits the starting-grid endpoint. Telemetry is requested only for configured driver/lap intervals after verified driver/lap responses; failed fetches cannot use stale disk data | `test_hardening.py`: qualifying endpoint plan, explicit telemetry and stale driver-fetch tests |
| Existing derivative files could be trusted merely because they existed | Proxy/contact receipts bind original hash, transform recipe, derivative hash and byte count. New derivatives are probed and fully decoded before replacement; failed generation preserves the prior output | `test_hardening.py`: corruption, recipe change, atomic replacement and valid-cache tests |
| Source observations could remain attached after original bytes changed | Catalog verifies original SHA-256 and review identity/path/ranges. Review intervals must be finite and within the original duration; reviewed ranges survive cache hits | `test_hardening.py`: stale review, out-of-range and cache-hit review tests |
| Race result logic did not represent Q1/Q2/Q3 classification | Qualifying compares complete driver sets, positions and each phase's valid time. Duplicate records, nonfinite values and invented no-time results are rejected. Hadjar's display slot remains distinct from his official unclassified position | `test_session_pipeline.py` and `test_release_gates.py`: phase reconciliation, duplicate driver and no-time tests |
| A changed review could be stamped onto old catalog ranges | Analysis checks the catalog's review-receipt hash against the current review before using associations | `test_release_gates.py`: changed-review rejection |
| A scene could silently use an updated source behind an old association, exceed reviewed footage or cite an unknown event | Analysis and rendering require current source/review bindings, source-to-asset identity, valid event/claim links and intervals contained in both the event association and reviewed footage | `test_session_pipeline.py` and `test_release_gates.py`: scene bounds, orphan claims and older-source rejection |
| Atomic MP4 replacement alone did not keep captions, scripts, thumbnails and EDL together | Every render writes to `outputs/versions/<run_id>/`; `outputs/manifest.json` commits the selected bundle only after all requested renders finish and inputs remain unchanged. Sidecars and the versioned EDL have hashes. The top-level EDL is a convenience copy | `test_release_gates.py`: failure of the second format preserves the previous manifest and versioned EDL |
| A technically valid older video could pass finalization after a script, configuration or review changed | Mandatory render input hashes cover configuration, research, script, review, editorial and catalog inputs, plus present optional data/mapping files. Validation and finalization recheck these bindings and required companion hashes | `test_release_gates.py`: missing bindings, changed script/config/review, extra captured input and missing requested format tests |
| An artifact-presence summary could be mistaken for executed orchestration | The harness writes a receipt for each real stage execution, with event ID, input/output hashes, timestamps and failure reason | `f1_pipeline/harness.py`; actual receipts in the selected event's `runs/stages/` |
| A Jev integration plan could be mistaken for actual model decisions | `prepare-jev` validates per-asset request payloads and records `actual_model_inference:false`. Analysis identifies editorial/rule provenance. Provider inference is separate and never silently substituted | Adapter contract tests in `tests/test_jev_adapter.py`; request index records actual preparation |

The output manifest is the authoritative commit point, not the latest directory or filename. Downstream validation follows its versioned EDL and media paths. A narrowly scoped compatibility branch permits the retained pre-versioned Singapore Sprint release; new qualifying releases require the current bindings.

## Actual evidence at this checkpoint

The qualifying acquisition retained **23 original videos / 219,992,111 bytes**, 22 caption tracks, 23 sampled visual reviews and 34 editorial intervals. The six supplemental source outcomes and 35 exclusions remain explicit. No media bytes were changed during manifest-path normalization.

The initial qualifying catalog attempt rejected paths that still contained the workspace prefix. All media filesystem references were then normalized to event-relative `research/media/...` paths, and `event_ids` aliases were added to preserve timeline associations through the catalog schema. Direct use of `catalog.sources_list` and `catalog.review_ranges` under the qualifying `F1_WORKSPACE` subsequently verified **23 original hashes, 34 intervals and 305 filesystem path values**, with zero errors. See the event's `research/media/path_normalization_receipt.json`. The subsequent catalog and versioned render stages have produced their artifacts; this path/schema check is not final output QA. Failed stage receipts remain retained, including the initial path failure and an analysis attempt before catalog completion, as evidence that prerequisites were enforced.

The qualifying data manifest records **11 successful verified endpoint receipts**, zero failures, 22 entrants, 363 lap records and **688 bounded car-data samples** across Verstappen lap 11 and Leclerc lap 24. These are actual local acquisitions, separate from proposed workflow capabilities.

The retained Sprint logs show **11 pipeline tests passed** in `runs/pipeline-tests.txt` and **9 offline Jev adapter tests passed** in `runs/jev-tests.txt`. The independent qualifying review documented a later **32-test passing baseline** followed by eight release-gate regressions, six initially failing. Those historical failures motivated the currently implemented binding checks. They must not be presented as either a current failure count or a completed qualifying release.

The final retained suite rerun passes **63 pipeline tests and 9 offline Jev adapter tests**, including Sprint compatibility, timeline integrity and harness contracts. Logs are retained with this qualifying run.

The current tree contains tests across `test_core.py`, `test_review.py`, `test_hardening.py`, `test_session_pipeline.py` and `test_release_gates.py`. Reproduce the suite with the bundled Python so Pillow-dependent rendering guards are exercised:

```sh
# From the source checkout
F1_TEST_PYTHON=.venv/bin/python
"$F1_TEST_PYTHON" -B -m unittest discover -s tests -v
"$F1_TEST_PYTHON" -B -m unittest discover -s tests -p 'test_jev_adapter.py' -v
```

These temporary-fixture and mocked-transport checks verify contracts and regressions. They do not establish factual narration, real provider quality, source reuse permission, full source playback, or acceptance of the qualifying edits.

## Remaining boundaries

Research agents still perform discovery, source interpretation, timeline construction and editorial review. The deterministic runner executes collection, processing, arithmetic, assembly and validation; it is not an unattended web-search or agent service. A new event requires a new research bundle, discovered-source inventory, reviewed associations and script, not just a changed session key.

Two nonblocking review observations remain relevant to operators: the generic stage harness can report a successful operation as `passed` even if the collection result inside its manifest is `partial`, so inspect both; and classification-lap association uses the latest matching official duration, so treat that association as an inference unless phase boundaries are separately verified. The retained qualifying event research independently records phase boundaries.

Jev requests can support session matching, labeling, evidence support and editorial scoring after observations exist. There has been **no live Jev inference** in this qualifying run, and no held-out F1 quality evaluation has been completed. Deterministic calculations and editorial judgments remain labelled accordingly.

Final technical validation, independent editorial review, rendered visual/playback review, measured audio checks and `finalize` have **passed**. Finalization binds those checks to the exact delivered files. User playback acceptance is never inferred. Public availability does not supply publication clearance, and no access-control bypass forms part of this workflow.

## Final verification for the repeat run

- 63 pipeline regression tests and 9 offline Jev adapter tests pass. Exact logs are in the event `runs/pipeline-tests.txt` and `runs/jev-adapter-tests.txt`.
- The final 61.8-second vertical and 150.5-second landscape masters pass complete decode, H.264/AAC compatibility, caption order/bounds and audio/video end alignment. Measured loudness is -16.11 and -16.09 LUFS, respectively; true peaks are -1.50 dBTP.
- Every scene midpoint was visually inspected. Both masters reached browser `ended=true` with no media error. This is agent verification, not inferred user acceptance.
- A real cache repeat processed all 23 assets without invoking derivative generation; canonical catalog and analysis hashes were unchanged.
- The page has 13 events, 6 story outlines and 34 selected excerpts. Widths of 320 and 390 pixels have no horizontal overflow. Filter, expansion, theme, clip playback and pause-on-collapse behavior pass. All 575 local references resolve, and no hosted file exceeds 25 MiB.
- The original Sprint masters still match their retained hashes; its Site checkout remains clean.

Remaining boundaries are deliberate: discovery is bounded, not an unattended search service; Jev has 23 validated requests but no live inference without a provider credential; the current presentation copy is curated for this qualifying event and rejects another event identity. Source reviews are sampled observations. The private Site is published as a versioned deployment, although local preview asset rebuilding still occurs in place. Historical Sprint reprocessing requires its old review endpoints to be normalized before strict catalog ingestion; retained Sprint outputs remain usable.

The first native hosting upload exposed a transport limit: the 161 MiB package did not upload within the service's 60-second window. Phone derivatives now use bounded video/audio bitrates and a 60 MiB total package gate. Full-resolution masters and downloaded originals are unchanged. Source-repository credentials are refreshed after expiration; retries retain the same Site identity and reconcile saved versions before another publication attempt.
