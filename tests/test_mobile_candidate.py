"""One-shot mobile execution bindings: no credential or provider calls."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from f1_pipeline.hosted_inference import preflight

PROJECT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'The optional mobile helper needs Node.js')
class MobileCandidateTests(unittest.TestCase):
    def fixture(self, root):
        def write(relative, data):
            file = root / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(data))
            return {'path': relative, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
        write('config/event.json', json.loads((PROJECT/'examples/synthetic/config/event.json').read_text()))
        request = json.loads((PROJECT/'examples/synthetic/hosted-request.json').read_text())
        binding = write('runs/pilot/request.json', request)
        reference = write('runs/pilot/reference.json', {'prompt_version': 'reference', 'rubric_version': 'rubric'})
        manifest = write('outputs/manifest.json', {'synthetic': 'bound manifest'})
        video = write('outputs/synthetic-video.json', {'synthetic': 'bound video'})
        auth = {'source': {'kind': 'human'}, 'max_calls': 1, 'provider': 'openrouter',
                'model': request['model'], 'budget_usd': 1, 'request_binding': binding,
                'work_id': 'candidate-v2', 'comparison_id': 'synthetic-comparison',
                'prompt_version': 'corrected-json-v2', 'rubric_version': 'rubric'}
        authorization = write('runs/pilot/authorization.json', auth)
        state = {'comparison_id': auth['comparison_id'], 'manifest_sha256': manifest['sha256'],
                 'video': video, 'reference_receipt': reference,
                 'active_hosted_candidate': {**{k: auth[k] for k in ('model', 'work_id', 'prompt_version', 'rubric_version')},
                                            'request': binding, 'spending_authorization': authorization}}
        write('runs/pilot/pilot-state.json', state)
        # Construct a fictional origin; private deployment addresses never enter source.
        return {'mode': 'verify-execution', 'siteUrl': 'https://' + 'synthetic' + '.chatgpt.site',
                'workspace': str(root), 'budgetUsd': 1, 'operationId': authorization['sha256'][:24],
                'requestSha256': preflight(request)['request_sha256']}

    def invoke(self, payload):
        return subprocess.run([shutil.which('node'), str(PROJECT/'scripts/run_mobile_candidate.mjs')],
                              input=json.dumps(payload)+'\n', text=True, capture_output=True, timeout=10)

    def test_corrected_work_keeps_its_prompt_identity_and_refuses_existing_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.fixture(root)
            result = self.invoke(payload)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(result.stdout.splitlines()[-1])
            self.assertEqual(record['work_id'], 'candidate-v2')
            self.assertFalse(record['inference_attempted'])
            assets = root/'runs/model-evaluations/synthetic-comparison/candidate-v2.assets'
            assets.mkdir(parents=True)
            (assets/'intent.json').write_text('{"synthetic":"interrupted execution"}')
            self.assertNotEqual(self.invoke(payload).returncode, 0)

    def test_corrected_work_cannot_change_prompt_identity_under_old_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.fixture(root)
            state_path = root/'runs/pilot/pilot-state.json'
            state = json.loads(state_path.read_text())
            state['active_hosted_candidate']['prompt_version'] = 'unapproved-prompt'
            state_path.write_text(json.dumps(state))
            self.assertNotEqual(self.invoke(payload).returncode, 0)

    def test_legacy_work_id_cannot_reuse_authorization_in_a_fresh_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.fixture(root)
            assets = root/'runs/model-evaluations/synthetic-comparison/candidate-v2.assets'
            assets.mkdir(parents=True)
            (assets/'intent.json').write_text('{"synthetic":"already attempted"}')
            state_path = root/'runs/pilot/pilot-state.json'
            state = json.loads(state_path.read_text())
            state['comparison_id'] = 'unapproved-comparison'
            state['active_hosted_candidate'].update(work_id='openrouter-candidate-v1',
                prompt_version='unapproved-prompt', rubric_version='unapproved-rubric')
            state_path.write_text(json.dumps(state))
            result = self.invoke(payload)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('verified_execution_bindings', result.stdout)

    def test_old_authorization_without_identity_bindings_is_read_only_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.fixture(root)
            authorization_path = root/'runs/pilot/authorization.json'
            authorization = json.loads(authorization_path.read_text())
            for field in ('work_id', 'comparison_id', 'prompt_version', 'rubric_version'):
                authorization.pop(field)
            authorization_path.write_text(json.dumps(authorization))
            sha = hashlib.sha256(authorization_path.read_bytes()).hexdigest()
            state_path = root/'runs/pilot/pilot-state.json'
            state = json.loads(state_path.read_text())
            state['active_hosted_candidate']['work_id'] = 'openrouter-candidate-v1'
            state['active_hosted_candidate']['spending_authorization']['sha256'] = sha
            state_path.write_text(json.dumps(state))
            payload['operationId'] = sha[:24]
            self.assertNotEqual(self.invoke(payload).returncode, 0)
