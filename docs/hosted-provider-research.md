# Hosted inference provider contract

Checked 2026-10-10 against primary DeepInfra documentation. These are API facts
and implementation limits, not an F1 output-quality benchmark. No inference,
credential access, account change or media upload was performed.

## Explicit execution and billing

DeepInfra documents a bearer-token POST to
`https://api.deepinfra.com/v1/openai/chat/completions`. Request fields include
`model`, `messages`, `max_tokens`, `temperature`, `top_p` and `response_format`.
Leaving `service_tier` unset selects standard scheduling and pricing. Its
`fail_fast` option avoids capacity queueing; it does not authorize fallback.
[Chat completion contract](https://docs.deepinfra.com/chat/overview).

This is a separately billed provider API. OpenAI-compatible request syntax does
not use the user's signed-in Codex ChatGPT subscription. Preserve subscription
work in supported Codex surfaces and require a concrete authorized provider,
request and budget before sending a request.

## Exact initial models and rates

The following standard USD rates are per million tokens. Cached rates are
documented for reference; preflight spending estimates assume uncached input.
Model listings are provider claims about serving precision/context, not observed
runtime fingerprints or evidence of human-accepted quality.

| Exact model ID | Input / output / cached input | Listed context | Listed precision | Primary source |
|---|---:|---:|---|---|
| `deepseek-ai/DeepSeek-V4-Pro-0813` | $1.30 / $2.60 / $0.10 | 1,048,576 | FP8 | [Provider model/API](https://deepinfra.com/deepseek-ai/DeepSeek-V4-Pro-0813/api) |
| `Qwen/Qwen3.5-397B-A17B` | $0.45 / $3.00 / $0.22 | 262,144 | FP8 | [Provider model/API](https://deepinfra.com/Qwen/Qwen3.5-397B-A17B/api) |
| `deepseek-ai/DeepSeek-V3.2` | $0.26 / $0.38 / $0.13 | 163,840 | FP4 | [Provider model/API](https://deepinfra.com/deepseek-ai/DeepSeek-V3.2/api) |
| `openai/gpt-oss-120b` | $0.037 / $0.17 / not listed | 131,072 | BF16 | [Provider model/API](https://deepinfra.com/openai/gpt-oss-120b/api) |

DeepSeek V4 Pro is the initial strong text candidate; Qwen is the strong
text/vision candidate. The other two are value comparators. Each model's API page
shows the exact requested/returned model field and a usage example with
`prompt_tokens`, `completion_tokens`, `total_tokens` and `estimated_cost`.
That last field is an estimate; it is not a settled account bill. A missing
hosted weight/build fingerprint remains unknown.

## Reasoning, structure and modality boundaries

DeepInfra documents `reasoning_effort` values `none`, `low`, `medium` and `high`,
explicitly lists DeepSeek V4 Pro as a supported reasoning model, and says
reasoning tokens are billed as output. Avoid double-counting a reasoning detail
on top of aggregate output usage. A received reasoning trace is untrusted model
content, not decision evidence or user feedback.
[Reasoning contract](https://docs.deepinfra.com/chat/reasoning).

The API documents `json_object` and `json_schema` output modes across supported
models. Provider JSON generation does not replace local validation, factual
checks or human review. Start with text or JSON-object output; unsupported
settings must fail rather than silently downgrade.
[Structured output contract](https://docs.deepinfra.com/chat/structured-outputs).

Qwen's listing labels it multimodal. The vision API accepts a public image URL or
base64 image through content parts. This establishes provider capability, not
permission to upload local/private media or dereference arbitrary URLs. The first
adapter remains text-only; a future vision adapter needs explicit bounded media,
input/hash, token-accounting and authorization contracts. Speech is a separate
later adapter and listening evaluation.
[Vision contract](https://docs.deepinfra.com/chat/vision).

## Spending and evidence rules

`max_tokens` bounds generated tokens; the docs describe model-dependent context
limits and no request-level dollar ceiling or input-token cap. Request byte limits
are resource caps, never actual token measurements. Without a verified tokenizer,
preflight uses the full listed model context at uncached input price plus the
requested maximum output at output price. This intentionally conservative ceiling
is conditional on the recorded rates and provider honoring token limits; refresh
the rates before approving a paid execution. Actual usage is checked afterward,
and a ceiling breach is a failed receipt. Local validation cannot prevent an
unexpected provider billing error.
[Token and scheduling limits](https://docs.deepinfra.com/chat/overview).

DeepInfra reports cached input at
`usage.prompt_tokens_details.cached_tokens`, a subset of prompt usage. Preserve
the reported value when present; absence means unknown, not an observed cache
miss. Cache-related cost savings require actual reported accounting.
[Cache usage contract](https://docs.deepinfra.com/chat/prompt-caching).

Use one bounded nonstreaming request, refuse redirects, and do not retry an
ambiguous failure or switch model/provider. Record exact request/response byte
hashes, elapsed time, actual usage when valid, and unsuccessful attempts without
fabricating a model result. Do not log credentials or echo error bodies. A
transport/schema success is not factual validity or human acceptance.

DeepInfra states that ordinary inference inputs/outputs remain in memory and are
not used for training for these model families; its bulk APIs have different
retention. Those policies do not grant permission to transmit private feedback.
Keep feedback local and send only explicitly selected evidence needed by the task.
[Provider privacy policy](https://docs.deepinfra.com/account/data-privacy).

## Implemented adapter interface

`f1_pipeline.hosted_inference.preflight(payload, budget_usd=None)` validates
locally. `evaluate(payload, execute=False, budget_usd=None, api_key=None,
timeout=20, opener=None)` uses the same default and never reads a credential or
contacts a provider during preflight. Execution requires `execute=True`, a
positive finite budget covering the context ceiling, and an existing DeepInfra
credential. Missing/invalid credentials produce an unattempted failure. Invalid
local input raises `HostedInferenceError`; unsuccessful execution returns a
failed receipt. The CLI owns workspace selection and immutable persistence.

Required request fields are exact `model`, nonempty text `messages` (roles
system/user/assistant), and integer `max_tokens` from 1 to 16,384. Optional
sampling fields are `temperature` and `top_p`; structured output accepts only
`{"type":"json_object"}`. Explicit `reasoning_effort` is currently supported
only for DeepSeek V4 Pro, whose provider support was directly verified. Other
fields, multimodal content, arbitrary endpoints, streaming and service tiers are
refused. Local caps are 64 messages, 131,072 request bytes, 2,000,000 response
bytes and a timeout from 0.001 to 60 seconds. Byte counts are never token counts.

Receipts use `f1.hosted-inference.v1` with preflight/succeeded/failed status,
request and full-response hashes, attempts, observed model, output text bytes/hash,
validated aggregate usage and optional cached/reasoning token subsets. Unknown
details remain null. Empty, whitespace-padded or malformed provider model identity
remains unknown; its raw response hash and valid metering are still retained. An
oversized body records an explicitly named prefix hash,
never a hash mislabeled as the complete response. Failed identity, truncation,
output shape or token-limit checks retain valid usage and response hashes while
omitting the model result. HTTP failures preserve bounded body hashes, without
echoing the bodies. Ambiguous transport failures retain unknown execution/billing.

Cost metadata retains the exact dated rate snapshot, preflight ceiling, a
usage-based estimate, a separately reported provider estimate and
`actual_billing_usd: null`. Cache/reasoning subsets are not double-counted; absent
cache details mean an uncached assumption for the local estimate. No field
claims a settled bill. `accepted_model_result` means the transport/output contract
passed; it never means grounded factual correctness or human acceptance.

Fifteen offline transport tests exercise those public interfaces using synthetic
HTTP responses, including the standard library's redirect processing with a fake
HTTPS transport. No tests mock this project's internal adapter objects, contact
an inference endpoint, load real credentials or upload evidence/feedback.
