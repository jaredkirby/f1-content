"""Hosted inference behavior at the public HTTP transport boundary, offline."""
import unittest
import hashlib
import io
import json
import os
import urllib.error
import urllib.request
import urllib.response
from email.message import Message
from unittest.mock import patch

from f1_pipeline import hosted_inference


MODEL = "deepseek/deepseek-v4.1-flash"


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
                      "cost": 0.000001124, "is_byok": False}}


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
        self.assertEqual(receipt["cost"]["preflight_ceiling_usd"], 0.3146928)
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
                   {**request_payload(), "reasoning_effort": "medium"}]
        for payload in invalid:
            with self.subTest(payload_type=type(payload).__name__), self.assertRaises(hosted_inference.HostedInferenceError):
                hosted_inference.preflight(payload)

    def test_exact_requested_model_and_verified_reasoning_efforts(self):
        for effort in ('low', 'high', 'max'):
            receipt = hosted_inference.preflight({**request_payload(), 'reasoning_effort': effort})
            self.assertEqual(receipt['requested_model'], MODEL)
            self.assertEqual(receipt['cost']['preflight_ceiling_usd'], 0.3146928)
        for model in ('openai/gpt-oss-120b', 'deepseek-ai/DeepSeek-V4-Pro-0813', MODEL + ':free'):
            with self.assertRaises(hosted_inference.HostedInferenceError):
                hosted_inference.preflight({**request_payload(), 'model': model})

    def test_reasoning_forms_are_explicit_and_conflicts_fail_before_a_call(self):
        for reasoning in ({'enabled': False}, {'effort': 'max', 'exclude': False}):
            receipt = hosted_inference.preflight({**request_payload(), 'reasoning': reasoning})
            for key,value in reasoning.items():
                self.assertEqual(receipt['effective_settings']['reasoning'][key],value)
        for reasoning in ({'effort':'medium'}, {'enabled':'false'}, {'max_tokens':100},
                          {'effort':[], 'exclude':True}, {'effort':'high','enabled':False}):
            with self.subTest(reasoning=reasoning), self.assertRaises(hosted_inference.HostedInferenceError):
                hosted_inference.evaluate({**request_payload(),'reasoning':reasoning},opener=OfflineOpener())
        with self.assertRaises(hosted_inference.HostedInferenceError):
            hosted_inference.preflight({**request_payload(),'reasoning':{'enabled':False},'reasoning_effort':'high'})

    def test_only_openrouter_environment_credential_is_used(self):
        with patch.dict(os.environ, {'DEEPINFRA_API_KEY':'legacy-test-key'}, clear=True):
            receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,opener=OfflineOpener())
            self.assertFalse(receipt['inference_attempted'])
            self.assertEqual(receipt['error']['code'],'credential_unavailable')
        opener=SyntheticOpener(SyntheticResponse(json.dumps(provider_response()).encode()))
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':'openrouter-test-only'}, clear=True):
            receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,opener=opener)
        self.assertEqual(receipt['status'],'succeeded')
        self.assertEqual(opener.requests[0][0].get_header('Authorization'),'Bearer openrouter-test-only')
        self.assertNotIn('openrouter-test-only',json.dumps(receipt))

    def test_credit_charge_is_not_a_rate_estimate_or_a_complete_byok_bill(self):
        for byok, actual in ((False,0.002),(True,None),(None,None)):
            response=provider_response();response['usage'].update(cost=0.002)
            if byok is None:response['usage'].pop('is_byok')
            else:response['usage']['is_byok']=byok
            receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,
                api_key='test-only',opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
            self.assertEqual(receipt['status'],'succeeded')
            self.assertEqual(receipt['cost']['provider_reported_cost_usd'],0.002)
            self.assertEqual(receipt['cost']['actual_billing_usd'],actual)
            self.assertEqual(receipt['cost']['usage_rate_estimate_usd'],0.0000084)
        response=provider_response();response['usage'].pop('cost')
        receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,
            api_key='test-only',opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
        self.assertIsNone(receipt['cost']['actual_billing_usd'])

    def test_canonical_alias_and_observed_provider_are_retained_without_inference(self):
        response=provider_response();response['model']='deepseek/deepseek-v4.1-flash-20260910'
        response['provider']='DeepSeek'
        response['openrouter_metadata']={'requested':MODEL,'strategy':'direct','attempt':1,
            'is_byok':False,'endpoints':{'available':[{'model':response['model'],'provider':'DeepSeek','selected':True}]}}
        receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,
            api_key='test-only',opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
        self.assertEqual(receipt['status'],'succeeded')
        self.assertEqual(receipt['observed_model'],response['model'])
        self.assertEqual(receipt['observed_serving_provider'],'DeepSeek')
        self.assertEqual(receipt['observed_router_attempts'],1)
        unobserved=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,
            api_key='test-only',opener=SyntheticOpener(SyntheticResponse(json.dumps(provider_response()).encode())))
        self.assertIsNone(unobserved['observed_serving_provider'])
        self.assertIsNone(unobserved['observed_router_attempts'])

    def test_unrequested_routing_and_transformations_fail_with_charge_retained(self):
        variants=[{'provider':'another-provider'}, {'openrouter_metadata':{'attempt':2}},
                  {'openrouter_metadata':{'strategy':'fallback'}}, {'openrouter_metadata':{'strategy':[]}},
                  {'openrouter_metadata':{'requested':'different/model'}},
                  {'openrouter_metadata':{'pipeline':[{'type':'context_compression'}]}},
                  {'openrouter_metadata':{'endpoints':{'available':[{'selected':True,'model':[]}]}}},
                  {'openrouter_metadata':{'is_byok':True}}, {'model':[]}]
        for variant in variants:
            response={**provider_response(),**variant}
            with self.subTest(variant=variant):
                receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,
                    api_key='test-only',opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
                self.assertEqual(receipt['status'],'failed')
                self.assertFalse(receipt['accepted_model_result'])
                self.assertEqual(receipt['cost']['provider_reported_cost_usd'],0.000001124)
                self.assertEqual(receipt['usage']['input_tokens'],12)

    def test_valid_token_or_charge_measurements_survive_other_metering_failures(self):
        response=provider_response();response['usage']['total_tokens']=999
        receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,
            api_key='test-only',opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['cost']['actual_billing_usd'],0.000001124)
        response=provider_response();response['usage']['cost']=-1
        receipt=hosted_inference.evaluate(request_payload(),execute=True,budget_usd=1,
            api_key='test-only',opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['usage']['total_tokens'],16)
        self.assertIsNone(receipt['cost']['actual_billing_usd'])

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
        self.assertEqual(receipt["cost"]["usage_rate_estimate_usd"], 0.0000084)
        self.assertIsNone(receipt["cost"]["provider_estimated_cost_usd"])
        self.assertEqual(receipt["cost"]["provider_reported_cost_usd"], 0.000001124)
        self.assertEqual(receipt["cost"]["actual_billing_usd"], 0.000001124)
        self.assertNotIn("test-only", json.dumps(receipt))
        sent, timeout = opener.requests[0]
        self.assertEqual(sent.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(sent.get_method(), "POST")
        self.assertEqual(timeout, 20)
        body = json.loads(sent.data)
        self.assertNotIn("n", body)
        self.assertFalse(body["stream"])
        self.assertNotIn('fail_fast', body)
        self.assertEqual(body['provider']['only'], ['deepseek'])
        self.assertFalse(body['provider']['allow_fallbacks'])
        self.assertTrue(body['provider']['require_parameters'])
        self.assertEqual(body['provider']['max_price'], {'prompt': 0.3, 'completion': 1.2})
        self.assertEqual(sent.get_header('Authorization'), 'Bearer test-only')
        self.assertNotIn("service_tier", body)
        self.assertEqual(receipt["request_sha256"], hashlib.sha256(sent.data).hexdigest())

    def test_redirect_or_failed_transport_is_never_retried_or_accepted(self):
        raw = json.dumps(provider_response()).encode()
        responses = [SyntheticResponse(raw, status=302),
                     SyntheticResponse(raw, url="https://other.example/"),
                     urllib.error.URLError("private-error"), TimeoutError("private-error")]
        responses += [urllib.error.HTTPError(hosted_inference.ENDPOINT, status, "private-error", {},
                                             io.BytesIO(b"private-error"))
                      for status in (400,401,402,403,404,429,502)]
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
                           ("total_tokens", 15), ("cost", float("nan")),
                           ("cost", -1), ("cost", True),
                           ("cost", 2),
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
        response["usage"].update(prompt_tokens_details={"cached_tokens": 8},
                                 completion_tokens_details={"reasoning_tokens": 2},
                                 cost=0.000006048)
        payload = {**request_payload(), "model": response["model"]}
        receipt = hosted_inference.evaluate(payload, execute=True, budget_usd=1,
            api_key="test-only", opener=SyntheticOpener(SyntheticResponse(json.dumps(response).encode())))
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(receipt["usage"]["output_tokens"], 4)
        self.assertEqual(receipt["usage"]["reasoning_tokens"], 2)
        self.assertEqual(receipt["usage"]["cached_input_tokens"], 8)
        self.assertEqual(receipt["cost"]["usage_rate_estimate_usd"], 0.000006048)

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
                self.assertIsNone(receipt["cost"]["provider_estimated_cost_usd"])
                self.assertEqual(receipt["cost"]["provider_reported_cost_usd"], 0.000001124)
                self.assertEqual(receipt["cost"]["actual_billing_usd"], 0.000001124)
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
