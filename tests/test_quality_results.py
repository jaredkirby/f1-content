"""Synthetic, no-network source-bound categorical evaluation regressions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from f1_pipeline import jev_inference
from f1_pipeline.jev_adapter import encode
from f1_pipeline.model_evaluation import import_model_work
from f1_pipeline.quality_protocol import freeze_protocol
from f1_pipeline.quality_results import preview_results, save_results, report_results, run


def write(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding='utf-8')
    return {'path': path, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def binding(root, path):
    return {'path': path, 'sha256': hashlib.sha256((root / path).read_bytes()).hexdigest()}


def native_work(root, identity, frozen_binding, rubric, case, index):
    work_id, comparison = 'work-' + str(index), 'fictional-pilot'
    assets = f'runs/model-evaluations/{comparison}/{work_id}.assets/'
    payload = {'model': jev_inference.MODEL_ID,
               'state': {'case_id': case['case_id'], 'evidence': case['evidence'],
                         'evaluation_case': {'protocol_receipt': frozen_binding, 'case_id': case['case_id'],
                                             'rubric': rubric, 'evidence': case['evidence']}},
               'questions': {'grounding': {'type': 'choice', 'instructions': 'Fictional binary grounding rubric.',
                                         'criteria': {'supported': 'Supported by fictional evidence.',
                                                      'unsupported': 'Not supported by fictional evidence.'}}}}
    request = write(root, assets + 'request.json', payload)
    answers = {'grounding': {'type': 'choice', 'choice': 'supported', 'confidence': 0.8,
                            'probabilities': {'supported': 0.8, 'unsupported': 0.2}}}
    output = encode(answers).decode('utf-8')
    output_binding = write(root, assets + 'result.txt', output)
    provider = jev_inference.preflight(payload)
    provider.update(status='succeeded', inference_attempted=True, actual_model_inference=True,
                    accepted_model_result=True, attempts=1, observed_model=jev_inference.CANONICAL_SLUG,
                    observed_generation_id='fictional-generation-' + str(index),
                    observed_serving_provider='TypeSafe', response_sha256='a' * 64,
                    usage={'input_tokens': 10, 'output_tokens': 5},
                    result={'answers': answers, 'output_text': output, 'output_sha256': output_binding['sha256']})
    provider_binding = write(root, assets + 'provider-receipt.json', provider)
    model = {'provider': 'openrouter', 'model': provider['observed_model'], 'access': 'hosted_api',
             'identity_source': 'observed', 'revision': None, 'quantization': None,
             'session_reference': provider['observed_generation_id'],
             'settings': {**provider['effective_settings'], 'catalog_canonical_slug': provider['catalog_canonical_slug'],
                          'transport_timeout_seconds': 20, 'observed_serving_provider': 'TypeSafe'}}
    usage = {'input_tokens': 10, 'output_tokens': 5, 'reasoning_tokens': None, 'token_scope': 'attributable',
             'cost_usd': None, 'estimated_cost_usd': None, 'cost_source': 'unknown',
             'machine_seconds': None, 'human_revision_seconds': None}
    record = {'schema_version': 'f1.model_work.v1', 'work_id': work_id, 'comparison_id': comparison,
              'task': 'claim_judgment', 'format': 'text', 'event_id': identity['id'], 'event_identity': identity,
              'prompt_version': 'fixture-v1', 'rubric_version': rubric['version'],
              'preference_version': None, 'preference_binding': None,
              'inputs': [binding(root, 'config/event.json'), request],
              'evidence': [frozen_binding, {key: rubric[key] for key in ('path', 'sha256')}] + case['evidence'],
              'attempts': [{'attempt_id': 'attempt-1', 'status': 'completed', 'error': None,
                            'model': model, 'outputs': [output_binding], 'provenance': [request, provider_binding],
                            'usage': usage, 'eligibility': {'status': 'not_reviewed', 'failures': [], 'review_files': []}}]}
    import_path = write(root, assets + 'model-work-import.json', record)['path']
    saved = import_model_work(import_path, root=root)
    return {'path': saved['receipt_path'], 'sha256': saved['sha256']}


def fixture(root):
    """Return valid request dict; write it as evaluation.json for CLI/wheel reuse."""
    identity = {'id': 'synthetic-session', 'year': 2026, 'country_name': 'Example',
                'session_name': 'Qualifying', 'event_date': '2026-10-10', 'session_key': 999999,
                'meeting_key': 999999}
    write(root, 'config/event.json', {**identity, 'reserve_bytes': 1})
    rubric = {**write(root, 'research/rubric.txt', 'Fictional binary rubric, not a real human review.'),
              'version': 'fixture-v1'}
    protocol = {'schema_version': 'f1.quality_protocol.v1', 'protocol_id': 'sample-1',
                'event_identity': identity, 'rubric': rubric,
                'split_assignment': {'kind': 'operator_declared', 'reference': 'Fictional fixture split'},
                'cases': [{'case_id': 'development', 'split': 'development', 'source_group_ids': ['one'],
                           'evidence': [write(root, 'research/dev.txt', 'Fictional development data.')]},
                          {'case_id': 'held-out', 'split': 'held_out', 'source_group_ids': ['two'],
                           'evidence': [write(root, 'research/held.txt', 'Fictional held-out data.')]},
                          {'case_id': 'unassessed', 'split': 'held_out', 'source_group_ids': ['three'],
                           'evidence': [write(root, 'research/unassessed.txt', 'Fictional third data.')]}]}
    write(root, 'protocol.json', protocol)
    frozen = freeze_protocol('protocol.json', root=root)
    frozen_binding = {'path': frozen['receipt_path'], 'sha256': frozen['sha256']}
    assessments = []
    for index, case in enumerate(protocol['cases'][:2]):
        work = native_work(root, identity, frozen_binding, rubric, case, index)
        assessments.append({'case_id': case['case_id'], 'model_work': work, 'attempt_id': 'attempt-1',
                            'question_id': 'grounding', 'expected_label': 'supported' if index == 0 else 'unsupported',
                            'human_source': {'kind': 'human', 'reviewer': 'Fictional test reviewer',
                                             'reference': 'Synthetic label declaration, not real human evidence'}})
    request = {'schema_version': 'f1.quality_results.v1', 'evaluation_id': 'fictional-evaluation',
               'protocol_receipt': frozen_binding, 'assessments': assessments}
    write(root, 'evaluation.json', request)
    return request


class QualityResults(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.request = fixture(self.root)

    def preview(self):
        write(self.root, 'evaluation.json', self.request)
        return preview_results('evaluation.json', root=self.root)

    def work(self, index=0):
        path = self.request['assessments'][index]['model_work']['path']
        return json.loads((self.root / path).read_text())

    def rewrite_work(self, work, index=0):
        path = self.request['assessments'][index]['model_work']['path']
        self.request['assessments'][index]['model_work'] = write(self.root, path, work)

    def rewrite_provider(self, edit, index=0):
        work = self.work(index)
        path = work['attempts'][0]['provenance'][1]['path']
        provider = json.loads((self.root / path).read_text())
        edit(provider)
        work['attempts'][0]['provenance'][1] = write(self.root, path, provider)
        self.rewrite_work(work, index)

    def test_independent_labels_raw_confusion_split_and_partial_coverage_without_calls(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('socket.create_connection', side_effect=AssertionError('No network')), \
             patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network')), \
             patch('f1_pipeline.credentials.resolve_api_key', side_effect=AssertionError('No credentials')):
            result = preview_results('evaluation.json', root=self.root)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        development, held = result['groups']
        self.assertEqual((development['count'], development['correct'], development['accuracy']), (1, 1, 1))
        self.assertEqual((held['count'], held['incorrect'], held['accuracy']), (1, 1, 0))
        self.assertEqual(held['confusion'], [{'expected': 'unsupported', 'predicted': 'supported', 'count': 1}])
        self.assertEqual(held['missing_case_ids'], ['unassessed'])
        self.assertEqual(held['coverage'], 'partial')
        self.assertEqual(result['unassessed_case_ids'], ['unassessed'])
        self.assertEqual(result['human_acceptance'], 'not_inferred')
        self.assertFalse(result['provider_calls'])
        self.assertFalse(result['model_promotion'])

    def test_save_report_exclusive_snapshot_and_new_identifier_correction(self):
        saved = save_results('evaluation.json', root=self.root)
        path = self.root / saved['receipt_path']
        before = path.read_bytes()
        self.assertEqual(report_results(saved['receipt_path'], root=self.root)['status'], 'current_evaluation')
        with self.assertRaisesRegex(ValueError, 'already saved'):
            save_results('evaluation.json', root=self.root)
        self.assertEqual(before, path.read_bytes())
        self.request['evaluation_id'] = 'corrected-evaluation'
        self.request['assessments'][1]['expected_label'] = 'supported'
        write(self.root, 'correction.json', self.request)
        other = save_results('correction.json', root=self.root)
        self.assertNotEqual(saved['receipt_path'], other['receipt_path'])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(report_results(saved['receipt_path'], root=self.root)['groups'][1]['accuracy'], 0)

    def test_changed_original_request_invalidates_saved_report(self):
        saved = save_results('evaluation.json', root=self.root)
        self.request['assessments'][0]['expected_label'] = 'unsupported'
        write(self.root, 'evaluation.json', self.request)
        with self.assertRaisesRegex(ValueError, 'Stale or missing'):
            report_results(saved['receipt_path'], root=self.root)

    def test_current_protocol_and_all_work_bindings_required(self):
        for path in ('research/dev.txt', 'research/rubric.txt', 'protocol.json',
                     'runs/model-evaluations/fictional-pilot/work-0.assets/result.txt'):
            with self.subTest(path=path):
                original = (self.root / path).read_bytes()
                (self.root / path).write_text('Changed')
                with self.assertRaises(ValueError):
                    preview_results('evaluation.json', root=self.root)
                (self.root / path).write_bytes(original)

    def test_cross_event_bool_identity_and_rubric_mismatches_refused(self):
        original = self.work()
        for field, value in (('session_key', True), ('session_name', 'Sprint')):
            work = deepcopy(original)
            work['event_identity'][field] = value
            self.rewrite_work(work)
            with self.assertRaisesRegex(ValueError, 'identity'):
                self.preview()
        work = deepcopy(original)
        work['rubric_version'] = 'other-rubric'
        self.rewrite_work(work)
        with self.assertRaisesRegex(ValueError, 'rubric'):
            self.preview()

    def test_unrelated_work_cannot_be_attributed_by_the_caller(self):
        original = self.work()
        for remove in range(3):
            work = deepcopy(original)
            del work['evidence'][remove]
            self.rewrite_work(work)
            with self.assertRaisesRegex(ValueError, 'must bind frozen protocol'):
                self.preview()

    def test_metadata_only_cross_case_reassignment_cannot_turn_development_work_into_held_out(self):
        protocol = json.loads((self.root / 'protocol.json').read_text())
        work = self.work()
        work['evidence'].extend(protocol['cases'][1]['evidence'])
        self.rewrite_work(work)
        self.request['assessments'] = [deepcopy(self.request['assessments'][0])]
        self.request['assessments'][0]['case_id'] = 'held-out'
        with self.assertRaisesRegex(ValueError, 'transport association'):
            self.preview()

    def test_missing_incomplete_or_changed_transport_association_is_refused(self):
        original = self.work()
        req_path = original['inputs'][1]['path']
        provider_path = original['attempts'][0]['provenance'][1]['path']
        original_payload = json.loads((self.root / req_path).read_text())
        original_provider = json.loads((self.root / provider_path).read_text())
        variants = [None, {}, {**original_payload['state']['evaluation_case'], 'case_id': 'held-out'},
                    {**original_payload['state']['evaluation_case'], 'extra': 'Unsupported'},
                    {**original_payload['state']['evaluation_case'], 'protocol_receipt': {'path': 'other', 'sha256': 'a' * 64}},
                    {**original_payload['state']['evaluation_case'], 'evidence': []},
                    {**original_payload['state']['evaluation_case'], 'rubric': {'version': 'other'}}]
        for association in variants:
            work, payload, provider = deepcopy(original), deepcopy(original_payload), deepcopy(original_provider)
            if association is None:
                del payload['state']['evaluation_case']
            else:
                payload['state']['evaluation_case'] = association
            req_binding = write(self.root, req_path, payload)
            provider.update({key: jev_inference.preflight(payload)[key] for key in ('request_sha256', 'request_bytes')})
            work['inputs'][1] = req_binding
            work['attempts'][0]['provenance'] = [req_binding, write(self.root, provider_path, provider)]
            self.rewrite_work(work)
            with self.subTest(association=association), self.assertRaisesRegex(ValueError, 'transport association'):
                self.preview()

    def test_one_native_answer_cannot_be_reused_across_cases(self):
        protocol = json.loads((self.root / 'protocol.json').read_text())
        work = self.work()
        work['evidence'].extend(protocol['cases'][1]['evidence'])
        self.rewrite_work(work)
        self.request['assessments'][1]['model_work'] = deepcopy(self.request['assessments'][0]['model_work'])
        self.request['assessments'][1]['expected_label'] = 'supported'
        with self.assertRaisesRegex(ValueError, 'reused native prediction'):
            self.preview()

    def test_unknown_cases_invalid_labels_duplicates_and_extra_prediction_refused(self):
        original = deepcopy(self.request)
        for field, value in (('case_id', 'other-case'), ('expected_label', 'maybe'), ('prediction', 'unsupported')):
            self.request = deepcopy(original)
            self.request['assessments'][0][field] = value
            with self.assertRaises(ValueError):
                self.preview()
        self.request = deepcopy(original)
        self.request['assessments'].append(deepcopy(self.request['assessments'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate case assessment'):
            self.preview()

    def test_explicit_human_source_and_bounded_assessments_required(self):
        original = deepcopy(self.request)
        for source in ({'kind': 'model', 'reviewer': 'AI', 'reference': 'Automatic'},
                       {'kind': 'human', 'reviewer': '', 'reference': 'Unknown'}):
            self.request = deepcopy(original)
            self.request['assessments'][0]['human_source'] = source
            with self.assertRaises(ValueError):
                self.preview()
        self.request = deepcopy(original)
        self.request['assessments'] *= 501
        with self.assertRaisesRegex(ValueError, '1 to 1000'):
            self.preview()

    def test_failed_or_unaccepted_provider_and_completed_attempt_fail_closed(self):
        original = self.work()
        provider_path = original['attempts'][0]['provenance'][1]['path']
        provider_bytes = (self.root / provider_path).read_bytes()
        for key, value in (('status', 'failed'), ('accepted_model_result', False),
                           ('actual_model_inference', False), ('request_sha256', 'f' * 64)):
            self.rewrite_work(deepcopy(original))
            (self.root / provider_path).write_bytes(provider_bytes)
            self.rewrite_provider(lambda record: record.update({key: value}))
            with self.assertRaisesRegex(ValueError, 'provider receipt'):
                self.preview()
        (self.root / provider_path).write_bytes(provider_bytes)
        work = deepcopy(original)
        work['attempts'][0].update(status='failed', error='provider_failed')
        self.rewrite_work(work)
        with self.assertRaisesRegex(ValueError, 'completed'):
            self.preview()

    def test_malformed_provider_fields_and_model_work_fail_without_type_tracebacks(self):
        original = self.work()
        provider_path = original['attempts'][0]['provenance'][1]['path']
        provider_bytes = (self.root / provider_path).read_bytes()
        for key, value in (('observed_model', []), ('observed_serving_provider', {}),
                           ('attempts', True), ('attempts', 1.0), ('response_sha256', [])):
            self.rewrite_work(deepcopy(original))
            (self.root / provider_path).write_bytes(provider_bytes)
            self.rewrite_provider(lambda record: record.update({key: value}))
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.preview()
        work = deepcopy(original)
        work['attempts'][0]['provenance'][1] = write(self.root, provider_path, [])
        self.rewrite_work(work)
        with self.assertRaisesRegex(ValueError, 'must be an object'):
            self.preview()
        (self.root / provider_path).write_bytes(provider_bytes)
        work = deepcopy(original)
        work['format'] = []
        self.rewrite_work(work)
        with self.assertRaisesRegex(ValueError, 'Malformed imported'):
            self.preview()

    def test_changed_output_with_updated_binding_still_cannot_disagree_with_provider(self):
        work = self.work()
        work['attempts'][0]['outputs'][0] = write(self.root, work['attempts'][0]['outputs'][0]['path'], '{}')
        self.rewrite_work(work)
        with self.assertRaisesRegex(ValueError, 'output differs'):
            self.preview()

    def test_cross_attempt_output_provider_and_copied_work_path_refused(self):
        original = self.work()
        other = self.work(1)
        for key in ('outputs', 'provenance'):
            work = deepcopy(original)
            work['attempts'][0][key] = other['attempts'][0][key]
            self.rewrite_work(work)
            with self.assertRaisesRegex(ValueError, 'canonical native attempt'):
                self.preview()
        self.rewrite_work(deepcopy(original))
        self.request['assessments'][0]['model_work'] = write(self.root, 'copied-work.json', original)
        with self.assertRaisesRegex(ValueError, 'canonical imported'):
            self.preview()

    def test_duplicate_case_with_independent_work_in_same_domain_is_not_an_extra_sample(self):
        protocol = json.loads((self.root / 'protocol.json').read_text())
        other_binding = native_work(self.root, protocol['event_identity'], self.request['protocol_receipt'],
                                    protocol['rubric'], protocol['cases'][0], 2)
        other = deepcopy(self.request['assessments'][0])
        other['model_work'] = other_binding
        self.request['assessments'].append(other)
        with self.assertRaisesRegex(ValueError, 'Duplicate case assessment'):
            self.preview()

    def test_saved_report_rechecks_work_and_refuses_moved_receipt(self):
        saved = save_results('evaluation.json', root=self.root)
        copy = write(self.root, 'copied-evaluation.json', json.loads((self.root / saved['receipt_path']).read_text()))
        with self.assertRaisesRegex(ValueError, 'canonical saved'):
            report_results(copy['path'], root=self.root)
        work_path = self.request['assessments'][0]['model_work']['path']
        write(self.root, work_path, self.work())
        # A harmless byte-level serialization change also invalidates the binding.
        with (self.root / work_path).open('a') as handle:
            handle.write('\n')
        with self.assertRaisesRegex(ValueError, 'Stale or missing'):
            report_results(saved['receipt_path'], root=self.root)

    def test_question_score_and_noul_refused_even_when_native_response_valid(self):
        # Change both request and accepted result coherently, preserving provider
        # request hash and work bindings; the evaluation slice must still refuse.
        for kind in ('score', 'noul'):
            work = self.work()
            req_path = work['inputs'][1]['path']
            provider_path = work['attempts'][0]['provenance'][1]['path']
            payload = json.loads((self.root / req_path).read_text())
            payload['questions']['grounding'] = {'type': kind, 'instructions': 'Synthetic rubric',
                'criteria': ['low', 'high'] if kind == 'score' else None}
            answers = {'grounding': {'type': kind, 'noul': 0.5} if kind == 'noul' else
                       {'type': kind, 'probabilities': {'0': 0.5, '1': 0.5}, 'confidence': 0.5,
                        'legend': {'0': 'low', '1': 'high'}, 'score': 0.5}}
            req_binding = write(self.root, req_path, payload)
            output = encode(answers).decode()
            output_binding = write(self.root, work['attempts'][0]['outputs'][0]['path'], output)
            provider = json.loads((self.root / provider_path).read_text())
            provider.update({key: jev_inference.preflight(payload)[key] for key in ('request_sha256', 'request_bytes')})
            provider['result'] = {'answers': answers, 'output_text': output, 'output_sha256': output_binding['sha256']}
            work['inputs'][1] = req_binding
            work['attempts'][0].update(outputs=[output_binding], provenance=[req_binding, write(self.root, provider_path, provider)])
            self.rewrite_work(work)
            with self.assertRaisesRegex(ValueError, 'choice question'):
                self.preview()

    def test_distinct_exact_settings_and_question_domains_are_not_pooled(self):
        work = self.work(1)
        work['attempts'][0]['model']['settings']['transport_timeout_seconds'] = 30
        self.rewrite_work(work, 1)
        result = self.preview()
        self.assertNotEqual(result['groups'][0]['domain_id'], result['groups'][1]['domain_id'])
        self.assertEqual(len(result['groups']), 4)
        empty = [group for group in result['groups'] if group['count'] == 0]
        self.assertEqual(len(empty), 2)
        self.assertTrue(all(group['accuracy'] is None and group['coverage'] == 'partial' for group in empty))
        # Native questions with changed instructions are a different rubric domain.
        work = self.work(1)
        work['attempts'][0]['model']['settings']['transport_timeout_seconds'] = 20
        req_path = work['inputs'][1]['path']
        payload = json.loads((self.root / req_path).read_text())
        payload['questions']['grounding']['instructions'] = 'Different question wording'
        req_binding = write(self.root, req_path, payload)
        work['inputs'][1] = req_binding
        work['attempts'][0]['provenance'][0] = req_binding
        provider_path = work['attempts'][0]['provenance'][1]['path']
        provider = json.loads((self.root / provider_path).read_text())
        provider.update({key: jev_inference.preflight(payload)[key] for key in ('request_sha256', 'request_bytes')})
        work['attempts'][0]['provenance'][1] = write(self.root, provider_path, provider)
        self.rewrite_work(work, 1)
        result = self.preview()
        self.assertNotEqual(result['groups'][0]['domain_id'], result['groups'][1]['domain_id'])

    def test_publish_rechecks_and_leaves_no_partial_receipt(self):
        def change(_):
            write(self.root, 'research/dev.txt', 'Changed during save')
        with patch('f1_pipeline.quality_results.os.fsync', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'Stale or missing'):
                save_results('evaluation.json', root=self.root)
        self.assertEqual(list((self.root / 'runs/quality-results').iterdir()), [])

    def test_receipt_hash_and_resolved_predictions_rechecked(self):
        saved = save_results('evaluation.json', root=self.root)
        path = self.root / saved['receipt_path']
        original = path.read_bytes()
        receipt = json.loads(original)
        receipt['resolved_assessments'][0]['prediction'] = 'unsupported'
        write(self.root, saved['receipt_path'], receipt)
        with self.assertRaisesRegex(ValueError, 'Corrupt'):
            report_results(saved['receipt_path'], root=self.root)
        from f1_pipeline.quality_protocol import _hash
        receipt['record_sha256'] = _hash({key: value for key, value in receipt.items() if key != 'record_sha256'})
        write(self.root, saved['receipt_path'], receipt)
        with self.assertRaisesRegex(ValueError, 'predictions differ'):
            report_results(saved['receipt_path'], root=self.root)

    def test_symlink_destination_refused_and_execute_is_unsupported(self):
        alternate = self.root / 'alternate'
        alternate.mkdir()
        (self.root / 'runs/quality-results').symlink_to(alternate, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'canonical paths'):
            save_results('evaluation.json', root=self.root)
        self.assertEqual(list(alternate.iterdir()), [])
        with self.assertRaisesRegex(ValueError, 'cannot execute'):
            run(SimpleNamespace(command='quality-results-preview', request='evaluation.json', execute=True))


if __name__ == '__main__':
    unittest.main()
