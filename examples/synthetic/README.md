# Offline synthetic example

The identifiers and metadata here are deliberately fictional. They do not
represent a real event and must not be used for collection or publication.

```sh
./scripts/f1 --workspace examples/synthetic doctor
.venv/bin/python -m f1_pipeline.jev_adapter --request examples/synthetic/jev-request.json --validate-only
```

These commands validate configuration and the typed-request contract without
network access, provider credentials, media downloads or writes to this example.
They do not demonstrate real Jev inference or a completed production session.
