"""Bounded OpenRouter text inference; validation is offline unless explicitly executed.

Provider contract and dated rate sources: docs/hosted-provider-research.md.
OpenAI-compatible syntax does not use Codex ChatGPT subscription billing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from .credentials import resolve_api_key
import time
import urllib.error
import urllib.request

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL_ID = "deepseek/deepseek-v4.1-flash"
CANONICAL_SLUG = "deepseek/deepseek-v4.1-flash-20260910"
RESPONSE_MODELS = {MODEL_ID, CANONICAL_SLUG}
RATE_DATE = "2026-10-10"
MAX_REQUEST_BYTES = 131072
MAX_OUTPUT_TOKENS = 65536
MAX_RESPONSE_BYTES = 2000000
MODELS = {
    MODEL_ID: {
        # Peak rates cover the advertised DeepSeek time-of-day discounts.
        "context_tokens": 1048576, "input_rate": "0.30", "output_rate": "1.20",
        "cached_input_rate": "0.006",
    },
}
ROUTING = {"only": ["deepseek"], "allow_fallbacks": False, "require_parameters": True,
           "max_price": {"prompt": 0.30, "completion": 1.20}}
REASONING_EFFORTS = {"low", "high", "max"}


class HostedInferenceError(ValueError):
    """A local request cannot be evaluated safely; messages contain no input data."""


def _encode(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise HostedInferenceError("Request must contain finite UTF-8 JSON data") from None


def _number(value, low, high):
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def _request_body(payload):
    required = {"model", "messages", "max_tokens"}
    optional = {"temperature", "top_p", "response_format", "reasoning_effort", "reasoning"}
    if (not isinstance(payload, dict) or not required <= set(payload)
            or set(payload) - required - optional):
        raise HostedInferenceError("Request requires model, messages and max_tokens; unsupported fields are refused")
    if not isinstance(payload["model"], str) or payload["model"] not in MODELS:
        raise HostedInferenceError("Unsupported model; use an exact approved hosted model ID")
    if type(payload["max_tokens"]) is not int or not 1 <= payload["max_tokens"] <= MAX_OUTPUT_TOKENS:
        raise HostedInferenceError("max_tokens must be an integer from 1 to 65536")
    messages = payload["messages"]
    if not isinstance(messages, list) or not 1 <= len(messages) <= 64:
        raise HostedInferenceError("messages must contain 1 to 64 text messages")
    for item in messages:
        if (not isinstance(item, dict) or set(item) != {"role", "content"}
                or not isinstance(item["role"], str) or item["role"] not in {"system", "user", "assistant"}
                or not isinstance(item["content"], str) or not item["content"].strip()):
            raise HostedInferenceError("Only nonempty system, user or assistant text messages are supported")
    for name, low, high in (("temperature", 0, 2), ("top_p", 0, 1)):
        if name in payload and not _number(payload[name], low, high):
            raise HostedInferenceError("Invalid sampling value")
    if "response_format" in payload and payload["response_format"] != {"type": "json_object"}:
        raise HostedInferenceError("Only json_object structured output is supported")
    if (payload.get("response_format") == {"type": "json_object"}
            and not any("json" in item["content"].lower() for item in messages)):
        raise HostedInferenceError("JSON-object output requires a JSON instruction in message content")
    if "reasoning_effort" in payload:
        if (not isinstance(payload["reasoning_effort"], str)
                or payload["reasoning_effort"] not in REASONING_EFFORTS):
            raise HostedInferenceError("Reasoning setting is not verified for this model")
        if "reasoning" in payload:
            raise HostedInferenceError("Use one reasoning configuration, not both forms")
        reasoning = {"effort": payload["reasoning_effort"], "exclude": True}
    elif "reasoning" in payload:
        reasoning = payload["reasoning"]
        if (not isinstance(reasoning, dict) or not reasoning
                or set(reasoning) - {"effort", "enabled", "exclude"}
                or ("effort" in reasoning and (not isinstance(reasoning["effort"], str)
                                               or reasoning["effort"] not in REASONING_EFFORTS))
                or any(type(reasoning[k]) is not bool for k in ("enabled", "exclude") if k in reasoning)
                or ("effort" in reasoning and "enabled" in reasoning)):
            raise HostedInferenceError("Invalid or unverified reasoning configuration")
        reasoning = {"effort": "high", "exclude": True, **reasoning} if set(reasoning) <= {"exclude"} else {"exclude": True, **reasoning}
    else:
        reasoning = {"effort": "high", "exclude": True}
    effective = {k: v for k, v in payload.items() if k not in {"reasoning", "reasoning_effort"}}
    body = _encode({**effective, "reasoning": reasoning, "stream": False, "provider": ROUTING,
                    "usage": {"include": True},
                    "plugins": [{"id": "context-compression", "enabled": False}]})
    if len(body) > MAX_REQUEST_BYTES:
        raise HostedInferenceError("Request exceeds the local byte limit")
    return body


def preflight(payload, *, budget_usd=None):
    """Validate locally and report a full-context ceiling under the recorded rates."""
    body = _request_body(payload)
    model = MODELS[payload["model"]]
    ceiling = (Decimal(model["context_tokens"]) * Decimal(model["input_rate"])
               + Decimal(payload["max_tokens"]) * Decimal(model["output_rate"])) / 1000000
    if budget_usd is not None and (not _number(budget_usd, 0, 1000000) or budget_usd <= 0):
        raise HostedInferenceError("budget_usd must be positive finite USD, at most 1000000")
    return {
        "schema_version": "f1.hosted-inference.v1", "provider": "openrouter",
        "endpoint": ENDPOINT, "requested_model": payload["model"],
        "observed_model": None, "status": "preflight",
        "inference_attempted": False, "actual_model_inference": False,
        "accepted_model_result": False, "attempts": 0,
        "request_sha256": hashlib.sha256(body).hexdigest(), "request_bytes": len(body),
        "input_messages_sha256": hashlib.sha256(_encode(payload["messages"])).hexdigest(),
        "effective_settings": {k: v for k, v in json.loads(body).items() if k not in {"model", "messages"}},
        "catalog_canonical_slug": CANONICAL_SLUG,
        "observed_serving_provider": None, "observed_router_attempts": None,
        "observed_generation_id": None,
        "input_text_bytes": sum(len(item["content"].encode("utf-8"))
                                for item in payload["messages"]),
        "response_sha256": None, "response_bytes": None, "usage": None,
        "cost": {"budget_usd": budget_usd, "preflight_ceiling_usd": float(ceiling),
                 "usage_rate_estimate_usd": None, "provider_estimated_cost_usd": None,
                 "provider_reported_cost_usd": None, "actual_billing_usd": None,
                 "is_byok": None, "actual_cost_source": "unknown", "rate_date": RATE_DATE,
                 "rate_source": "https://openrouter.ai/api/v1/models/" + CANONICAL_SLUG + "/endpoints",
                 "rate_basis": "dated DeepSeek peak rates; discounts not assumed",
                 "rate_snapshot": {"input_usd_per_million": model["input_rate"],
                                   "output_usd_per_million": model["output_rate"],
                                   "cached_input_usd_per_million": model["cached_input_rate"],
                                   "context_tokens": model["context_tokens"]}},
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def evaluate(payload, *, execute=False, budget_usd=None, api_key=None, timeout=20, opener=None):
    """Default to offline preflight; execution requires an explicit request and budget."""
    if type(execute) is not bool:
        raise HostedInferenceError("execute must be an explicit boolean")
    if not _number(timeout, 0.001, 300):
        raise HostedInferenceError("timeout must be finite, positive and at most 300 seconds")
    receipt = preflight(payload, budget_usd=budget_usd)
    if not execute:
        return receipt
    if budget_usd is None or budget_usd < receipt["cost"]["preflight_ceiling_usd"]:
        raise HostedInferenceError("Execution requires an explicit budget covering the full-context ceiling")
    key = resolve_api_key() if api_key is None else api_key
    if not isinstance(key, str) or not key or len(key) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        return _failure(receipt, "credential_unavailable", "Missing or invalid OpenRouter credential")
    body = _request_body(payload)
    request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Accept": "application/json", "User-Agent": "f1-content-hosted/1.0",
        "X-OpenRouter-Metadata": "enabled",
    })
    opener = opener if opener is not None else urllib.request.build_opener(_NoRedirect())
    start = time.monotonic()
    receipt.update(inference_attempted=True, actual_model_inference=None, attempts=1)
    try:
        with opener.open(request, timeout=timeout) as result:
            receipt["http_status"] = result.getcode()
            final_url = result.geturl()
            raw = result.read(MAX_RESPONSE_BYTES + 1)
        _record_bytes(receipt, raw)
        if final_url != ENDPOINT or receipt["http_status"] != 200:
            raise HostedInferenceError("Unexpected endpoint or HTTP status; redirects are refused")
        response = _load(raw)
        if not isinstance(response, dict):
            raise HostedInferenceError("Provider response must be an object")
        observed = response.get("model")
        canonical_identity = (isinstance(observed, str) and 1 <= len(observed) <= 256
                              and all(c.isascii() and (c.isalnum() or c in "._/-:") for c in observed))
        receipt["observed_model"] = observed if canonical_identity else None
        generation_id = response.get("id")
        if isinstance(generation_id, str) and 1 <= len(generation_id) <= 256 and all(c.isascii() and (c.isalnum() or c in "_-.") for c in generation_id):
            receipt["observed_generation_id"] = generation_id
        # Preserve a valid request charge even if model/output/token validation fails.
        metering_error = None
        try:
            _record_cost(receipt, response)
        except HostedInferenceError as exc:
            metering_error = exc
        try:
            receipt["usage"] = _usage(response.get("usage"))
        except HostedInferenceError as exc:
            metering_error = metering_error or exc
        if metering_error:
            raise metering_error
        if not canonical_identity or observed not in RESPONSE_MODELS:
            raise HostedInferenceError("Missing or unexpected provider model identity")
        _record_routing(receipt, response)
        if response.get("object") != "chat.completion" or response.get("service_tier") not in (None, "default", "standard"):
            raise HostedInferenceError("Unexpected provider response kind or service tier")
        receipt["actual_model_inference"] = True
        model = MODELS[payload["model"]]
        measured = receipt["usage"]
        if (measured["input_tokens"] > model["context_tokens"]
                or measured["output_tokens"] > payload["max_tokens"]
                or measured["total_tokens"] > model["context_tokens"]):
            raise HostedInferenceError("Provider token usage exceeds the approved limits")
        cached = measured["cached_input_tokens"]
        cache_priced = cached is not None and model["cached_input_rate"] is not None
        cached = cached if cache_priced else 0
        receipt["cost"]["usage_rate_estimate_usd"] = float((
            Decimal(measured["input_tokens"] - cached) * Decimal(model["input_rate"])
            + Decimal(cached) * Decimal(model["cached_input_rate"] or model["input_rate"])
            + Decimal(measured["output_tokens"]) * Decimal(model["output_rate"])) / 1000000)
        receipt["cost"]["usage_rate_estimate_basis"] = "reported-cache" if cache_priced else "uncached-input-assumption"
        reported_cost = receipt["cost"]["provider_reported_cost_usd"]
        if ((reported_cost is not None and reported_cost > budget_usd)
                or receipt["cost"]["usage_rate_estimate_usd"] > budget_usd):
            raise HostedInferenceError("Provider usage or estimated cost exceeds the approved budget")
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise HostedInferenceError("Provider must return one completion")
        choice = choices[0]
        message = choice.get("message") if isinstance(choice, dict) else None
        if (not isinstance(message, dict) or message.get("role") != "assistant"
                or not isinstance(message.get("content"), str) or not message["content"].strip()
                or choice.get("finish_reason") != "stop" or type(choice.get("index")) is not int
                or choice["index"] != 0
                or message.get("tool_calls") or message.get("function_call") or message.get("refusal")):
            raise HostedInferenceError("Provider completion is missing or unfinished")
        output = message["content"].encode("utf-8")
        if payload.get("response_format") == {"type": "json_object"} and not isinstance(_load(output), dict):
            raise HostedInferenceError("Provider completion does not match JSON-object output mode")
        receipt.update(status="succeeded", actual_model_inference=True, accepted_model_result=True,
                       result={"output_text": message["content"], "output_bytes": len(output),
                               "output_sha256": hashlib.sha256(output).hexdigest()})
        return receipt
    except HostedInferenceError as exc:
        return _failure(receipt, "invalid_response", str(exc))
    except (ValueError, UnicodeError, RecursionError):
        return _failure(receipt, "invalid_response", "Provider returned invalid UTF-8 JSON data")
    except urllib.error.HTTPError as exc:
        receipt["http_status"] = exc.code
        try:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            _record_bytes(receipt, raw)
        except (OSError, ValueError, HostedInferenceError):
            pass
        finally:
            exc.close()
        return _failure(receipt, "provider_http_error", "Provider HTTP error " + str(exc.code))
    except (urllib.error.URLError, TimeoutError, OSError):
        return _failure(receipt, "connection_failed", "Provider connection failed; execution or charge may be unknown")
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - start, 6)
        receipt["completed_at"] = datetime.now(timezone.utc).isoformat()


def _record_cost(receipt, response):
    """A USD-credit charge is observed; BYOK does not reveal the upstream bill."""
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return
    cost = usage.get("cost")
    if cost is not None and not _number(cost, 0, 1000000):
        raise HostedInferenceError("Invalid OpenRouter request charge")
    receipt["cost"]["provider_reported_cost_usd"] = cost
    metadata = response.get("openrouter_metadata")
    metadata_byok = metadata.get("is_byok") if isinstance(metadata, dict) else None
    byok = usage.get("is_byok", metadata_byok)
    if (byok is not None and type(byok) is not bool) or (metadata_byok is not None and
            (type(metadata_byok) is not bool or byok != metadata_byok)):
        raise HostedInferenceError("Invalid or conflicting OpenRouter billing scope")
    receipt["cost"]["is_byok"] = byok
    if cost is not None and byok is False:
        receipt["cost"].update(actual_billing_usd=cost, actual_cost_source="openrouter_usage_cost")


def _record_routing(receipt, response):
    """Retain observed routing without inferring missing provider identity."""
    providers = []
    provider = response.get("provider")
    if provider is not None:
        providers.append(provider)
    metadata = response.get("openrouter_metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise HostedInferenceError("Invalid OpenRouter routing metadata")
        attempt = metadata.get("attempt")
        if attempt is not None:
            if type(attempt) is not int or not 1 <= attempt <= 100:
                raise HostedInferenceError("Invalid router attempt count")
            receipt["observed_router_attempts"] = attempt
            if attempt != 1:
                raise HostedInferenceError("Router fallback or retry was not authorized")
        strategy = metadata.get("strategy")
        if strategy is not None and strategy not in ("direct", "alias"):
            raise HostedInferenceError("Unexpected router strategy")
        if metadata.get("requested", MODEL_ID) != MODEL_ID:
            raise HostedInferenceError("Unexpected router model selection")
        if metadata.get("pipeline"):
            raise HostedInferenceError("Unrequested router transformation or tool use")
        endpoints = metadata.get("endpoints", {})
        if not isinstance(endpoints, dict) or not isinstance(endpoints.get("available", []), list):
            raise HostedInferenceError("Invalid routed endpoint metadata")
        if any(not isinstance(item, dict) or type(item.get("selected", False)) is not bool
               for item in endpoints.get("available", [])):
            raise HostedInferenceError("Invalid routed endpoint observation")
        selected = [item for item in endpoints.get("available", []) if isinstance(item, dict) and item.get("selected") is True]
        if len(selected) > 1:
            raise HostedInferenceError("Unexpected multiple serving endpoints")
        for item in selected:
            if not isinstance(item.get("model"), str) or item["model"] not in RESPONSE_MODELS:
                raise HostedInferenceError("Unexpected routed model identity")
            providers.append(item.get("provider"))
        attempts = metadata.get("attempts")
        if attempts is not None and (not isinstance(attempts, list) or len(attempts) != 1 or
                not isinstance(attempts[0], dict) or not isinstance(attempts[0].get("model"), str)
                or attempts[0]["model"] not in RESPONSE_MODELS):
            raise HostedInferenceError("Unexpected router execution history")
        if attempts:
            providers.append(attempts[0].get("provider"))
    if any(not isinstance(p, str) or p.lower() != "deepseek" for p in providers):
        raise HostedInferenceError("Unexpected serving provider; the requested route is pinned")
    if providers:
        receipt["observed_serving_provider"] = "DeepSeek"


def _usage(value):
    if (not isinstance(value, dict)
            or any(type(value.get(key)) is not int or value[key] < 0
                   for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
            or value["prompt_tokens"] + value["completion_tokens"] != value["total_tokens"]):
        raise HostedInferenceError("Missing or invalid provider token usage")
    cached = _detail(value.get("prompt_tokens_details"), "cached_tokens", value["prompt_tokens"])
    reasoning = _detail(value.get("completion_tokens_details"), "reasoning_tokens", value["completion_tokens"])
    return {"input_tokens": value["prompt_tokens"], "output_tokens": value["completion_tokens"],
            "total_tokens": value["total_tokens"], "cached_input_tokens": cached,
            "reasoning_tokens": reasoning}


def _record_bytes(receipt, raw):
    if len(raw) > MAX_RESPONSE_BYTES:
        receipt.update(response_prefix_sha256=hashlib.sha256(raw).hexdigest(),
                       response_prefix_bytes=len(raw))
        raise HostedInferenceError("Provider response exceeds the local byte limit")
    receipt.update(response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw))


def _detail(details, name, total):
    if details is None:
        return None
    if not isinstance(details, dict):
        raise HostedInferenceError("Invalid provider token detail")
    value = details.get(name)
    if value is not None and (type(value) is not int or not 0 <= value <= total):
        raise HostedInferenceError("Invalid provider token detail")
    return value


def _load(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise HostedInferenceError("Provider returned duplicate JSON keys")
            out[key] = value
        return out

    def constant(value):
        raise HostedInferenceError("Provider returned nonfinite JSON data")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise HostedInferenceError("Provider returned nonfinite JSON data")
        return result

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def _failure(receipt, code, message):
    receipt.update(status="failed", error={"code": code, "message": message})
    return receipt
