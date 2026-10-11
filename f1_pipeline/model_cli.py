"""Explicit workspace commands for human feedback and model work.

Hosted execution is never part of ``run``. It needs a reviewed request, a budget
and an explicit execute flag; subscription-authored work is imported offline.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

COMMANDS = (
    'feedback-record', 'feedback-status', 'preference-record', 'preference-status',
    'model-import', 'model-route', 'model-evaluate', 'model-infer', 'jev-infer', 'model-run', 'model-review',
)
MAX_DOCUMENT_BYTES = 2_000_000


def options(parser):
    group = parser.add_argument_group('explicit feedback and model-work commands')
    group.add_argument('--request', type=Path, help='Reviewed JSON input for an explicit model/feedback command')
    group.add_argument('--task', default='story_script', help='Task for model-route or model-infer')
    group.add_argument('--subscription-status', default='unknown',
                       choices=['available', 'limited', 'unavailable', 'unknown'])
    group.add_argument('--comparison-id', help='Bounded comparison identifier')
    group.add_argument('--work-id', help='Unique model-work identifier')
    group.add_argument('--prompt-version', help='Actual prompt version for a hosted execution')
    group.add_argument('--rubric-version', help='Actual review-rubric version for a hosted execution')
    group.add_argument('--evidence', action='append', default=[], help='Event-relative evidence file; repeat as needed')
    group.add_argument('--expected-plan-sha256', help='Require the exact authorized model-plan bytes before execution')
    group.add_argument('--execute', action='store_true', help='Explicitly execute bounded hosted model work')
    group.add_argument('--budget-usd', type=float, help='Authorized hosted request budget under the documented rates')
    group.add_argument('--timeout-seconds', type=float, default=20, help='Bounded hosted transport timeout, at most 60 seconds')


def load_request(path):
    if path is None:
        raise ValueError('This command requires --request with a reviewed JSON document')
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError('Input document exceeds the local byte limit')
    return json.loads(path.read_text(encoding='utf-8'),
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Finite JSON is required')))


def _slug(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,99}', value):
        raise ValueError(label + ' must be an explicit bounded identifier')
    return value


def _binding(relative):
    from .core import ROOT, digest, safe_relative
    path = safe_relative(relative)
    if not path.is_file():
        raise ValueError('Referenced evidence is not a workspace file')
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)}


def _hosted_work(args):
    from .core import ROOT, config, ensure_space, safe_relative, write_json
    if args.command == 'jev-infer':
        from .jev_inference import evaluate, preflight, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES
    else:
        from .hosted_inference import evaluate, preflight, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES
    if not math.isfinite(args.timeout_seconds) or not 0.001 <= args.timeout_seconds <= 60:
        raise ValueError('timeout-seconds must be finite, positive and at most 60')
    payload = load_request(args.request)
    preview = preflight(payload, budget_usd=args.budget_usd)
    if not args.execute:
        return preview
    if args.budget_usd is None:
        raise ValueError('Execution requires an explicit --budget-usd')
    if args.budget_usd < preview['cost']['preflight_ceiling_usd']:
        raise ValueError('Execution budget must cover the displayed full-context ceiling')

    from .feedback import preference_status
    from .model_evaluation import import_model_work
    comparison = _slug(args.comparison_id, 'comparison-id')
    work_id = _slug(args.work_id, 'work-id')
    _slug(args.task, 'task')
    for value, label in ((args.prompt_version, 'prompt-version'), (args.rubric_version, 'rubric-version')):
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError(label + ' is required for execution')
    if not args.evidence:
        raise ValueError('Execution requires at least one --evidence file from the selected workspace')
    if args.format == 'both':
        raise ValueError('Choose one --format for this model-work comparison')
    evidence = [_binding(p) for p in args.evidence]
    c = config()
    # Reserve room for request, provider/output receipts and the imported work
    # before any billable request; stored output can appear in several receipts.
    storage_allowance = 8 * MAX_RESPONSE_BYTES + 2 * MAX_REQUEST_BYTES
    ensure_space(storage_allowance, root=ROOT, reserve=c['reserve_bytes'])
    event_identity = {k: c[k] for k in ('id', 'year', 'country_name', 'session_name',
                                       'event_date', 'session_key', 'meeting_key')}
    preferences = preference_status(root=ROOT)
    assets = safe_relative(f'runs/model-evaluations/{comparison}/{work_id}.assets')
    receipt_path = safe_relative(f'runs/model-evaluations/{comparison}/{work_id}.json')
    if assets.exists() or receipt_path.exists():
        raise ValueError('Model-work identifier already exists; do not repeat a possibly billed execution')
    assets.mkdir(parents=True)
    request_path = assets / 'request.json'
    write_json(request_path, payload)
    inputs = [_binding('config/event.json'), _binding(request_path)]
    intent_path = assets / 'intent.json'
    write_json(intent_path, {'event_identity': event_identity, 'task': args.task,
                            'format': args.format, 'inputs': inputs, 'evidence': evidence,
                            'preflight': preview, 'transport_timeout_seconds': args.timeout_seconds,
                            'status': 'execution_requested'})
    result = evaluate(payload, execute=True, budget_usd=args.budget_usd, timeout=args.timeout_seconds)
    provider_path = assets / 'provider-receipt.json'
    write_json(provider_path, result)
    outputs = []
    if result['accepted_model_result']:
        output = assets / 'result.txt'
        output.write_text(result['result']['output_text'], encoding='utf-8')
        outputs = [_binding(output)]
    usage = result.get('usage') or {}
    cost = result.get('cost') or {}
    preference_binding = None
    if preferences.get('version'):
        preference_binding = {
            'version': preferences['version'],
            'record_hashes': {r['id']: r['record_sha256'] for r in preferences['confirmed']},
        }
    record = {
        'schema_version': 'f1.model_work.v1', 'work_id': work_id,
        'comparison_id': comparison, 'task': args.task, 'format': args.format,
        'event_id': c['id'], 'event_identity': event_identity,
        'prompt_version': args.prompt_version, 'rubric_version': args.rubric_version,
        'preference_version': preferences.get('version'), 'preference_binding': preference_binding,
        'inputs': inputs, 'evidence': evidence,
        'attempts': [{
            'attempt_id': 'attempt-1', 'status': 'completed' if outputs else 'failed',
            'model': {
                'provider': result['provider'], 'model': result.get('observed_model'),
                'access': 'hosted_api',
                'identity_source': 'observed' if result.get('observed_model') else 'unknown',
                'settings': {**result['effective_settings'],
                             'catalog_canonical_slug': result.get('catalog_canonical_slug'),
                             'transport_timeout_seconds': args.timeout_seconds,
                             'observed_serving_provider': result.get('observed_serving_provider')},
                'session_reference': result.get('observed_generation_id'), 'revision': None, 'quantization': None,
            },
            'outputs': outputs,
            'usage': {
                'input_tokens': usage.get('input_tokens'), 'output_tokens': usage.get('output_tokens'),
                'reasoning_tokens': usage.get('reasoning_tokens'), 'token_scope': 'attributable' if usage else 'unknown',
                'cost_usd': cost.get('actual_billing_usd'),
                'estimated_cost_usd': cost.get('usage_rate_estimate_usd'),
                'cost_source': 'provider_receipt' if cost.get('actual_billing_usd') is not None else 'unknown',
                'machine_seconds': result.get('elapsed_seconds'), 'human_revision_seconds': None,
            },
            'eligibility': {'status': 'not_reviewed', 'failures': [], 'review_files': []},
            'error': None if outputs else result.get('error', {}).get('code', 'provider_failed'),
            'provenance': [_binding(request_path), _binding(provider_path)],
        }],
    }
    import_path = assets / 'model-work-import.json'
    write_json(import_path, record)
    imported = import_model_work(import_path, root=ROOT)
    return {'provider_result': result, 'model_work': imported}


def run(args):
    from .core import ROOT
    if args.execute and args.command not in ('model-infer', 'jev-infer', 'model-run'):
        raise ValueError('--execute is only supported by explicit model execution commands')
    if args.command == 'model-run':
        from .model_jobs import run_plan
        return run_plan(args)
    if args.command == 'model-review':
        from .model_jobs import review_plan
        return review_plan(args.request)
    if args.command in ('feedback-record', 'preference-record', 'feedback-status', 'preference-status'):
        from .feedback import record_feedback, record_preference, feedback_status, preference_status
        if args.command == 'feedback-record':
            return record_feedback(load_request(args.request), root=ROOT)
        if args.command == 'preference-record':
            return record_preference(load_request(args.request), root=ROOT)
        if args.command == 'feedback-status':
            return feedback_status(root=ROOT, write_view=True)
        return preference_status(root=ROOT)
    if args.command in ('model-import', 'model-route', 'model-evaluate'):
        from .model_evaluation import import_model_work, route_advice, evaluation_report
        if args.command == 'model-import':
            load_request(args.request)
            return import_model_work(args.request, root=ROOT)
        if args.command == 'model-route':
            return route_advice(args.task, subscription_status=args.subscription_status, root=ROOT)
        return evaluation_report(comparison_id=args.comparison_id, root=ROOT)
    if args.command in ('model-infer', 'jev-infer'):
        return _hosted_work(args)
    raise ValueError('Unknown model-work command')
