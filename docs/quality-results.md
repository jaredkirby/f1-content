# Offline categorical evaluation results

The `quality-results-preview`, `quality-results-save` and `quality-results-report`
commands join explicit human label declarations to a current
[frozen quality protocol](quality-evaluation.md) and native Jev model work. They
never invoke a provider, resolve credentials or infer film approval. Real human
labels and real held-out execution remain separate work.

## Prepare evidence before inference

Freeze the protocol first. For each evaluated case, the native `jev-infer` work
must bind the frozen protocol receipt, the exact rubric file and every case
evidence binding among its `--evidence` files. Its `--rubric-version` must equal
the protocol rubric version. Use exact evidence paths/hashes from that frozen
case. The native request's `state` must be an object containing an
`evaluation_case` object with exactly `protocol_receipt`, `case_id`, `rubric` and
`evidence`. Its values must exactly equal the selected frozen receipt binding,
case ID, full protocol rubric binding/version and case evidence list. This
association travels inside the hash-bound request actually sent to the provider;
adding evidence only to model-work metadata cannot reassign a prediction to a
case. Preserve the claim/evidence packet in the other `state` fields, which remain
untrusted source material. These workflow operations do not authorize a new
provider call.

The required transport metadata has this shape:

```json
{
  "model": "typesafe/jev-1.13",
  "state": {
    "evaluation_case": {
      "protocol_receipt": {
        "path": "runs/quality-protocols/sample-v1.json",
        "sha256": "<current frozen receipt SHA-256>"
      },
      "case_id": "case-development",
      "rubric": {
        "version": "rubric-v1",
        "path": "research/rubric.txt",
        "sha256": "<protocol rubric SHA-256>"
      },
      "evidence": [
        {"path": "research/case-development.json", "sha256": "<case evidence SHA-256>"}
      ]
    },
    "claim_evidence_packet": "Replace with the actual bounded claim/evidence packet."
  },
  "questions": {
    "claim_support": {
      "type": "choice",
      "instructions": "Use the actual exact reviewed rubric instructions.",
      "criteria": {"supported": "Evidence supports the claim.", "unsupported": "Evidence does not support the claim."}
    }
  }
}
```

Older requests without this metadata are refused. Prepare a new bound request and
work receipt; do not retrofit an association onto an earlier provider result.

This slice accepts only the canonical imported receipt produced for a single
native OpenRouter Jev `attempt-1`, with an accepted, completed, nonfailed result.
The request, provider receipt and output must belong to that same work's `.assets`
directory. The observed model and settings must match the native provider receipt;
its request hash and output bytes are revalidated. A native Jev **choice** question
supplies the available labels and the prediction. Score and Noul questions,
subscription text work, unrelated earlier smoke tests and arbitrary copied
receipts are refused. These limits avoid treating old generic model output as a
frozen-case result. A provenance binding is a recorded operator association;
local hashes do not authenticate the provider or prove the model read a file.

## Declare labels and preview

Create a workspace JSON request with exactly these fields. Replace all example
identifiers, paths, hashes and fictional labels with the actual reviewed evidence.
The example is a shape illustration, not an executable real evaluation:

```json
{
  "schema_version": "f1.quality_results.v1",
  "evaluation_id": "case-review-v1",
  "protocol_receipt": {
    "path": "runs/quality-protocols/sample-v1.json",
    "sha256": "<current frozen receipt SHA-256>"
  },
  "assessments": [
    {
      "case_id": "case-development",
      "model_work": {
        "path": "runs/model-evaluations/claim-pilot/case-development.json",
        "sha256": "<current imported model-work SHA-256>"
      },
      "attempt_id": "attempt-1",
      "question_id": "claim_support",
      "expected_label": "supported",
      "human_source": {
        "kind": "human",
        "reviewer": "Explicit reviewer reference",
        "reference": "Explicit review/source reference for this label"
      }
    }
  ]
}
```

The request allows 1–1000 assessments. Each assessment names a protocol case and
an exact question in its bound native request. Expected labels must be an option
of that question. Every label requires a nonempty reviewer and source reference.
These are operator-supplied declarations of human evidence, not authenticated
reviewer identities. The workflow does not check agreement or independence of
reviewers. A caller cannot supply or override `prediction`.

```sh
scripts/f1 --workspace /absolute/event quality-results-preview --request requests/evaluation-v1.json
scripts/f1 --workspace /absolute/event quality-results-save --request requests/evaluation-v1.json
scripts/f1 --workspace /absolute/event quality-results-report --request runs/quality-results/case-review-v1.json
```

Preview reads and validates without writing. Save rechecks all bindings before
publishing complete bytes exclusively to
`runs/quality-results/<evaluation_id>.json`; an existing identifier is refused.
Report checks the original request, frozen protocol, case/rubric evidence, model
work, provider provenance and output again. Changed or missing evidence fails
validation rather than rebinding an old result.

## Read the report

For each exact model/settings, prompt version, rubric binding and full question
schema, the report separates development from held-out cases. Each group gives
raw expected/predicted confusion counts, assessed case count, correct/incorrect
counts, observed accuracy, missing case IDs and partial/complete case coverage.
The full question includes its instructions and option descriptions; similarly
named incompatible questions cannot share a group. Serving generation references
identify individual attempts and do not split a model/settings group.

A case can appear at most once in one model/settings/question domain, even through
another work receipt. One exact model-work/attempt/question prediction can appear
at most once across all assessments; reusing an answer cannot inflate case counts. Every observed domain reports both protocol splits,
including zero-assessment groups with `accuracy: null`. Unassessed protocol cases
are also listed globally. Completeness is case coverage within that domain and
split; it is not statistical adequacy, source independence or model parity.

Accuracy is the fraction correct **among supplied usable completed outputs**. The
workflow refuses failed attempts; it does not measure abstention rates, provider
failure rates, end-to-end reliability or recall over missing cases. Source-group
membership is preserved from the operator-declared protocol, not independently
verified. No confidence calibration, parity threshold, quality promotion,
editorial acceptance or cost-per-accepted-film claim is produced. Use existing
[model feedback workflows](model-workflows.md) for exact-film human feedback and
observed cost accounting.

## Corrections and retention

Keep the original request and its complete evidence files in place. A corrected
label or changed evidence requires a **new evaluation ID and request path**.
Older receipts are immutable snapshots; editing their bound files makes their
current report stale. To preserve a report across new versions, preserve every
original bound path, including protocol and model-work files. Hashes detect drift
and accidental edits, not malicious rewriting by an operator with file access.
