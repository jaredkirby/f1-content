# OpenRouter and native Jev integration

Verified 2026-10-10 using official documentation, the public OpenAPI schema and
unauthenticated endpoint metadata. No credential was read and no inference ran.

## Verified contracts

Real Jev is available through OpenRouter using an OpenRouter key and billing
account; a separate TypeSafe account is unnecessary. Select `typesafe/jev-1.13`.
`~typesafe/jev-latest` changes its target over time, while `typesafe/jev-router`
selects a generative model and reasoning effort. Neither is the appropriate pin
for reproducible typed F1 judgments.
[Jev hub](https://openrouter.ai/docs/guides/community/jev),
[latest alias](https://openrouter.ai/~typesafe/jev-latest),
[chat router](https://openrouter.ai/typesafe/jev-router).

The live endpoint advertises provider `TypeSafe`, routing tag `typesafe`, model
identity `typesafe/jev-1.13-20260917`, $0.042 per million input tokens and free
output. Limits are 64,000 total context tokens, 32,000 prompt tokens and 57,600
completion tokens. Serving quantization is unknown. The distinction between total
context and prompt limit resolves the differing 64K and 32K descriptions in the
model page and introductory guide.
[Endpoint metadata](https://openrouter.ai/api/v1/models/typesafe/jev-1.13/endpoints).

Both `POST https://openrouter.ai/api/v1/systemone` and
`POST https://openrouter.ai/api/alpha/decisions` use `DecisionsRequest` and
`DecisionsResponse` in the public OpenAPI specification. Required request fields
are `model`, `state`, `questions`; optional `provider` uses `ProviderPreferences`.
The System One route therefore supports routing controls despite their omission
from the short SDK migration example. It is the smallest migration from this
repository's existing TypeSafe-shaped client.
[OpenAPI specification](https://openrouter.ai/openapi.json),
[System One reference](https://openrouter.ai/docs/api/api-reference/systemone/submit-a-system-one-request).

System One preserves typed answers and adds OpenRouter generation identity,
provider and cost observations. The documented concrete response model is
`typesafe/jev-1.13-20260917`; bare `jev-1.13` maps to the namespaced model.
Avoid assuming the legacy direct-provider identity `jev-1.13.0` is an OpenRouter
response identity.
[SDK compatibility guide](https://openrouter.ai/docs/guides/community/typesafe-sdk).

The response schema requires `model`, `answers`, `usage`, and integer
`usage.input_tokens` and `usage.output_tokens`. `usage.cost`, response `provider`
and `id` are optional. There is no required `total_tokens` or `is_byok`. Choice
requires `type` and `choice`; Score requires `type` and `score`. Their distributions,
confidence and Score legend are optional in this schema, although native TypeSafe
documentation describes them as returned. Missing optional observations must not
be invented.
[OpenAPI response schemas](https://openrouter.ai/openapi.json),
[classification cookbook](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/jev-classification).

Choice probabilities cover declared labels; Score is the probability-weighted
level index; Noul is the probability of yes. Confidence differs from the winning
probability: Choice normalizes the highest probability above an even split, and
Score measures concentration around the most likely ordered level. These quantities
do not establish accuracy on F1 evidence or human editorial quality.
[TypeSafe API](https://docs.typesafe.ai/api),
[confidence definitions](https://docs.typesafe.ai/confidence).

## Recommended implementation

Keep direct TypeSafe receipts and the legacy adapter compatible. Add an explicit
OpenRouter Jev route with shared question validation, a default offline preflight,
one bounded execution and no retry. Use `provider.only: ["typesafe"]`,
`allow_fallbacks: false`, and `max_price: {prompt: 0.042, completion: 0}`. Price
caps use USD per million tokens. These settings request the chosen route; observed
provider and model checks must still detect an unexpected result.
[Routing controls](https://openrouter.ai/docs/guides/routing/provider-selection).

Use a conservative per-call ceiling of $0.002688: 64,000 × $0.042 / 1,000,000.
This is a dated upper allowance, not predicted token consumption or an observed
charge. Include all questions in request accounting and enforce local byte and
question limits independently of token limits. Refresh public metadata before an
authorized run. Budget the whole planned batch before its first request.

Store raw response hashes and independently valid usage/cost before judging the
answer schema. Preserve `usage.cost` as the OpenRouter-reported USD charge; keep
broader billing scope unknown when unobserved. Missing cost is unknown, never zero.
Missing required token fields, model mismatch, malformed distributions, changed
Score legends or missing confidence should prevent a result from satisfying the
project's stricter advisory contract. This is a local acceptance policy, not a
claim that all such responses violate OpenRouter's optional-field schema.

The reference documents HTTP 400/401/402/403/404/413/429/500/502/503/524/529 errors.
It does not promise metering on failed requests. A timeout or invalid response can
leave execution and charging uncertain. Preserve that uncertainty; do not infer
free inference or retry automatically.
[System One error contract](https://openrouter.ai/docs/api/api-reference/systemone/submit-a-system-one-request).

Bind each request to one event, evidence hashes, a rubric version and a unique job
ID. Apply Jev to session matching, asset labels, individual claim support and
separate editorial scoring dimensions. Keep original answers available for later
threshold evaluation. Until a held-out F1 evaluation and explicit human decision
exist, scores are advisory and cannot change release gates or authorize tools.
This follows the provider's classification and citation-checking patterns, adapted
to the repository's evidence and human-review contracts.
[Classification pattern](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/jev-classification),
[citation checking](https://docs.typesafe.ai/cookbooks/citation_check).

## Existing generative route

The pinned `deepseek` endpoint for `deepseek/deepseek-v4.1-flash` still advertises
1,048,576 context tokens. Peak input/output/cached-input rates remain
$0.30/$1.20/$0.006 per million; the observed weekend window is half those rates.
Its supported parameters include `response_format` but omit `structured_outputs`.
Keep JSON-object mode plus local semantic validation; do not claim strict JSON
Schema support merely because another provider for this model offers it.
[DeepSeek endpoint metadata](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints),
[structured-output requirements](https://openrouter.ai/docs/guides/features/structured-outputs).

The next live run needs an existing securely supplied OpenRouter key, a frozen
evidence-bound job plan and explicit finite budget covering the selected jobs.
Offline tests should exercise both transport boundaries and never need that key.
Native Jev and DeepSeek receipts must identify the actual route; preparing jobs
or passing synthetic tests is not evidence that inference occurred.
