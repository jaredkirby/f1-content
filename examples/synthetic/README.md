# Offline synthetic example

The identifiers and metadata here are deliberately fictional. They do not
represent a real event and must not be used for collection or publication.

```sh
./scripts/f1 --workspace examples/synthetic doctor
.venv/bin/python -m f1_pipeline.jev_adapter --request examples/synthetic/jev-request.json --validate-only
./scripts/f1 --workspace examples/synthetic quality-preview --request quality-protocol.json
./scripts/f1 --workspace examples/synthetic model-run --request story-plan.json
```

These commands validate configuration, typed requests, a source-grouped quality
protocol and a ledger-bound story plan without
network access, provider credentials, media downloads or writes to this example.
They do not demonstrate real Jev inference or a completed production session.
See [quality evaluation](../../docs/quality-evaluation.md) and
[story contracts](../../docs/story-contract.md) for the explicit freeze/execution
boundaries. Keep all fictional evidence separate from real feedback or approval.
