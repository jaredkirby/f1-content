"""One-shot mobile execution bindings: no credential or provider calls."""
import hashlib
import json
import os
import sys
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
                              input=json.dumps(payload)+'\n', text=True, capture_output=True, timeout=10,
                              env={**os.environ,'F1_PYTHON':sys.executable})

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

    def test_model_plan_handoff_binds_budget_jobs_and_refuses_changed_plan(self):
        import test_model_jobs as jobs
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=jobs.ModelJobsTests().fixture(root)
            sha=hashlib.sha256(plan.read_bytes()).hexdigest()
            payload={'mode':'verify-plan','siteUrl':'https://'+'synthetic'+'.chatgpt.site',
                     'workspace':str(root),'planPath':'plan.json','requestSha256':sha,
                     'operationId':sha[:24],'budgetUsd':0.5,'maxCalls':2}
            result=self.invoke(payload)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout.splitlines()[-1])['status'],'verified_plan_bindings')
            payload['maxCalls']=3
            self.assertNotEqual(self.invoke(payload).returncode,0)
            payload['maxCalls']=2
            data=json.loads(plan.read_text());data['budget_usd']=2;plan.write_text(json.dumps(data))
            self.assertNotEqual(self.invoke(payload).returncode,0)

    def test_persistent_handoff_stores_before_execution_and_stops_if_storage_fails(self):
        import test_model_jobs as jobs
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=jobs.ModelJobsTests().fixture(root)
            sha=hashlib.sha256(plan.read_bytes()).hexdigest()
            payload={'mode':'execute-plan','siteUrl':'https://'+'synthetic'+'.chatgpt.site',
                     'workspace':str(root),'planPath':'plan.json','requestSha256':sha,
                     'operationId':sha[:24],'budgetUsd':0.5,'maxCalls':2,'persistKeychain':True}
            for denied in (False,True):
                harness=root/'transport.mjs'
                harness.write_text("""
import cp from 'node:child_process';
import {syncBuiltinESMExports} from 'node:module';
const original=cp.spawnSync; let stored=false;
cp.spawnSync=(cmd,args,options)=>{
 if(args.includes('f1_pipeline.credentials')){
   if(options.input!=='synthetic-mobile-persist')throw Error('stdin missing');
   if(args.some(a=>a.includes('synthetic-mobile-persist')))throw Error('secret in args');
   stored=true;
   return {status:DENIED?2:0,stdout:'{"status":"stored"}',stderr:''};
 }
 if(args.includes('--execute')){
   if(!stored||DENIED||options.env.OPENROUTER_API_KEY)throw Error('storage boundary bypass');
   return {status:0,stdout:'{"status":"synthetic_execution_after_storage"}',stderr:''};
 }
 return original(cmd,args,options);
};
syncBuiltinESMExports();
globalThis.fetch=async()=>({status:200,text:async()=>JSON.stringify(HANDOFF)});
""".replace('DENIED','true' if denied else 'false').replace('HANDOFF',json.dumps({
                    'key':'synthetic-mobile-persist','operationId':sha[:24],'requestSha256':sha,
                    'budgetUsd':0.5,'maxCalls':2,'persistKeychain':True})))
                result=subprocess.run([shutil.which('node'),'--import',str(harness),str(PROJECT/'scripts/run_mobile_candidate.mjs')],
                    input=json.dumps(payload)+'\n',text=True,capture_output=True,timeout=10,
                    env={**os.environ,'F1_PYTHON':sys.executable})
                self.assertEqual(result.returncode,1 if denied else 0,result.stderr)
                self.assertNotIn('synthetic-mobile-persist',result.stdout+result.stderr)
                if not denied:self.assertIn('synthetic_execution_after_storage',result.stdout)

    def test_storage_consent_must_match_in_both_directions(self):
        import test_model_jobs as jobs
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=jobs.ModelJobsTests().fixture(root)
            sha=hashlib.sha256(plan.read_bytes()).hexdigest()
            payload={'mode':'execute-plan','siteUrl':'https://'+'synthetic'+'.chatgpt.site',
                     'workspace':str(root),'planPath':'plan.json','requestSha256':sha,
                     'operationId':sha[:24],'budgetUsd':0.5,'maxCalls':2}
            for local,remote in ((None,True),(False,True),(True,False)):
                with self.subTest(local=local,remote=remote):
                    if local is None:payload.pop('persistKeychain',None)
                    else:payload['persistKeychain']=local
                    harness=root/'transport.mjs'
                    harness.write_text("""
import cp from 'node:child_process';
import {syncBuiltinESMExports} from 'node:module';
const original=cp.spawnSync;
cp.spawnSync=(cmd,args,options)=>{
 if(args.includes('--execute')||args.includes('f1_pipeline.credentials')){
  process.stdout.write('FORBIDDEN_SIDE_EFFECT\\n');
  return {status:0,stdout:'{"status":"stored"}',stderr:''};
 }
 return original(cmd,args,options);
};
syncBuiltinESMExports();
globalThis.fetch=async()=>({status:200,text:async()=>JSON.stringify(HANDOFF)});
""".replace('HANDOFF',json.dumps({'key':'synthetic-key','operationId':sha[:24],
                        'requestSha256':sha,'budgetUsd':0.5,'maxCalls':2,'persistKeychain':remote})))
                    result=subprocess.run([shutil.which('node'),'--import',str(harness),str(PROJECT/'scripts/run_mobile_candidate.mjs')],
                        input=json.dumps(payload)+'\n',text=True,capture_output=True,timeout=10,
                        env={**os.environ,'F1_PYTHON':sys.executable})
                    self.assertNotIn('FORBIDDEN_SIDE_EFFECT',result.stdout)
                    self.assertEqual(result.returncode,1)
