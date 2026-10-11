# OpenRouter hosted inference contract

Checked 2026-10-10 against official OpenRouter documentation, live public model and
endpoint metadata, and the upstream model card. This supersedes the active
DeepInfra contract. Historical receipts retain their original provider and rates.
Public GETs were performed; no inference, key access, account change or media upload.

## Selected route and capability

The user selected `deepseek/deepseek-v4.1-flash`. Its public catalog identifies
canonical slug `deepseek/deepseek-v4.1-flash-20260910`, a 1,048,576-token context,
image/text input and text output, optional reasoning with low/high/max effort,
and default high effort. The upstream model card lists MIT for code and weights.
The project adapter supports bounded text only. Advertised vision/tool capability
is not an implemented or authorized media/tool workflow.
[Model guide](https://openrouter.ai/deepseek/deepseek-v4.1-flash/llms.txt),
[public catalog](https://openrouter.ai/api/v1/models),
[upstream card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash).

The initial serving route uses `provider.only: ["deepseek"]`,
`allow_fallbacks: false` and `require_parameters: true`. Other OpenRouter providers
list different quantizations and prices. The selected endpoint's precision is
unknown; pinning it does not prove a runtime/weight fingerprint or F1 quality.
An alternative provider is a separate quality comparison, not an automatic fallback.
[Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

## Request and response

POST `https://openrouter.ai/api/v1/chat/completions` with JSON and
`Authorization: Bearer $OPENROUTER_API_KEY`. The project requires exact model,
1–64 nonempty system/user/assistant text messages and `max_tokens` from 1–16,384.
Optional controls are temperature, top_p, JSON-object output and one reasoning
configuration. Default reasoning is high with reasoning text excluded. Effort
accepts low/high/max; reasoning may be explicitly disabled with enabled:false.
Conflicting forms and unsupported options fail before a request.
[Chat contract](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion),
[reasoning behavior](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

The sent body forces nonstreaming, requests usage, and explicitly disables the
context-compression plugin. No model list, server tools, media or arbitrary
provider/endpoint controls are accepted. DeepInfra's n/fail_fast fields are removed.
Exactly one completed assistant choice with stop finish reason is required.
Known catalog alias/canonical identity is retained exactly as observed; an
unexpected model, refusal, tool call, truncation or invalid JSON-object output
fails the result contract. No internal retry or redirect is allowed.
[Compression contract](https://openrouter.ai/docs/guides/features/message-transforms).

Opt-in `X-OpenRouter-Metadata: enabled` exposes routing observations when available.
Keep observed serving provider and router attempt count unknown when absent.
Observed provider/model switching, multiple attempts or transformations fail the
output contract. Preserve valid metering despite that failure. Generation IDs are
retained when valid; serving revision and quantization remain unknown.
[Router metadata](https://openrouter.ai/docs/guides/features/router-metadata).

## Price and cost meaning

The selected DeepSeek endpoint advertises discounted windows and peak USD rates:

| Input / output / cached input per 1M tokens | Context | Serving precision |
|---|---:|---|
| $0.30 / $1.20 / $0.006 | 1,048,576 | Unknown |

Use peak rates for the conservative preflight ceiling: full context at uncached
input price plus capped output. Send provider max_price caps of prompt:0.30 and
completion:1.20 (units: USD per million). At 8,192 output tokens, the ceiling is
$0.3244032; this is neither a token prediction nor an authorized spend. Byte limits
are not token measurements. Refresh metadata before a paid run. These controls
cannot prevent a provider billing defect.
[Endpoint snapshot source](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-20260910/endpoints),
[price filter](https://openrouter.ai/docs/guides/routing/provider-selection#max-price).

Valid usage.cost is an OpenRouter-reported credit charge, distinct from a local
peak-rate estimate. Record it as actual request cost only with explicitly false
is_byok (usage or consistent router metadata). BYOK or missing scope leaves the
full actual inference cost unknown while retaining the reported OpenRouter charge.
Credit-purchase fees and other account expenses are outside this request charge.
Missing cost remains null, not zero. Valid charges survive malformed token usage;
valid token usage survives invalid charges. Cache and reasoning counts are subsets
of aggregate input/output usage and are never added twice.
[USD-credit billing](https://openrouter.ai/support),
[usage response schema](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion).

## Execution and evidence boundaries

`preflight(payload, budget_usd=None)` is offline and reads no key.
`evaluate(payload, execute=False, budget_usd=None, api_key=None, timeout=20, opener=None)`
requires explicit execute:true, a positive finite budget covering the ceiling and
an existing OpenRouter key for one call. Resource caps remain 131,072 request bytes,
2,000,000 response bytes and 0.001–60 seconds. Missing keys produce an unattempted
failure; transport/HTTP/schema failures retain safe evidence without echoing raw
error bodies or credentials. Rate limiting is returned for an explicit later
operator decision; no automatic backoff can duplicate an ambiguous charge.

Receipts retain `f1.hosted-inference.v1`, OpenRouter provider, endpoint, exact
request/response hashes, effective settings, catalog identity, observed model,
route/generation observations, actual usage, peak estimates and explicit charge
scope. Oversized responses expose only labeled prefix hashes. accepted_model_result
means the transport/output contract passed, not grounding or human approval.

The CLI selects one event workspace, checks storage before a call, saves immutable
input/evidence/intent/result receipts and imports provider-neutral model work.
Recorded request charges use cost_source:provider_receipt. Interrupted work retains
raw measurements without inventing an attempt or complete efficiency total. The
Codex subscription remains first; OpenRouter is separately billed. Never send raw
private feedback by default or treat account/provider settings as user approval.

Synthetic tests exercise public HTTP/CLI boundaries, including real standard-library
redirect handling with a fake HTTPS transport. They do not establish live model
quality, account access, provider reliability or real phone acceptance. A completed
candidate edit still needs the mobile destination and explicit user review.
