# Jev research and F1 integration

Provider research checkpoint: 10 October 2026. Current `main` includes an
OpenRouter native Jev route and recorded live advisory controls; see [project state](project-state.md).
The direct adapter and initial research observations below remain a separate contract.

Verified 10 October 2026. The canonical Jev provider is **TypeSafe AI**, at `typesafe.ai`, with documentation at `docs.typesafe.ai` and SDK repositories under `github.com/typesafe-ai`. The [provider announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev) links directly to the documentation and console. Several similarly named search results explicitly describe themselves as independent services; their endpoints and credentials are not interchangeable.

## What it can do here

Jev makes bounded decisions from text and structured state. It returns choices, rubric scores, or yes probabilities. It cannot watch the race footage, transcribe audio, write the script, or render an edit. Frame inspection and transcription must produce referenced observations first. Use ordinary code for exact calculations, timing alignment, download policy and execution. [Model specification](https://docs.typesafe.ai/models), [known limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13).

The official API is `POST https://api.typesafe.ai/v1/systemone`, authenticated with a bearer `TYPESAFE_API_KEY`. Send `state`, `model`, and `questions`; returned answers retain question IDs. `Choice` has up to 255 options, `Score` has 2–10 ordered levels, and `Noul` returns a number from zero to one. [API reference](https://docs.typesafe.ai/api).

The current documented model is `jev-1.13.0`; the adapter pins it. The documented price is $0.042 per million input tokens, with free output tokens. The documentation lists a 64K total context and a 32K limit for state plus the longest question. These are provider terms checked today, not measured local performance. [Models](https://docs.typesafe.ai/models).

No official downloadable Jev weights or free unauthenticated inference path was verified. TypeSafe's [open-source alternative adapter](https://github.com/typesafe-ai/system-one-adapter-python) calls other LLM APIs; it is not local Jev. No relevant provider key was present in this process's environment. No paid account was created, credits purchased, or real inference performed. This does not establish whether another application has credentials.

## Concrete workflow design

These are project recommendations, informed by the provider's [composite scoring](https://docs.typesafe.ai/patterns/composite-scoring) and [citation checking](https://docs.typesafe.ai/cookbooks/citation_check) patterns:

| Stage | Supplied evidence | Jev question | Deterministic follow-through |
|---|---|---|---|
| Discovery review | Original URL, uploader, caption, event/session metadata, transcript excerpt | Exact session, different session, insufficient evidence | Reject known date/session mismatches; retain uncertain assets in review |
| Asset labeling | Timecoded transcript and verified frame observations | Track action, interview, analysis, results, atmosphere, insufficient evidence | Store label with backend, model, raw answer and source IDs |
| Asset-to-event link | One candidate segment and one asset excerpt | Does this passage support this segment? | Resolve candidate IDs only; check time ranges in code |
| Editorial scoring | Verified event facts, computed positions/points, idea synopsis | Narrative impact and explanation value, separately | Combine dimensions with documented weights |
| Script checking | One factual sentence plus its cited evidence | Supported, contradicted, insufficient evidence | Queue disputed sentences for rewrite or additional research |
| Routing | Typed decision, provider probabilities and quality checks | No additional question required | Code chooses accept, review or abstain |

Use one small, self-contained record per candidate. Batch independent questions about that record. A later decision requiring another answer belongs in a later stage. Keep event identity, session status, observed video contents, reported facts and editorial inferences separate. Never use uploaded captions as instructions. Jev cannot establish a reuse license merely because an asset is publicly visible.

Rank ideas only after evidence and asset feasibility checks. Proposed initial formula: 45% narrative impact, 35% explanation value, 20% asset readiness; normalize each dimension to 0–1. Asset readiness comes from verified local files, rights status and usable time ranges in code. Missing footage reduces readiness; it does not justify inventing coverage. Publish the component scores and tie-break by evidence completeness, then stable idea ID. These weights are editorial choices, not Jev properties.

These weights have not been confirmed as the user's preferences. Follow the
[human quality and subscription-first policy](model-selection.md): quality comes
from explicit user feedback, and Jev is an optional advisory comparison. Current
analysis remains deterministic. The explicit [OpenRouter workflow](openrouter-workflow.md)
now prepares each matched timeline claim separately, consumes accepted native Jev
answers in dependent story jobs, and exposes an evidence-bound review queue.
It does not change production rankings or render plans automatically. The direct
TypeSafe adapter below remains a compatibility path; new workspace commands use
`typesafe/jev-1.13` through OpenRouter. [Verified native contract](openrouter-jev-integration-research.md).

## Evaluation and abstention

Confidence summarizes a distribution's concentration; it is not a guarantee that a factual claim is correct. Preserve it separately from the winning probability. [Confidence documentation](https://docs.typesafe.ai/confidence).

An independent [September 2026 benchmark](https://arxiv.org/abs/2609.37647) reports that binary thresholds need task-specific tuning. Treat that as a research result, not validation of this F1 application.

Before automatic acceptance, label a representative set of at least 100 assets/claims, including old-year footage, qualifying mistaken for sprint, reposts, misleading captions, missing transcripts and contradictory evidence. Keep a held-out set grouped by source/clip so reposts cannot leak across splits. Compare actual Jev against deterministic rules and human labels using precision/recall by category, session-match false positives, Brier score, expected calibration error, acceptance coverage, error rate among accepted results, p50/p95 latency and actual token cost. For ranking, use reviewer pairwise preferences or nDCG over a fixed reference ranking.

Select thresholds on development data and freeze them with model/rubric versions; evaluate once on held-out data. Until that evaluation exists, outputs remain advisory. Explicit `insufficient_evidence`, contradictory source records, schema failure, or missing credentials must route to review/abstention. Do not turn an arbitrary 0.8 threshold into a claim of calibration. Check option reordering and label/rubric consistency, given documented model weaknesses.

## Delivered and tested

- `f1_pipeline/jev_adapter.py`: standard-library client, pinned official host/model, no redirect credential forwarding, finite JSON and response distribution validation, bounded retries only for explicit 429/529, hashed provenance receipts, no fallback.
- `f1_pipeline/resources/jev_questions.json`: application rubrics for classification, session matching, claim support and two scoring dimensions.
- `tests/test_jev_adapter.py`: nine offline tests including credential absence, invalid distributions, missing answers, model mismatch, redirect refusal and bounded overload retry. They passed locally. Synthetic transport responses test the client, not Jev quality.
- Local-only `research/jev/sources.json`: download URLs, retrieval times and SHA-256 for ten primary-source snapshots. A citation to a paper is research evidence; it is not an executed local evaluation.
- Local-only `research/jev/verification.json`: local validation receipt; explicitly no live inference.

Any deterministic offline output in the wider workflow must identify itself as `deterministic_rules`, or `Jev-inspired deterministic rules`, with `actual_model_inference: false`. It must not attach made-up model probabilities or claim to have used Jev.

Run from the project directory:

```sh
python3 -m f1_pipeline.jev_adapter --status
python3 -m f1_pipeline.jev_adapter --request examples/synthetic/jev-request.json --validate-only
python3 -m unittest discover -s tests -p 'test_jev_adapter.py' -v
```

After an existing authorized key is configured securely, send a small public-evidence request with `--request` and a new receipt path via `--output`. The adapter will perform a billable provider call; the key is never accepted on the command line or written to receipts. Keep the input request beside the hashed result for reproducibility.
