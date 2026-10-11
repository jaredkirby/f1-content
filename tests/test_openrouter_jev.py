"""Native Jev over OpenRouter: synthetic provider HTTP boundary only."""
import json
import io
import copy
import urllib.error
import unittest
from unittest.mock import patch

from f1_pipeline import jev_inference

REQUEST = {'model': 'typesafe/jev-1.13', 'state': {'claim': 'Fictional A finished first'},
           'questions': {'support': {'type': 'choice', 'instructions': 'Use evidence only',
             'criteria': {'supported': 'Direct evidence', 'insufficient_evidence': 'Missing'}}}}

RESPONSE = {'model': 'typesafe/jev-1.13-20260917', 'id': 'gen-synthetic', 'provider': 'TypeSafe',
            'usage': {'input_tokens': 1000, 'output_tokens': 60, 'cost': 0.000042},
            'answers': {'support': {'type': 'choice', 'choice': 'supported',
                'probabilities': {'supported': 0.9, 'insufficient_evidence': 0.1}, 'confidence': 0.8}}}


class Reply(io.BytesIO):
    def getcode(self): return 200
    def geturl(self): return jev_inference.ENDPOINT


class Provider:
    def __init__(self, response): self.response, self.requests = response, []
    def open(self, request, timeout):
        self.requests.append(request)
        return Reply(json.dumps(self.response).encode())


class OpenRouterJevTests(unittest.TestCase):
    def test_preflight_is_offline_and_pins_native_jev_with_a_total_ceiling(self):
        with patch('urllib.request.build_opener', side_effect=AssertionError('network')):
            result = jev_inference.evaluate(REQUEST)
        self.assertFalse(result['inference_attempted'])
        self.assertEqual(result['requested_model'], 'typesafe/jev-1.13')
        self.assertEqual(result['cost']['preflight_ceiling_usd'], 0.002688)
        self.assertEqual(result['effective_settings']['provider']['only'], ['typesafe'])
        self.assertFalse(result['effective_settings']['provider']['allow_fallbacks'])
        self.assertIsNone(result['cost']['actual_billing_usd'])

    def test_native_jev_execution_retains_typed_answers_identity_and_measured_charge(self):
        provider = Provider(RESPONSE)
        result = jev_inference.evaluate(REQUEST, execute=True, budget_usd=0.003,
                                       api_key='synthetic-test-key', opener=provider)
        self.assertTrue(result['accepted_model_result'])
        self.assertEqual(result['result']['answers']['support']['choice'], 'supported')
        self.assertEqual(result['cost']['actual_billing_usd'], 0.000042)
        self.assertEqual(result['usage']['input_tokens'], 1000)
        self.assertEqual(result['observed_model'], 'typesafe/jev-1.13-20260917')
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(provider.requests[0].full_url, jev_inference.ENDPOINT)
        self.assertNotIn('synthetic-test-key', json.dumps(result))

    def test_invalid_judgments_retain_a_reported_charge_without_acceptance(self):
        for mutate in (lambda r:r['answers']['support'].pop('confidence'),
                       lambda r:r.update(model=['invalid']),
                       lambda r:r.update(provider='different-provider'),
                       lambda r:r['answers']['support'].update(probabilities={'supported':1.2,'insufficient_evidence':-0.2})):
            response=copy.deepcopy(RESPONSE);mutate(response)
            with self.subTest(response=response):
                result=jev_inference.evaluate(REQUEST, execute=True, budget_usd=0.003,
                    api_key='synthetic-test-key',opener=Provider(response))
                self.assertFalse(result['accepted_model_result'])
                self.assertEqual(result['cost']['actual_billing_usd'],0.000042)

    def test_no_key_under_budget_and_throttling_never_retry_or_fake_results(self):
        provider=Provider(RESPONSE)
        result=jev_inference.evaluate(REQUEST,execute=True,budget_usd=0.003,api_key='',opener=provider)
        self.assertFalse(result['inference_attempted']);self.assertEqual(provider.requests,[])
        with self.assertRaises(ValueError):
            jev_inference.evaluate(REQUEST,execute=True,budget_usd=0.001,api_key='synthetic',opener=provider)
        class Throttled:
            calls=0
            def open(self,request,timeout):
                self.calls+=1
                raise urllib.error.HTTPError(request.full_url,429,'busy',{},io.BytesIO(b'{}'))
        transport=Throttled()
        result=jev_inference.evaluate(REQUEST,execute=True,budget_usd=0.003,api_key='synthetic',opener=transport)
        self.assertEqual(transport.calls,1)
        self.assertIsNone(result['actual_model_inference'])
        self.assertIsNone(result['cost']['actual_billing_usd'])
