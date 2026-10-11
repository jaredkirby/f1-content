"""Public CLI/workspace flows; synthetic files and no provider inference."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class ModelWorkflowCLI(unittest.TestCase):
    def invoke(self, root, *args):
        env = dict(os.environ, PYTHONPATH=str(PROJECT), PYTHONDONTWRITEBYTECODE='1')
        env.pop('F1_WORKSPACE', None)
        return subprocess.run(
            [sys.executable, '-B', '-m', 'f1_pipeline', '--workspace', str(root), *args],
            cwd=PROJECT, env=env, capture_output=True, text=True,
        )

    def workspace(self, root):
        (root / 'config').mkdir()
        (root / 'config/event.json').write_text(
            (PROJECT / 'examples/synthetic/config/event.json').read_text()
        )

    def outputs(self, root):
        def artifact(relative, content):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            return hashlib.sha256(content).hexdigest()
        edl = 'outputs/versions/fixture/edit-plan.json'
        edl_sha = artifact(edl, b'{"synthetic":true}')
        videos = []
        for format_name in ('vertical', 'landscape'):
            base = 'outputs/versions/fixture/' + format_name
            paths = {'path': base + '.mp4', 'captions': base + '.srt',
                     'script': base + '.txt', 'thumbnail': base + '.jpg'}
            hashes = {key: artifact(path, ('synthetic ' + format_name + ' ' + key).encode())
                      for key, path in paths.items()}
            videos.append({'format': format_name, **paths, 'sha256': hashes['path'],
                           'companion_sha256': {key: hashes[key] for key in ('captions', 'script', 'thumbnail')},
                           'title': 'Synthetic ' + format_name, 'duration': 1, 'width': 360, 'height': 640})
        manifest = {'event_id': 'synthetic-session', 'run_id': 'fixture', 'videos': videos,
                    'edit_plan': edl, 'edit_plan_sha256': edl_sha}
        (root / 'outputs/manifest.json').write_text(json.dumps(manifest))
        return hashlib.sha256((root / 'outputs/manifest.json').read_bytes()).hexdigest()

    def test_human_approval_is_for_the_exact_reviewed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.workspace(root)
            sha = self.outputs(root)
            request = root / 'feedback-request.json'
            request.write_text(json.dumps({
                'event_id': 'synthetic-session', 'manifest_sha256': sha,
                'source': {'kind': 'human', 'reviewer': 'synthetic test reviewer', 'reference': 'fictional test instruction'},
                'outcome': 'approved', 'comments': 'Clear grounding on the phone.',
                'scope': {'kind': 'output', 'target': sha},
            }))
            recorded = self.invoke(root, 'feedback-record', '--request', str(request))
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            status = self.invoke(root, 'feedback-status')
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)['status'], 'approved')
            (root / 'outputs/versions/fixture/vertical.mp4').write_bytes(b'changed synthetic output')
            changed = self.invoke(root, 'feedback-status')
            self.assertEqual(changed.returncode, 0, changed.stderr)
            self.assertEqual(json.loads(changed.stdout)['status'], 'not_reviewed')
            self.assertFalse(json.loads(changed.stdout)['binding_valid'])

    def test_hosted_request_defaults_to_preview_without_writing_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.workspace(root)
            request = root / 'request.json'
            request.write_text(json.dumps({
                'model': 'openai/gpt-oss-120b',
                'messages': [{'role': 'user', 'content': 'Synthetic evidence only.'}],
                'max_tokens': 64,
            }))
            result = self.invoke(root, 'model-infer', '--request', str(request))
            self.assertEqual(result.returncode, 0, result.stderr)
            preview = json.loads(result.stdout)
            self.assertFalse(preview['inference_attempted'])
            self.assertFalse(preview['accepted_model_result'])
            self.assertEqual(preview['status'], 'preflight')
            self.assertFalse((root / 'runs/model-evaluations').exists())

    def test_subscription_work_and_human_feedback_preserve_unknown_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.workspace(root)
            manifest_sha = self.outputs(root)
            c = json.loads((root / 'config/event.json').read_text())
            def binding(path):
                return {'path': path, 'sha256': hashlib.sha256((root / path).read_bytes()).hexdigest()}
            request = root / 'work-request.json'
            request.write_text(json.dumps({
                'schema_version': 'f1.model_work.v1', 'work_id': 'reference', 'comparison_id': 'pilot',
                'task': 'story_script', 'format': 'vertical', 'event_id': c['id'],
                'event_identity': {k: c[k] for k in ('id', 'year', 'country_name', 'session_name', 'event_date', 'session_key', 'meeting_key')},
                'prompt_version': 'synthetic-v1', 'rubric_version': 'synthetic-review-v1',
                'preference_version': None, 'preference_binding': None,
                'inputs': [binding('config/event.json')], 'evidence': [binding('config/event.json')],
                'attempts': [{
                    'attempt_id': 'first', 'status': 'completed',
                    'model': {'provider': 'OpenAI', 'model': None, 'access': 'chatgpt_subscription',
                              'identity_source': 'unknown', 'settings': None, 'session_reference': None,
                              'revision': None, 'quantization': None},
                    'outputs': [binding('outputs/versions/fixture/vertical.txt')],
                    'usage': {**{k: None for k in ('input_tokens', 'output_tokens', 'reasoning_tokens',
                                                 'cost_usd', 'estimated_cost_usd', 'machine_seconds', 'human_revision_seconds')},
                              'token_scope': 'unknown', 'cost_source': 'unknown'},
                    'eligibility': {'status': 'not_reviewed', 'failures': [], 'review_files': []},
                    'error': None, 'provenance': [],
                }],
            }))
            imported = self.invoke(root, 'model-import', '--request', str(request))
            self.assertEqual(imported.returncode, 0, imported.stderr)
            receipt = json.loads(imported.stdout)
            feedback = root / 'feedback-request.json'
            feedback.write_text(json.dumps({
                'event_id': c['id'], 'manifest_sha256': manifest_sha,
                'source': {'kind': 'human', 'reviewer': 'synthetic reviewer', 'reference': 'fictional test feedback'},
                'outcome': 'approved', 'comments': 'Clear grounding on my phone.',
                'scope': {'kind': 'output', 'target': manifest_sha},
                'model_runs': [{'path': receipt['receipt_path'], 'sha256': receipt['sha256']}],
            }))
            approved = self.invoke(root, 'feedback-record', '--request', str(feedback))
            self.assertEqual(approved.returncode, 0, approved.stderr)
            report = self.invoke(root, 'model-evaluate', '--comparison-id', 'pilot')
            self.assertEqual(report.returncode, 0, report.stderr)
            data = json.loads(report.stdout)
            self.assertEqual(data['quality']['human_approved_outputs'], 1)
            self.assertIsNone(data['measurements']['actual_total_cost_usd'])
            self.assertIsNone(data['measurements']['cost_per_accepted_output_usd'])
            self.assertEqual(data['measurements']['unknown_cost_attempts'], 1)

    def test_explicit_hosted_work_saves_output_and_provider_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.workspace(root)
            request = root / 'hosted-request.json'
            request.write_text(json.dumps({'model': 'openai/gpt-oss-120b',
                'messages': [{'role': 'user', 'content': 'Synthetic request only.'}], 'max_tokens': 64}))
            script = '''
import io, json, sys
from unittest.mock import patch
class Response:
    status = 200
    def getcode(self): return 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def geturl(self): return 'https://api.deepinfra.com/v1/openai/chat/completions'
    def read(self, limit):
        return json.dumps({'object':'chat.completion','model':'openai/gpt-oss-120b', 'choices':[{'index':0,
            'message':{'role':'assistant','content':'Synthetic generated text.'}, 'finish_reason':'stop'}],
            'usage':{'prompt_tokens':8,'completion_tokens':2,'total_tokens':10,'estimated_cost':0.000001}}).encode()
class Transport:
    def open(self, request, timeout):
        assert request.full_url == 'https://api.deepinfra.com/v1/openai/chat/completions'
        return Response()
with patch('urllib.request.build_opener', return_value=Transport()):
    from f1_pipeline.cli import main
    raise SystemExit(main(sys.argv[1:]))
'''
            env = dict(os.environ, PYTHONPATH=str(PROJECT), PYTHONDONTWRITEBYTECODE='1',
                       DEEPINFRA_API_KEY='synthetic-test-key')
            env.pop('F1_WORKSPACE', None)
            result = subprocess.run([sys.executable, '-B', '-c', script, '--workspace', str(root),
                'model-infer', '--request', str(request), '--execute', '--budget-usd', '0.01',
                '--comparison-id', 'pilot', '--work-id', 'hosted', '--format', 'vertical',
                '--prompt-version', 'synthetic-v1', '--rubric-version', 'human-review-v1',
                '--evidence', 'config/event.json'], cwd=PROJECT, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            data = json.loads(result.stdout)
            self.assertEqual(data['provider_result']['status'], 'succeeded')
            work = data['model_work']['record']
            attempt = work['attempts'][0]
            self.assertEqual(attempt['model']['model'], 'openai/gpt-oss-120b')
            self.assertEqual(attempt['usage']['input_tokens'], 8)
            self.assertIsNone(attempt['usage']['cost_usd'])
            self.assertEqual(attempt['usage']['estimated_cost_usd'], 0.000001)
            self.assertEqual(attempt['eligibility']['status'], 'not_reviewed')
            report = self.invoke(root, 'model-evaluate', '--comparison-id', 'pilot')
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertEqual(json.loads(report.stdout)['quality']['human_approved_outputs'], 0)
            # The same public flow must retain a failed request with valid usage
            # when the synthetic provider omits a usable model identity.
            bad_script = script.replace("'model':'openai/gpt-oss-120b'", "'model':''")
            failed = subprocess.run([sys.executable, '-B', '-c', bad_script, '--workspace', str(root),
                'model-infer', '--request', str(request), '--execute', '--budget-usd', '0.01',
                '--comparison-id', 'pilot', '--work-id', 'invalid-identity', '--format', 'vertical',
                '--prompt-version', 'synthetic-v1', '--rubric-version', 'human-review-v1',
                '--evidence', 'config/event.json'], cwd=PROJECT, env=env, text=True, capture_output=True)
            self.assertEqual(failed.returncode, 2, failed.stderr)
            self.assertTrue(failed.stdout, failed.stderr)
            attempted = json.loads(failed.stdout)['model_work']['record']['attempts'][0]
            self.assertEqual(attempted['status'], 'failed')
            self.assertIsNone(attempted['model']['model'])
            self.assertEqual(attempted['usage']['input_tokens'], 8)
            report = self.invoke(root, 'model-evaluate', '--comparison-id', 'pilot')
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertEqual(json.loads(report.stdout)['attempt_count'], 2)
            self.assertIsNone(json.loads(report.stdout)['measurements']['actual_total_cost_usd'])

    def test_local_report_shows_current_human_review_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.workspace(root)
            sha = self.outputs(root)
            processed = root / 'data/processed'
            processed.mkdir(parents=True)
            (processed / 'catalog.json').write_text(json.dumps({'sources': [], 'assets': []}))
            (processed / 'editorial.json').write_text(json.dumps({'timeline': [], 'ideas': [], 'sources': []}))
            request = root / 'feedback-request.json'
            request.write_text(json.dumps({
                'event_id': 'synthetic-session', 'manifest_sha256': sha,
                'source': {'kind': 'human', 'reviewer': 'synthetic reviewer', 'reference': 'fictional test feedback'},
                'outcome': 'approved', 'comments': 'Clear grounding.',
                'scope': {'kind': 'output', 'target': sha},
            }))
            recorded = self.invoke(root, 'feedback-record', '--request', str(request))
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            rendered = self.invoke(root, 'report')
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn('Human review: approved', (root / 'outputs/index.html').read_text())
            (root / 'outputs/versions/fixture/vertical.txt').write_bytes(b'changed synthetic narration')
            rendered = self.invoke(root, 'report')
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn('Human review: not reviewed', (root / 'outputs/index.html').read_text())

    def test_disk_reserve_is_checked_before_any_hosted_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.workspace(root)
            request = root / 'hosted-request.json'
            request.write_text(json.dumps({'model': 'openai/gpt-oss-120b',
                'messages': [{'role': 'user', 'content': 'Synthetic request only.'}], 'max_tokens': 64}))
            script = '''
import sys
from types import SimpleNamespace
from unittest.mock import patch
with patch('shutil.disk_usage', return_value=SimpleNamespace(free=1)), \\
     patch('urllib.request.build_opener', side_effect=AssertionError('Provider must not be contacted')):
    from f1_pipeline.cli import main
    raise SystemExit(main(sys.argv[1:]))
'''
            env = dict(os.environ, PYTHONPATH=str(PROJECT), PYTHONDONTWRITEBYTECODE='1',
                       DEEPINFRA_API_KEY='synthetic-test-key')
            env.pop('F1_WORKSPACE', None)
            result = subprocess.run([sys.executable, '-B', '-c', script, '--workspace', str(root),
                'model-infer', '--request', str(request), '--execute', '--budget-usd', '0.01',
                '--comparison-id', 'pilot', '--work-id', 'reserve', '--format', 'vertical',
                '--prompt-version', 'synthetic-v1', '--rubric-version', 'human-review-v1',
                '--evidence', 'config/event.json'], cwd=PROJECT, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('Disk reserve', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse((root / 'runs/model-evaluations').exists())


if __name__ == '__main__':
    unittest.main()
