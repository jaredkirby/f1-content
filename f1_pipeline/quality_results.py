"""Offline categorical results, bound to a frozen sample and native Jev work.

Human labels are explicit operator declarations, not authenticated identities.
No inference, calibration, film acceptance or model promotion occurs here.
"""
from __future__ import annotations

from collections import Counter
import json
import os
import re
from pathlib import Path
import tempfile

from . import quality_protocol as protocol

COMMANDS = ('quality-results-preview', 'quality-results-save', 'quality-results-report')
SCHEMA = 'f1.quality_results.v1'
RECEIPT_SCHEMA = 'f1.quality_results_receipt.v1'
MAX_ASSESSMENTS = 1000


def _native_attempt(work, attempt_id, root):
    """Require the one native CLI attempt's canonical request/provider/output."""
    from .core import safe_relative
    from . import jev_inference as jev
    from .jev_adapter import JevError, encode, validate_request, validate_response
    if len(work['attempts']) != 1 or attempt_id != 'attempt-1':
        raise ValueError('This slice requires the single native Jev attempt-1')
    attempt = work['attempts'][0]
    if (attempt['attempt_id'] != attempt_id or attempt['status'] != 'completed'
            or attempt['error'] is not None or attempt['eligibility']['status'] == 'failed'):
        raise ValueError('Evaluation requires a completed nonfailed attempt')
    assets = f"runs/model-evaluations/{work['comparison_id']}/{work['work_id']}.assets/"
    paths = {'request': assets + 'request.json', 'provider': assets + 'provider-receipt.json',
             'output': assets + 'result.txt'}
    outputs = attempt['outputs']
    provenance = {item['path']: item for item in attempt['provenance']}
    inputs = {item['path']: item for item in work['inputs']}
    if (len(outputs) != 1 or outputs[0]['path'] != paths['output']
            or paths['provider'] not in provenance or paths['request'] not in provenance
            or inputs.get(paths['request']) != provenance[paths['request']]):
        raise ValueError('Output and provenance must belong to the same canonical native attempt')
    for item in outputs + attempt['provenance'] + work['inputs'] + work['evidence']:
        protocol._binding(item, root)
    payload = protocol._load(safe_relative(paths['request'], root=root))
    provider = protocol._load(safe_relative(paths['provider'], root=root))
    if not isinstance(provider, dict):
        raise ValueError('Native Jev provider receipt must be an object')
    try:
        validate_request(payload, model=jev.MODEL_ID)
        preview = jev.preflight(payload)
        if (provider.get('schema_version') != 'f1.hosted-inference.v1'
                or provider.get('provider') != 'openrouter' or provider.get('endpoint') != jev.ENDPOINT
                or provider.get('requested_model') != jev.MODEL_ID
                or provider.get('status') != 'succeeded'
                or provider.get('inference_attempted') is not True
                or provider.get('actual_model_inference') is not True
                or provider.get('accepted_model_result') is not True
                or type(provider.get('attempts')) is not int or provider['attempts'] != 1
                or provider.get('request_sha256') != preview['request_sha256']
                or provider.get('request_bytes') != preview['request_bytes']
                or protocol._canonical(provider.get('effective_settings')) != protocol._canonical(preview['effective_settings'])
                or provider.get('catalog_canonical_slug') != jev.CANONICAL_SLUG
                or not isinstance(provider.get('observed_model'), str)
                or provider['observed_model'] not in {jev.MODEL_ID, jev.CANONICAL_SLUG}
                or not (provider.get('observed_serving_provider') is None
                        or isinstance(provider['observed_serving_provider'], str)
                        and provider['observed_serving_provider'] in {'typesafe', 'TypeSafe'})
                or not isinstance(provider.get('response_sha256'), str)
                or not re.fullmatch(r'[a-f0-9]{64}', provider['response_sha256'])):
            raise ValueError('Invalid accepted native Jev provider receipt')
        result = provider.get('result')
        if not isinstance(result, dict):
            raise ValueError('Missing accepted Jev result')
        validate_response({'model': provider['observed_model'], 'usage': provider.get('usage'),
                           'answers': result.get('answers')}, payload,
                          allowed_models={jev.MODEL_ID, jev.CANONICAL_SLUG})
        output = encode(result['answers']).decode('utf-8')
        import hashlib
        output_sha = hashlib.sha256(output.encode('utf-8')).hexdigest()
        if (result.get('output_text') != output or result.get('output_sha256') != output_sha
                or outputs[0]['sha256'] != output_sha
                or safe_relative(paths['output'], root=root).read_bytes() != output.encode('utf-8')):
            raise ValueError('Native Jev output differs from its accepted provider result')
    except JevError as exc:
        raise ValueError(str(exc)) from None
    model = attempt['model']
    settings = model['settings']
    if (model['provider'] != provider['provider'] or model['model'] != provider['observed_model']
            or model['access'] != 'hosted_api' or model['identity_source'] != 'observed'
            or model['revision'] is not None or model['quantization'] is not None
            or model['session_reference'] != provider.get('observed_generation_id')
            or not isinstance(settings, dict)
            or set(settings) != {'provider', 'catalog_canonical_slug', 'transport_timeout_seconds', 'observed_serving_provider'}
            or protocol._canonical(settings['provider']) != protocol._canonical(jev.ROUTING)
            or settings['catalog_canonical_slug'] != provider['catalog_canonical_slug']
            or settings['observed_serving_provider'] != provider.get('observed_serving_provider')
            or not jev.number(settings['transport_timeout_seconds'], 0.001, 300)):
        raise ValueError('Model identity/settings do not match native Jev provenance')
    for key in ('input_tokens', 'output_tokens'):
        if attempt['usage'][key] != provider['usage'][key]:
            raise ValueError('Model work usage differs from native Jev provenance')
    return model, payload, result['answers']


def _evaluate(document, root):
    from .core import safe_relative
    from .model_evaluation import validate_model_work
    protocol._shape(document, {'schema_version', 'evaluation_id', 'protocol_receipt', 'assessments'}, 'evaluation request')
    if document['schema_version'] != SCHEMA:
        raise ValueError('Unsupported quality results schema')
    protocol._slug(document['evaluation_id'], 'evaluation_id')
    binding = document['protocol_receipt']
    protocol._binding(binding, root)
    protocol.check_protocol(binding['path'], root=root)
    frozen = protocol._load(safe_relative(binding['path'], root=root))['protocol']
    cases = {case['case_id']: case for case in frozen['cases']}
    assessments = document['assessments']
    if not isinstance(assessments, list) or not 1 <= len(assessments) <= MAX_ASSESSMENTS:
        raise ValueError('Evaluation needs 1 to 1000 assessments')
    cache, seen, used_predictions, results = {}, set(), set(), []
    for assessment in assessments:
        protocol._shape(assessment, {'case_id', 'model_work', 'attempt_id', 'question_id',
                                    'expected_label', 'human_source'}, 'assessment')
        protocol._slug(assessment['case_id'], 'case_id')
        case = cases.get(assessment['case_id'])
        if case is None:
            raise ValueError('Unknown frozen protocol case_id')
        source = assessment['human_source']
        protocol._shape(source, {'kind', 'reviewer', 'reference'}, 'human_source')
        if source['kind'] != 'human':
            raise ValueError('Expected labels require an explicit human declaration')
        for key in ('reviewer', 'reference'):
            protocol._text(source[key], 'human_source ' + key)
        work_binding = assessment['model_work']
        protocol._binding(work_binding, root)
        protocol._slug(assessment['attempt_id'], 'attempt_id')
        protocol._text(assessment['question_id'], 'question_id')
        prediction_key = (protocol._hash(work_binding), assessment['attempt_id'], assessment['question_id'])
        if prediction_key in used_predictions:
            raise ValueError('Duplicate case assessment or reused native prediction across assessments')
        used_predictions.add(prediction_key)
        cache_key = protocol._hash(work_binding)
        if cache_key not in cache:
            try:
                work = validate_model_work(protocol._load(safe_relative(work_binding['path'], root=root)), root=root)
            except (TypeError, KeyError, AttributeError) as exc:
                raise ValueError('Malformed imported model-work receipt') from exc
            expected_path = f"runs/model-evaluations/{work['comparison_id']}/{work['work_id']}.json"
            if work_binding['path'] != expected_path:
                raise ValueError('Evaluation requires the canonical imported model-work receipt')
            protocol._text(work.get('imported_at'), 'model-work imported_at')
            if (protocol._canonical(work['event_identity']) != protocol._canonical(frozen['event_identity'])
                    or work['rubric_version'] != frozen['rubric']['version']):
                raise ValueError('Model work exact event/rubric differs from frozen protocol')
            cache[cache_key] = work
        work = cache[cache_key]
        required = [binding, {key: frozen['rubric'][key] for key in ('path', 'sha256')}] + case['evidence']
        if any(item not in work['evidence'] for item in required):
            raise ValueError('Model work must bind frozen protocol, rubric and all case evidence')
        model, payload, answers = _native_attempt(work, assessment['attempt_id'], root)
        # Model-work metadata alone cannot establish what the provider judged.
        # Bind association inside the hashed payload actually sent to Jev.
        state = payload['state']
        association = state.get('evaluation_case') if isinstance(state, dict) else None
        expected_association = {'protocol_receipt': binding, 'case_id': case['case_id'],
                                'rubric': frozen['rubric'], 'evidence': case['evidence']}
        if (not isinstance(association, dict) or set(association) != set(expected_association)
                or protocol._canonical(association) != protocol._canonical(expected_association)):
            raise ValueError('Native request transport association differs from exact frozen evaluation case')
        question_id = assessment['question_id']
        protocol._text(question_id, 'question_id')
        question = payload['questions'].get(question_id)
        if question is None or question['type'] != 'choice':
            raise ValueError('Only an existing native Jev choice question can be evaluated')
        expected = assessment['expected_label']
        if not isinstance(expected, str) or expected not in question['criteria']:
            raise ValueError('Expected label is outside the exact native question options')
        domain = {'model': model, 'prompt_version': work['prompt_version'],
                  'rubric': frozen['rubric'], 'question_id': question_id, 'question': question}
        # Serving session identifies the attempt, not a model/settings domain.
        domain['model'] = {key: value for key, value in model.items() if key != 'session_reference'}
        domain_id = protocol._hash(domain)
        key = (case['case_id'], domain_id)
        if key in seen:
            raise ValueError('Duplicate case assessment in the same model/settings/question domain')
        seen.add(key)
        prediction = answers[question_id]['choice']
        results.append({'case_id': case['case_id'], 'split': case['split'],
                        'source_group_ids': case['source_group_ids'], 'domain_id': domain_id,
                        'domain': domain, 'model_work': work_binding,
                        'attempt_id': assessment['attempt_id'], 'expected_label': expected,
                        'prediction': prediction, 'correct': expected == prediction, 'human_source': source})
    return frozen, results


def _summary(document, frozen, results, status):
    groups = {}
    totals = Counter(case['split'] for case in frozen['cases'])
    for row in results:
        for split in ('development', 'held_out'):
            groups.setdefault((split, row['domain_id']), {'split': split, 'domain_id': row['domain_id'],
                'domain': row['domain'], 'assessed_cases': [], 'confusion': Counter(), 'correct': 0})
        key = (row['split'], row['domain_id'])
        group = groups.setdefault(key, {'split': row['split'], 'domain_id': row['domain_id'],
            'domain': row['domain'], 'assessed_cases': [], 'confusion': Counter(), 'correct': 0})
        group['assessed_cases'].append(row['case_id'])
        group['confusion'][(row['expected_label'], row['prediction'])] += 1
        group['correct'] += row['correct']
    for group in groups.values():
        count = len(group['assessed_cases'])
        group['assessed_cases'].sort()
        group.update(count=count, incorrect=count-group['correct'],
                     accuracy=group['correct']/count if count else None,
                     protocol_split_cases=totals[group['split']],
                     missing_case_ids=sorted(case['case_id'] for case in frozen['cases']
                        if case['split'] == group['split'] and case['case_id'] not in group['assessed_cases']),
                     coverage='complete' if count == totals[group['split']] else 'partial')
        group['confusion'] = [{'expected': expected, 'predicted': predicted, 'count': number}
                              for (expected, predicted), number in sorted(group['confusion'].items())]
    assessed = {row['case_id'] for row in results}
    return {'schema_version': 'f1.quality_results_status.v1', 'evaluation_id': document['evaluation_id'],
            'event_identity': frozen['event_identity'], 'protocol_id': frozen['protocol_id'], 'status': status,
            'assessments': results, 'groups': [groups[key] for key in sorted(groups)],
            'unassessed_case_ids': sorted(set(case['case_id'] for case in frozen['cases']) - assessed),
            'provider_calls': False, 'human_labels': 'operator_declared_not_authenticated',
            'human_acceptance': 'not_inferred', 'quality_parity': 'not_established',
            'calibration': 'not_established', 'model_promotion': False}


def _preview(request, root):
    from .core import digest
    path = protocol._request_path(request, root)
    binding = {'path': path.relative_to(root).as_posix(), 'sha256': digest(path)}
    document = protocol._load(path)
    frozen, results = _evaluate(document, root)
    protocol._binding(binding, root)
    return document, frozen, results, binding


def preview_results(request, *, root=None):
    root, _, _ = protocol._workspace(root)
    document, frozen, results, binding = _preview(request, root)
    return {**_summary(document, frozen, results, 'validated_preview'),
            'request_binding': binding, 'writes_performed': False}


def save_results(request, *, root=None):
    from .core import digest, ensure_space, now, safe_relative
    root, config, _ = protocol._workspace(root)
    document, frozen, results, binding = _preview(request, root)
    receipt = {'schema_version': RECEIPT_SCHEMA, 'saved_at': now(), 'request': document,
               'request_binding': binding, 'resolved_assessments': results}
    receipt['record_sha256'] = protocol._hash(receipt)
    encoded = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n'
    if len(encoded.encode('utf-8')) > protocol.MAX_DOCUMENT_BYTES:
        raise ValueError('Evaluation receipt exceeds bounded document size')
    relative = 'runs/quality-results/' + document['evaluation_id'] + '.json'
    target = safe_relative(relative, root=root)
    if target.relative_to(root).as_posix() != relative:
        raise ValueError('Evaluation receipts require canonical paths without symlink aliases')
    if target.exists():
        raise ValueError('Evaluation identifier already saved; corrections require a new evaluation_id')
    ensure_space(len(encoded.encode('utf-8')), root=root, reserve=config['reserve_bytes'])
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        current = _preview(request, root)
        if protocol._canonical(current) != protocol._canonical((document, frozen, results, binding)):
            raise ValueError('Evaluation evidence changed before publication')
        try:
            os.link(temporary, target)
        except FileExistsError:
            raise ValueError('Evaluation identifier already saved; use a new evaluation_id') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {**_summary(document, frozen, results, 'saved'), 'receipt_path': relative,
            'sha256': digest(target), 'record_sha256': receipt['record_sha256']}


def report_results(request, *, root=None):
    from .core import digest, safe_relative
    root, _, _ = protocol._workspace(root)
    path = protocol._request_path(request, root)
    receipt = protocol._load(path)
    protocol._shape(receipt, {'schema_version', 'saved_at', 'request', 'request_binding',
                              'resolved_assessments', 'record_sha256'}, 'evaluation receipt')
    if receipt['schema_version'] != RECEIPT_SCHEMA:
        raise ValueError('Unsupported quality results receipt')
    protocol._text(receipt['saved_at'], 'saved_at')
    if receipt['record_sha256'] != protocol._hash({key: value for key, value in receipt.items() if key != 'record_sha256'}):
        raise ValueError('Corrupt evaluation receipt hash')
    protocol._binding(receipt['request_binding'], root)
    original = protocol._load(safe_relative(receipt['request_binding']['path'], root=root))
    if protocol._canonical(original) != protocol._canonical(receipt['request']):
        raise ValueError('Evaluation differs from its bound original request')
    frozen, results = _evaluate(original, root)
    if protocol._canonical(results) != protocol._canonical(receipt['resolved_assessments']):
        raise ValueError('Evaluation predictions differ from current validated evidence')
    expected_path = 'runs/quality-results/' + original['evaluation_id'] + '.json'
    if path.relative_to(root).as_posix() != expected_path:
        raise ValueError('Report requires canonical saved evaluation receipt')
    return {**_summary(original, frozen, results, 'current_evaluation'),
            'receipt_path': expected_path, 'sha256': digest(path), 'writes_performed': False}


def run(args):
    from .core import ROOT
    if getattr(args, 'execute', False):
        raise ValueError('Quality results commands cannot execute inference')
    action = dict(zip(COMMANDS, (preview_results, save_results, report_results))).get(args.command)
    if action is None:
        raise ValueError('Unknown quality results command')
    return action(args.request, root=ROOT)
