# Narration and optional robot voice

The explicit speech commands prepare, import or generate narration, then select
clean audio or a vocoder derivative for rendering. The existing Samantha renderer
remains the default when a format has no prepared selection. `render` and `run`
never call ElevenLabs. These commands do not establish human voice acceptance.

## Prepare a script-bound request

Use a durable event workspace with a reviewed `research/event/video_plan.json`.
The helper copies exact scene narration, records the plan hash and sets explicit
limits. It refuses to overwrite an existing request. Generation never rewrites
the editorial script; pronunciation changes belong in a reviewed script revision
or a pinned provider dictionary.

```sh
.venv/bin/python scripts/prepare_narration_request.py \
  --workspace /absolute/event --job-id voice-pilot-01 --format vertical \
  --provider imported
./scripts/f1 --workspace /absolute/event speech-prepare \
  --request research/event/narration-request.json
```

`speech-prepare` is read-only: it reports the canonical request SHA-256, remaining
scene calls/characters and validated cache hits. It reads no credential. Each
scene is at most 2,000 characters; prepared/effected narration is at most 180
seconds per format. Different formats use different request/job IDs. Preparation
requires the reviewed JSON plan rather than the historical Sprint code fallback.

## Import existing audio

Import takes an exact request binding, operator provenance, one source audio/hash
per scene and reviewed caption timings. All paths are within the selected event.
Missing provider/cost observations remain unknown; imported Voice Lab metadata
is not a provider-attested execution receipt. Preserve the source audio in the
workspace before creating this bundle:

```json
{
  "schema_version": "f1.narration_import.v1",
  "request_sha256": "CANONICAL_SHA_FROM_PREFLIGHT",
  "provenance": {"kind": "operator_import", "reference": "Actual recording or generation reference"},
  "scenes": [{
    "id": "EXACT_SCENE_ID",
    "audio": {"path": "research/event/voice.wav", "sha256": "FILE_SHA256"},
    "reviewed_by": "ACTUAL_TIMING_REVIEWER",
    "captions": [{"start": 0.1, "end": 2.4, "text": "Exact planned narration."}]
  }]
}
```

```sh
./scripts/f1 --workspace /absolute/event speech-import \
  --request research/event/narration-request.json --bundle research/event/voice-import.json
```

Imports retain original bytes and fully decode a 48 kHz mono PCM16 derivative
using FFmpeg/ffprobe. Captions must cover the exact planned text, be finite,
monotonic and within the measured audio. Partial, changed or escaping files fail.

## Explicit generation

For prepared system speech use the helper with `--provider say`. Run
`speech-execute --request … --execute`. Samantha at 172 words/minute is recorded;
short phrase generations provide measured caption boundaries. System-speech
preparation needs macOS `say` and FFmpeg, but can later feed the vocoder.

For ElevenLabs, supply `--provider elevenlabs --voice ACTUAL_ID --settings
research/event/voice-settings.json` to the helper. The explicit settings object:

```json
{
  "output_format": "mp3_44100_128",
  "voice_settings": {"speed": 1, "stability": 0.5, "similarity_boost": 0.75, "style": 0, "use_speaker_boost": true},
  "seed": null,
  "apply_text_normalization": "auto",
  "pronunciation_dictionary_locators": []
}
```

The model defaults to `eleven_multilingual_v2`; set `--model` explicitly for a
different candidate. Eleven v3 accepts only `{"stability": 0}`, `0.5` or `1` in
`voice_settings`. Unsupported controls are rejected rather than silently changed.
Pinned dictionaries require `pronunciation_dictionary_id` and `version_id`.
Account voice/model and format eligibility must be checked for the real pilot.
Seeds are not a guarantee of identical regeneration.

Hosted execution requires `--execute` and a saved human authorization bound to
the canonical request SHA, provider, maximum calls, submitted characters and
credit ceiling. Use an actual account/model rate reference, not this example's
placeholder. The ceiling is calculated from the reviewed credits-per-character
rate; it is not a provider-enforced spend limit or a measured bill. USD and actual
charged credits stay null when the response does not expose them.

```json
{
  "schema_version": "f1.narration_authorization.v1",
  "request_sha256": "CANONICAL_SHA_FROM_PREFLIGHT",
  "source": {"kind": "human", "reviewer": "user", "reference": "ACTUAL_APPROVAL_REFERENCE"},
  "provider": "elevenlabs",
  "max_calls": 2,
  "max_characters": 2000,
  "max_credits": 2000,
  "credits_per_character": 1,
  "rate_reference": "ACTUAL_ACCOUNT_MODEL_RATE_AND_DATE"
}
```

```sh
./scripts/f1 --workspace /absolute/event speech-execute \
  --request research/event/narration-request.json \
  --authorization research/event/voice-authorization.json --execute
```

Provide `ELEVENLABS_API_KEY` through the process environment or use the separate
`org.f1-content.elevenlabs` login-Keychain item. Rebuild the helper with
`.venv/bin/python scripts/build_keychain.py`, then use
`.venv/bin/python -m f1_pipeline.credentials store --provider elevenlabs` for
hidden entry. This never reads OpenRouter's key. No secret goes into CLI values,
request JSON, run receipts or browser assets. See [credentials](credentials.md).

The adapter uses the [official timing API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps)
with no redirects or retries. It preserves original audio and character alignment,
then maps the original-text timing to readable captions. Missing alignment or a
different returned text fails; normalized-text alignment is never guessed.
Successful runs also create provider-neutral audio model-work receipts for the
existing [feedback and evaluation](model-workflows.md) workflow.

## Select clean audio or optional vocoder

For clean speech save `research/event/narration-effect.json`:

```json
{"schema_version": "f1.narration_effect.v1", "kind": "none"}
```

For robot speech, keep Voice Lab's GPL source in an independent checkout. Supply
its absolute `dist/dsp.js` path and record that file's SHA-256 in the recipe. F1
packages only its own headless invocation wrapper, not the external DSP code.
Do not silently download a module or use a different processor version.

```json
{
  "schema_version": "f1.narration_effect.v1",
  "kind": "robot_vocoder",
  "processor_sha256": "EXACT_EXTERNAL_DSP_FILE_SHA256",
  "options": {"mode": "single", "note": 43, "brightness": 0.6, "clarity": 0.48,
              "wet": 0.5, "tempo": 100, "echo": 0.1,
              "progression": "minor", "progressionBeats": 1}
}
```

Supported modes: `single`, `chord`, `melody`, `progression`. Note: MIDI 36–72;
tempo: 60–180 BPM; brightness/clarity/wet/echo: 0–1. Progressions: `minor`, `pop`,
`warm`, `cadence`; beats per chord: 1, 2, 4. Every effective setting is saved.
Speech speed belongs to generation, not DSP. Node and the external module are
needed only during vocoder processing, never during rendering.

```sh
./scripts/f1 --workspace /absolute/event speech-process \
  --request research/event/narration-request.json --effect research/event/narration-effect.json \
  --dsp-module /absolute/robot-voice-lab/dist/dsp.js
./scripts/f1 --workspace /absolute/event render --format vertical
./scripts/f1 --workspace /absolute/event validate
```

Omit `--dsp-module` for `none`. Disabled processing bypasses DSP; zero wet mix
with the vocoder selected still normalizes. Processing stitches clean scenes at
24 fps boundaries, runs DSP once at Voice Lab's 22.05 kHz rate, then restores
48 kHz and splits renderer slices. Echo adds one 0.6-second tail at the end,
padded to the frame grid. Speech captions end with the speech, before the tail.
Each recipe revision reuses clean source audio with zero TTS calls.

Selections live in `research/event/narration-selection.json` by format. Prepare
both selections before rendering `--format both`; a format without a selection
uses the existing system narration. A change invalidates prior render/review
bindings; rerender all desired outputs together for consistent current inputs.
Stale selections fail closed. To return a format to legacy Samantha rendering,
explicitly remove that format's selection from the registry (remove the registry
when none remain), then rerender; never relabel old approval as current.

## Results, failures and acceptance

`runs/narration/<job-id>/` retains the frozen request, intent, provider/import
receipts, originals, clean WAVs, timings and effect versions. `result.json` is
published only after validation; the current selection is a separate atomic
commit. The event workspace maintains its configured disk reserve. A job ID is
never reused after a partial or possibly billed execution. Inspect receipts
before authorizing a new job. Validated successful scene caches can be reused
within the same workspace across jobs and formats; changed bytes fail closed.

Render manifests/EDLs bind the selected narration files and receipt hashes.
Audio model-work links follow the exact video into the mobile review destination.
Technical checks do not establish voice quality. Use one version-bound private
[phone review destination](mobile-review.md), record actual playback/caption,
annotation and decision checks, then collect approve/reject comments. Voice or
effect defaults require explicit human promotion. No real hosted speech or phone
acceptance is claimed by the offline test suite.
