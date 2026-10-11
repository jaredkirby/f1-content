"""Bounded DeepInfra text inference; validation is offline unless explicitly executed.

Provider contract and dated rate sources: docs/hosted-provider-research.md.
OpenAI-compatible syntax does not use Codex ChatGPT subscription billing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.deepinfra.com/v1/openai/chat/completions"
RATE_DATE = "2026-10-10"
MAX_REQUEST_BYTES = 131072
MAX_OUTPUT_TOKENS = 16384
MAX_RESPONSE_BYTES = 2000000
MODELS = {
    "deepseek-ai/DeepSeek-V4-Pro-0813": {
        "context_tokens": 1048576, "input_rate": "1.30", "output_rate": "2.60",
        "cached_input_rate": "0.10",
    },
    "Qwen/Qwen3.5-397B-A17B": {
        "context_tokens": 262144, "input_rate": "0.45", "output_rate": "3.00",
        "cached_input_rate": "0.22",
    },
    "deepseek-ai/DeepSeek-V3.2": {
        "context_tokens": 163840, "input_rate": "0.26", "output_rate": "0.38",
        "cached_input_rate": "0.13",
    },
    "openai/gpt-oss-120b": {
        "context_tokens": 131072, "input_rate": "0.037", "output_rate": "0.17",
        "cached_input_rate": None,
    },
}


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
    optional = {"temperature", "top_p", "response_format", "reasoning_effort"}
    if (not isinstance(payload, dict) or not required <= set(payload)
            or set(payload) - required - optional):
        raise HostedInferenceError("Request requires model, messages and max_tokens; unsupported fields are refused")
    if not isinstance(payload["model"], str) or payload["model"] not in MODELS:
        raise HostedInferenceError("Unsupported model; use an exact approved hosted model ID")
    if type(payload["max_tokens"]) is not int or not 1 <= payload["max_tokens"] <= MAX_OUTPUT_TOKENS:
        raise HostedInferenceError("max_tokens must be an integer from 1 to 16384")
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
    if "reasoning_effort" in payload:
        if (payload["model"] != "deepseek-ai/DeepSeek-V4-Pro-0813"
                or not isinstance(payload["reasoning_effort"], str)
                or payload["reasoning_effort"] not in {"none", "low", "medium", "high"}):
            raise HostedInferenceError("Reasoning setting is not verified for this model")
    body = _encode({**payload, "n": 1, "stream": False, "fail_fast": True})
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
        "schema_version": "f1.hosted-inference.v1", "provider": "deepinfra",
        "endpoint": ENDPOINT, "requested_model": payload["model"],
        "observed_model": None, "status": "preflight",
        "inference_attempted": False, "actual_model_inference": False,
        "accepted_model_result": False, "attempts": 0,
        "request_sha256": hashlib.sha256(body).hexdigest(), "request_bytes": len(body),
        "input_messages_sha256": hashlib.sha256(_encode(payload["messages"])).hexdigest(),
        "input_text_bytes": sum(len(item["content"].encode("utf-8"))
                                for item in payload["messages"]),
        "response_sha256": None, "response_bytes": None, "usage": None,
        "cost": {"budget_usd": budget_usd, "preflight_ceiling_usd": float(ceiling),
                 "usage_rate_estimate_usd": None, "provider_estimated_cost_usd": None,
                 "actual_billing_usd": None, "rate_date": RATE_DATE,
                 "rate_source": "https://deepinfra.com/" + payload["model"] + "/api",
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
    if not _number(timeout, 0.001, 60):
        raise HostedInferenceError("timeout must be finite, positive and at most 60 seconds")
    receipt = preflight(payload, budget_usd=budget_usd)
    if not execute:
        return receipt
    if budget_usd is None or budget_usd < receipt["cost"]["preflight_ceiling_usd"]:
        raise HostedInferenceError("Execution requires an explicit budget covering the full-context ceiling")
    key = os.environ.get("DEEPINFRA_API_KEY", "") if api_key is None else api_key
    if not isinstance(key, str) or not key or len(key) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        return _failure(receipt, "credential_unavailable", "Missing or invalid DeepInfra credential")
    body = _request_body(payload)
    request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Accept": "application/json", "User-Agent": "f1-content-hosted/1.0",
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
        receipt["usage"] = _usage(response.get("usage"))
        estimate = response["usage"].get("estimated_cost")
        if estimate is not None and not _number(estimate, 0, 1000000):
            raise HostedInferenceError("Invalid provider cost estimate")
        receipt["cost"]["provider_estimated_cost_usd"] = estimate
        if not isinstance(response, dict) or response.get("model") != payload["model"]:
            raise HostedInferenceError("Missing or unexpected provider model identity")
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
        if ((estimate is not None and estimate > budget_usd)
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
