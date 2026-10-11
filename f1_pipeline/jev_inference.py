"""Native Jev via OpenRouter; no chat-model emulation or automatic retry.

Contract/rates: docs/openrouter-jev-integration-research.md (2026-10-10).
"""
from datetime import datetime, timezone
import hashlib
import json
from .credentials import resolve_api_key
import re
import time
import urllib.error
import urllib.request
from .jev_adapter import JevError, NoRedirect, encode, number, validate_request, validate_response

ENDPOINT = 'https://openrouter.ai/api/v1/systemone'
MODEL_ID = 'typesafe/jev-1.13'
CANONICAL_SLUG = 'typesafe/jev-1.13-20260917'
MAX_REQUEST_BYTES = 131072
MAX_RESPONSE_BYTES = 2000000
ROUTING = {'only': ['typesafe'], 'allow_fallbacks': False,
           'max_price': {'prompt': 0.042, 'completion': 0}}


def preflight(payload, *, budget_usd=None):
    try:
        validate_request(payload, model=MODEL_ID)
    except JevError as exc:
        raise ValueError(str(exc)) from None
    body = encode({**payload, 'provider': ROUTING})
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError('Jev request exceeds local byte limit')
    if budget_usd is not None and (not number(budget_usd, 0, 1000000) or budget_usd <= 0):
        raise ValueError('budget_usd must be positive finite USD')
    return {
        'schema_version': 'f1.hosted-inference.v1', 'provider': 'openrouter',
        'endpoint': ENDPOINT, 'requested_model': MODEL_ID, 'observed_model': None,
        'status': 'preflight', 'inference_attempted': False, 'actual_model_inference': False,
        'accepted_model_result': False, 'attempts': 0, 'effective_settings': {'provider': ROUTING},
        'request_sha256': hashlib.sha256(body).hexdigest(), 'request_bytes': len(body),
        'catalog_canonical_slug': CANONICAL_SLUG, 'observed_serving_provider': None,
        'observed_generation_id': None, 'response_sha256': None, 'usage': None,
        'cost': {'budget_usd': budget_usd, 'preflight_ceiling_usd': 0.002688,
                 'actual_billing_usd': None, 'provider_reported_cost_usd': None,
                 'usage_rate_estimate_usd': None, 'actual_cost_source': 'unknown',
                 'billing_scope': 'OpenRouter reported charge; other billing unobserved',
                 'rate_date': '2026-10-10', 'rate_basis': '64000 context tokens at 0.042 USD per million'},
        'completed_at': datetime.now(timezone.utc).isoformat(),
    }


def evaluate(payload, *, execute=False, budget_usd=None, api_key=None, timeout=20, opener=None):
    if type(execute) is not bool or not number(timeout, 0.001, 300):
        raise ValueError('Execution must be explicit and transport timeout bounded by 300 seconds')
    receipt = preflight(payload, budget_usd=budget_usd)
    if not execute:
        return receipt
    if budget_usd is None or budget_usd < receipt['cost']['preflight_ceiling_usd']:
        raise ValueError('Execution requires budget covering the full-context ceiling')
    key = resolve_api_key() if api_key is None else api_key
    if not isinstance(key, str) or not 1 <= len(key) <= 512 or any(not 33 <= ord(c) <= 126 for c in key):
        receipt.update(status='failed', error={'code': 'credential_unavailable', 'message': 'OpenRouter credential unavailable'})
        return receipt
    request = urllib.request.Request(ENDPOINT, data=encode({**payload, 'provider': ROUTING}), method='POST',
        headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json', 'Accept': 'application/json',
                 'User-Agent': 'f1-content-jev-openrouter/1.0'})
    opener = opener if opener is not None else urllib.request.build_opener(NoRedirect())
    start = time.monotonic()
    receipt.update(inference_attempted=True, actual_model_inference=None, attempts=1)
    try:
        with opener.open(request, timeout=timeout) as response:
            status, url = response.getcode(), response.geturl()
            raw = response.read(MAX_RESPONSE_BYTES+1)
        receipt.update(http_status=status, response_bytes=len(raw), response_sha256=hashlib.sha256(raw).hexdigest())
        if len(raw) > MAX_RESPONSE_BYTES or status != 200 or url != ENDPOINT:
            raise ValueError('Unexpected or oversized provider response')
        result = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        if not isinstance(result, dict):
            raise ValueError('Provider response must be an object')
        usage = result.get('usage', {})
        if not isinstance(usage, dict):
            raise ValueError('Provider usage is missing')
        cost = usage.get('cost')
        if cost is not None:
            if not number(cost, 0, 1000000):
                raise ValueError('Invalid provider charge')
            receipt['cost'].update(actual_billing_usd=cost, provider_reported_cost_usd=cost,
                                   actual_cost_source='provider_receipt')
        observed = result.get('model')
        if isinstance(observed, str) and re.fullmatch(r'[A-Za-z0-9_./:-]{1,256}', observed):
            receipt['observed_model'] = observed
        generation = result.get('id')
        if isinstance(generation, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,256}', generation):
            receipt['observed_generation_id'] = generation
        provider = result.get('provider')
        if provider not in (None, 'TypeSafe', 'typesafe'):
            raise ValueError('Unexpected serving provider')
        receipt['observed_serving_provider'] = provider
        if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input_tokens', 'output_tokens')):
            raise ValueError('Missing or invalid provider token usage')
        receipt['usage'] = {k: usage[k] for k in ('input_tokens', 'output_tokens')}
        estimate = usage['input_tokens'] * 0.042 / 1000000
        receipt['cost']['usage_rate_estimate_usd'] = estimate
        if (usage['input_tokens'] > 32000 or usage['output_tokens'] > 57600
                or sum(receipt['usage'].values()) > 64000 or estimate > budget_usd
                or (cost is not None and cost > budget_usd)):
            raise ValueError('Provider usage or charge exceeds approved limits')
        validate_response(result, payload, allowed_models={MODEL_ID, CANONICAL_SLUG})
        for name, question in payload['questions'].items():
            if question['type'] == 'score' and result['answers'][name]['legend'] != {
                    str(i): value for i, value in enumerate(question['criteria'])}:
                raise ValueError('Score legend changed from the requested rubric')
        output = encode(result['answers']).decode()
        receipt.update(status='succeeded', actual_model_inference=True, accepted_model_result=True,
                       result={'answers': result['answers'], 'output_text': output,
                               'output_sha256': hashlib.sha256(output.encode()).hexdigest()})
    except urllib.error.HTTPError as exc:
        receipt.update(status='failed', http_status=exc.code,
                       error={'code': 'provider_http_error', 'message': 'Provider HTTP error '+str(exc.code)})
        exc.close()
    except (urllib.error.URLError, TimeoutError, OSError):
        receipt.update(status='failed', error={'code': 'connection_failed', 'message': 'Execution and charge may be unknown'})
    except (ValueError, JevError, UnicodeError, RecursionError):
        receipt.update(status='failed', error={'code': 'invalid_response',
                       'message': 'Response does not satisfy the native Jev advisory contract'})
    finally:
        receipt['elapsed_seconds'] = round(time.monotonic()-start, 6)
        receipt['completed_at'] = datetime.now(timezone.utc).isoformat()
    return receipt
