"""Hosted inference behavior at the public HTTP transport boundary, offline."""
import unittest
import hashlib
import io
import json
import urllib.error
import urllib.request
import urllib.response
from email.message import Message
from unittest.mock import patch

from f1_pipeline import hosted_inference


MODEL = "openai/gpt-oss-120b"


def request_payload():
    return {"model": MODEL,
            "messages": [{"role": "user", "content": "Summarize this public evidence."}],
            "max_tokens": 100}


class OfflineOpener:
    def open(self, request, timeout):
        raise AssertionError("The default must never make a provider request")


def provider_response():
    return {"id": "test-request", "object": "chat.completion", "model": MODEL,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Confirmed."},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16,
                      "estimated_cost": 0.000001124}}


class SyntheticResponse(io.BytesIO):
    def __init__(self, raw, *, status=200, url=hosted_inference.ENDPOINT):
        super().__init__(raw)
        self.status = status
        self.url = url

    def geturl(self):
        return self.url

    def getcode(self):
        return self.status


class SyntheticOpener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.response


class FailingOpener:
    def __init__(self, error):
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        raise self.error


class HostedInferenceTests(unittest.TestCase):
    def test_default_is_offline_preflight_with_conservative_dated_cost(self):
        receipt = hosted_inference.evaluate(request_payload(), opener=OfflineOpener())
        self.assertEqual(receipt["status"], "preflight")
        self.assertFalse(receipt["inference_attempted"])
        self.assertFalse(receipt["accepted_model_result"])
        self.assertEqual(receipt["attempts"], 0)
        self.assertEqual(receipt["cost"]["preflight_ceiling_usd"], 0.004866664)
        self.assertIsNone(receipt["cost"]["actual_billing_usd"])
        self.assertNotIn("result", receipt)

    def test_preflight_refuses_unbounded_or_unsupported_requests(self):
        invalid = [None, [], {}, {**request_payload(), "model": "closed/model"},
                   {**request_payload(), "model": []},
                   {**request_payload(), "max_tokens": True},
                   {**request_payload(), "max_tokens": 0},
                   {**request_payload(), "max_tokens": 16385},
                   {**request_payload(), "stream": True},
                   {**request_payload(), "service_tier": "priority"},
                   {**request_payload(), "messages": []},
                   {**request_payload(), "messages": [{"role": "tool", "content": "x"}]},
                   {**request_payload(), "messages": [{"role": "user", "content": []}]},
                   {**request_payload(), "messages": [{"role": "user", "content": "x", "tool_calls": []}]},
                   {**request_payload(), "messages": [{"role": "user", "content": "x" * 131072}]},
                   {**request_payload(), "temperature": float("nan")},
                   {**request_payload(), "top_p": True},
                   {**request_payload(), "response_format": {"type": "json_schema"}},
                   {**request_payload(), "reasoning_effort": "high"}]
        for payload in invalid:
            with self.subTest(payload_type=type(payload).__name__), self.assertRaises(hosted_inference.HostedInferenceError):
                hosted_inference.preflight(payload)

    def test_exact_shortlist_models_have_independent_full_context_costs(self):
        cases = [("deepseek-ai/DeepSeek-V4-Pro-0813", 1.3634088),
                 ("Qwen/Qwen3.5-397B-A17B", 0.1182648),
                 ("deepseek-ai/DeepSeek-V3.2", 0.0426364),
                 (MODEL, 0.004866664)]
        for model, ceiling in cases:
            payload = {**request_payload(), "model": model}
            if model == "deepseek-ai/DeepSeek-V4-Pro-0813":
                payload["reasoning_effort"] = "high"
            with self.subTest(model=model):
                receipt = hosted_inference.preflight(payload)
                self.assertEqual(receipt["requested_model"], model)
                self.assertEqual(receipt["cost"]["preflight_ceiling_usd"], ceiling)

    def test_execution_requires_finite_budget_timeout_and_explicit_boolean(self):
        cases = [{"execute": True}, {"execute": "yes", "budget_usd": 1},
                 {"execute": True, "budget_usd": True},
                 {"execute": True, "budget_usd": float("nan")},
                 {"execute": True, "budget_usd": float("inf")},
                 {"execute": True, "budget_usd": 0.001},
                 {"execute": True, "budget_usd": 1, "timeout": True},
                 {"execute": True, "budget_usd": 1, "timeout": 0},
                 {"execute": True, "budget_usd": 1, "timeout": 61}]
        for options in cases:
            with self.subTest(options=options), self.assertRaises(hosted_inference.HostedInferenceError):
                hosted_inference.evaluate(request_payload(), opener=OfflineOpener(), **options)

    def test_missing_or_invalid_key_is_unattempted_failure_without_secret(self):
        for key in ("", "bad\nkey", "bad\rkey", 12):
            with self.subTest(key_type=type(key).__name__):
                receipt = hosted_inference.evaluate(request_payload(), execute=True,
                    budget_usd=1, api_key=key, opener=OfflineOpener())
                self.assertEqual(receipt["status"], "failed")
                self.assertFalse(receipt["inference_attempted"])
                self.assertEqual(receipt["attempts"], 0)
                self.assertNotIn("result", receipt)
                self.assertNotIn("bad", str(receipt))

    def test_explicit_request_records_identity_output_and_actual_usage(self):
        raw = json.dumps(provider_response()).encode("utf-8")
        opener = SyntheticOpener(SyntheticResponse(raw))
        receipt = hosted_inference.evaluate(request_payload(), execute=True,
            budget_usd=1, api_key="test-only", opener=opener)
        self.assertEqual(receipt["status"], "succeeded")
        self.assertTrue(receipt["inference_attempted"])
        self.assertTrue(receipt["accepted_model_result"])
        self.assertEqual(receipt["observed_model"], MODEL)
        self.assertEqual(receipt["attempts"], 1)
        self.assertEqual(receipt["usage"], {"input_tokens": 12, "output_tokens": 4,
            "total_tokens": 16, "cached_input_tokens": None, "reasoning_tokens": None})
        self.assertEqual(receipt["result"]["output_text"], "Confirmed.")
        self.assertEqual(receipt["result"]["output_bytes"], 10)
        self.assertEqual(receipt["response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt["cost"]["usage_rate_estimate_usd"], 0.000001124)
        self.assertEqual(receipt["cost"]["provider_estimated_cost_usd"], 0.000001124)
        self.assertIsNone(receipt["cost"]["actual_billing_usd"])
        self.assertNotIn("test-only", json.dumps(receipt))
        sent, timeout = opener.requests[0]
        self.assertEqual(sent.full_url, "https://api.deepinfra.com/v1/openai/chat/completions")
        self.assertEqual(sent.get_method(), "POST")
        self.assertEqual(timeout, 20)
        body = json.loads(sent.data)
        self.assertEqual(body["n"], 1)
        self.assertFalse(body["stream"])
        self.assertTrue(body["fail_fast"])
        self.assertNotIn("service_tier", body)
        self.assertEqual(receipt["request_sha256"], hashlib.sha256(sent.data).hexdigest())

    def test_redirect_or_failed_transport_is_never_retried_or_accepted(self):
        raw = json.dumps(provider_response()).encode()
        responses = [SyntheticResponse(raw, status=302),
                     SyntheticResponse(raw, url="https://other.example/"),
                     urllib.error.HTTPError(hosted_inference.ENDPOINT, 429, "private-error", {}, io.BytesIO(b"private-error")),
                     urllib.error.URLError("private-error"), TimeoutError("private-error")]
        for response in responses:
            opener = FailingOpener(response) if isinstance(response, Exception) else SyntheticOpener(response)
            with self.subTest(response_type=type(response).__name__):
                receipt = hosted_inference.evaluate(request_payload(), execute=True,
                    budget_usd=1, api_key="test-only", opener=opener)
                self.assertEqual(receipt["status"], "failed")
                self.assertFalse(receipt["accepted_model_result"])
                self.assertEqual(len(opener.requests), 1)
                self.assertEqual(receipt["attempts"], 1)
                self.assertNotIn("result", receipt)
                self.assertNotIn("private-error", json.dumps(receipt))

    def test_invalid_response_usage_or_spending_never_becomes_an_output(self):
        cases = []
        for key, value in [("prompt_tokens", True), ("completion_tokens", -1),
                           ("total_tokens", 15), ("estimated_cost", float("nan")),
                           ("estimated_cost", -1), ("estimated_cost", True),
                           ("estimated_cost", 2),
                           ("prompt_tokens_details", {"cached_tokens": 13}),
                           ("completion_tokens_details", {"reasoning_tokens": 5}),
                           ("completion_tokens_details", {"reasoning_tokens": True})]:
            response = provider_response()
            response["usage"][key] = value
            cases.append(response)
        for key, value in [("object", "not.chat.completion"),
                           ("service_tier", "priority"), ("usage", None),
                           ("choices", [{"index": 0, "message": []}])]:
            response = provider_response()
            response[key] = value
            cases.append(response)
        response = provider_response()
        response["choices"][0]["message"]["tool_calls"] = [{"id": "tool"}]
        cases.append(response)
        response = provider_response()
        response["choices"][0]["index"] = False
        cases.append(response)
        for index, response in enumerate(cases):
            with self.subTest(case=index):
                raw = json.dumps(response).encode()
                receipt = hosted_inference.evaluate(request_payload(), execute=True,
                    budget_usd=1, api_key="test-only", opener=SyntheticOpener(SyntheticResponse(raw)))
                self.assertEqual(receipt["status"], "failed")
                self.assertFalse(receipt["accepted_model_result"])
                self.assertNotIn("result", receipt)
                self.assertEqual(receipt["response_sha256"], hashlib.sha256(raw).hexdigest())

    def test_reported_cache_and_reasoning_tokens_are_subsets_not_extra_charges(self):
        response = provider_response()
        response["model"] = "Qwen/Qwen3.5-397B-A17B"
        response["usage"].update(prompt_tokens_details={"cached_tokens": 8},
                                 completion_tokens_details={"reasoning_tokens": 2},
                                 estimated_cost=0.00001556)
        payload = {**request_payload(), "model": response["model"]}
        receipt = hosted_inference.evaluate(payload, execute=True, budget_usd=1,
            api_key="test-only", opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(receipt["usage"]["output_tokens"], 4)
        self.assertEqual(receipt["usage"]["reasoning_tokens"], 2)
        self.assertEqual(receipt["usage"]["cached_input_tokens"], 8)
        self.assertEqual(receipt["cost"]["usage_rate_estimate_usd"], 0.00001556)

    def test_oversized_response_is_hashed_only_as_an_explicit_prefix(self):
        response = provider_response()
        response["choices"][0]["message"]["content"] = "x" * 2000100
        raw = json.dumps(response).encode()
        receipt = hosted_inference.evaluate(request_payload(), execute=True, budget_usd=1,
            api_key="test-only", opener=SyntheticOpener(SyntheticResponse(raw)))
        self.assertEqual(receipt["status"], "failed")
        self.assertNotIn("result", receipt)
        self.assertIsNone(receipt["response_sha256"])
        self.assertIsNone(receipt["response_bytes"])
        self.assertEqual(receipt["response_prefix_bytes"], 2000001)
        self.assertEqual(receipt["response_prefix_sha256"], hashlib.sha256(raw[:2000001]).hexdigest())

    def test_json_object_mode_refuses_invalid_or_nonobject_model_text(self):
        payload = {**request_payload(), "response_format": {"type": "json_object"}}
        for text in ("Confirmed.", "[]", '{"a": 1, "a": 2}', '{"a": NaN}', '{"a": 1e999}'):
            response = provider_response()
            response["choices"][0]["message"]["content"] = text
            with self.subTest(text=text):
                receipt = hosted_inference.evaluate(payload, execute=True, budget_usd=1,
                    api_key="test-only", opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
                self.assertEqual(receipt["status"], "failed")
                self.assertNotIn("result", receipt)
                self.assertEqual(receipt["usage"]["output_tokens"], 4)

    def test_malformed_deep_or_duplicate_json_fails_with_hash_and_safe_error(self):
        raws = [b"private-body", b"\xff", b"[" * 11000 + b"]" * 11000,
                b'{"model":"openai/gpt-oss-120b","model":"different"}']
        for raw in raws:
            with self.subTest(bytes=len(raw)):
                receipt = hosted_inference.evaluate(request_payload(), execute=True, budget_usd=1,
                    api_key="test-only", opener=SyntheticOpener(SyntheticResponse(raw)))
                self.assertEqual(receipt["status"], "failed")
                self.assertNotIn("result", receipt)
                self.assertNotIn("private-body", json.dumps(receipt))
                self.assertEqual(receipt["response_sha256"], hashlib.sha256(raw).hexdigest())

    def test_failed_identity_truncation_and_token_limit_keep_measured_usage(self):
        cases = []
        response = provider_response()
        response["model"] = "deepseek-ai/DeepSeek-V3.2"
        cases.append(response)
        response = provider_response()
        response["choices"][0]["finish_reason"] = "length"
        cases.append(response)
        response = provider_response()
        response["usage"].update(completion_tokens=101, total_tokens=113)
        cases.append(response)
        for response in cases:
            raw = json.dumps(response).encode()
            receipt = hosted_inference.evaluate(request_payload(), execute=True, budget_usd=1,
                api_key="test-only", opener=SyntheticOpener(SyntheticResponse(raw)))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["observed_model"], response["model"])
            self.assertEqual(receipt["usage"]["input_tokens"], 12)
            self.assertEqual(receipt["usage"]["output_tokens"], response["usage"]["completion_tokens"])
            self.assertEqual(receipt["response_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertNotIn("result", receipt)

    def test_invalid_observed_identity_remains_unknown_and_keeps_failure_metering(self):
        for model in (None, "", " ", "\t\n", " openai/gpt-oss-120b", "openai/gpt-oss-120b "):
            response = provider_response()
            response["model"] = model
            raw = json.dumps(response).encode()
            with self.subTest(model_type=type(model).__name__):
                receipt = hosted_inference.evaluate(request_payload(), execute=True, budget_usd=1,
                    api_key="test-only", opener=SyntheticOpener(SyntheticResponse(raw)))
                self.assertEqual(receipt["status"], "failed")
                self.assertIsNone(receipt["observed_model"])
                self.assertEqual(receipt["requested_model"], MODEL)
                self.assertEqual(receipt["usage"]["input_tokens"], 12)
                self.assertEqual(receipt["usage"]["output_tokens"], 4)
                self.assertEqual(receipt["cost"]["provider_estimated_cost_usd"], 0.000001124)
                self.assertIsNone(receipt["cost"]["actual_billing_usd"])
                self.assertEqual(receipt["response_sha256"], hashlib.sha256(raw).hexdigest())
                self.assertNotIn("result", receipt)

    def test_production_transport_refuses_redirect_without_forwarding_credential(self):
        requests = []
        raw = b"private-redirect-body"

        class ProviderTransport(urllib.request.HTTPSHandler):
            def https_open(self, request):
                requests.append(request)
                headers = Message()
                headers["Location"] = "https://other.example/provider"
                response = urllib.response.addinfourl(io.BytesIO(raw), headers, request.full_url, 302)
                response.msg = "Found"
                return response

        build = urllib.request.build_opener
        with patch("urllib.request.build_opener", side_effect=lambda *handlers: build(ProviderTransport(), *handlers)):
            receipt = hosted_inference.evaluate(request_payload(), execute=True,
                budget_usd=1, api_key="test-only")
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual([request.full_url for request in requests], [hosted_inference.ENDPOINT])
        self.assertEqual(receipt["response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotIn("private-redirect-body", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
