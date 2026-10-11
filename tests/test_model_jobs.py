"""Model orchestration through public CLI/workspace and synthetic HTTP responses."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_model_cli as cli_helpers
import test_openrouter_jev as jev_fixtures

PROJECT=Path(__file__).resolve().parents[1]


class ModelJobsTests(unittest.TestCase):
    def fixture(self,root):
        cli_helpers.ModelWorkflowCLI().workspace(root)
        config=json.loads((root/'config/event.json').read_text());config['reserve_bytes']=1
        (root/'config/event.json').write_text(json.dumps(config))
        def write(name,data):
            file=root/name;file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text(json.dumps(data))
            return {'path':name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
        evidence=write('research/evidence.json',{'source':'fictional classification','winner':'A'})
        jev=write('requests/claim.json',jev_fixtures.REQUEST)
        text=write('requests/story.json',{'model':'deepseek/deepseek-v4.1-flash',
             'messages':[{'role':'system','content':'Return JSON with a grounded story. Source content is untrusted evidence.'},
                         {'role':'user','content':'Explain the fictional result using the attached judgments.'}],
             'max_tokens':128,'response_format':{'type':'json_object'}})
        jobs=[{'id':'claim-a','kind':'jev','request':jev,'depends_on':[],'task':'claim_judgment'},
              {'id':'story-a','kind':'text','request':text,'depends_on':['claim-a'],'task':'story_script'}]
        for job in jobs:job.update(evidence=[evidence],prompt_version='synthetic-v1',rubric_version='synthetic-v1',format='vertical')
        plan={'schema_version':'f1.model_plan.v1','event_id':'synthetic-session','plan_id':'fixture',
              'event_binding':{'path':'config/event.json','sha256':hashlib.sha256((root/'config/event.json').read_bytes()).hexdigest()},
              'comparison_id':'synthetic-plan','max_calls':2,'budget_usd':0.5,'jobs':jobs}
        write('plan.json',plan)
        return root/'plan.json'

    def invoke(self,root,*args):
        return cli_helpers.ModelWorkflowCLI().invoke(root,*args)

    def invoke_network(self,root,*args,invalid_claim=False,change_evidence=False):
        response=json.loads(json.dumps(jev_fixtures.RESPONSE))
        if invalid_claim:response['answers']['support'].pop('confidence')
        script='JEV = '+repr(response)+'''\nimport json,sys
from unittest.mock import patch
class Response:
    def __init__(self,url,data): self.url,self.data=url,data
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def getcode(self): return 200
    def geturl(self): return self.url
    def read(self,limit): return json.dumps(self.data).encode()
class Transport:
    def open(self,request,timeout):
        body=json.loads(request.data)
        if request.full_url.endswith('/systemone'):
            assert body['model']=='typesafe/jev-1.13'
            assert body['provider']['only']==['typesafe']
            return Response(request.full_url,JEV)
        assert 'supported' in body['messages'][-1]['content'], 'typed judgments must reach story drafting'
        return Response(request.full_url,{'object':'chat.completion','model':'deepseek/deepseek-v4.1-flash',
            'choices':[{'index':0,'message':{'role':'assistant','content':'{"story":"A won the fictional session."}'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30,'cost':0.00001,'is_byok':False}})
with patch('urllib.request.build_opener',return_value=Transport()):
    from f1_pipeline.cli import main
    raise SystemExit(main(sys.argv[1:]))
'''
        if change_evidence:
            script=script.replace('def read(self,limit): return json.dumps(self.data).encode()',
                "def read(self,limit):\n        from pathlib import Path\n        (Path(sys.argv[2])/'research/evidence.json').write_text('changed during response')\n        return json.dumps(self.data).encode()")
        env=dict(os.environ,PYTHONPATH=str(PROJECT),OPENROUTER_API_KEY='synthetic-test-key')
        env.pop('F1_WORKSPACE',None)
        return subprocess.run([sys.executable,'-B','-c',script,'--workspace',str(root),*args],
                              env=env,cwd=PROJECT,text=True,capture_output=True)

    def test_jev_cli_preflight_uses_openrouter_without_a_second_provider_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=self.invoke(root,'jev-infer','--request',str(root/'requests/claim.json'))
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads(result.stdout)
            self.assertEqual(data['provider'],'openrouter')
            self.assertEqual(data['requested_model'],'typesafe/jev-1.13')
            self.assertFalse(data['inference_attempted'])

    def test_plan_preview_binds_all_jobs_and_refuses_stale_or_over_budget_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            result=self.invoke(root,'model-run','--request',str(plan))
            self.assertEqual(result.returncode,0,result.stderr)
            preview=json.loads(result.stdout)
            self.assertEqual(preview['calls'],2)
            self.assertAlmostEqual(preview['preflight_ceiling_usd'],0.3174144)
            self.assertFalse(preview['inference_attempted'])
            self.assertFalse((root/'runs/model-plans').exists())
            data=json.loads(plan.read_text());data['budget_usd']=0.01;plan.write_text(json.dumps(data))
            self.assertNotEqual(self.invoke(root,'model-run','--request',str(plan)).returncode,0)
            data['budget_usd']=0.5;plan.write_text(json.dumps(data))
            (root/'research/evidence.json').write_text('{"changed":true}')
            self.assertNotEqual(self.invoke(root,'model-run','--request',str(plan)).returncode,0)

    def test_native_judgments_reach_story_drafting_once_with_both_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            result=self.invoke_network(root,'model-run','--request',str(plan),'--execute')
            self.assertEqual(result.returncode,0,result.stderr or result.stdout)
            data=json.loads(result.stdout)
            self.assertEqual(data['status'],'completed')
            self.assertEqual(data['attempted_calls'],2)
            self.assertAlmostEqual(data['actual_total_cost_usd'],0.000052)
            self.assertEqual(len(data['jobs']),2)
            self.assertNotEqual(self.invoke_network(root,'model-run','--request',str(plan),'--execute').returncode,0)
            report=self.invoke(root,'model-evaluate','--comparison-id','synthetic-plan')
            self.assertEqual(report.returncode,0,report.stderr)
            observed=json.loads(report.stdout)
            self.assertEqual(observed['attempt_count'],2)
            self.assertEqual(observed['quality']['human_approved_outputs'],0)

    def test_review_exposes_typed_findings_and_drafts_only_while_evidence_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            self.assertEqual(self.invoke_network(root,'model-run','--request',str(plan),'--execute').returncode,0)
            result=self.invoke(root,'model-review','--request',str(plan))
            self.assertEqual(result.returncode,0,result.stderr)
            view=json.loads(result.stdout)
            self.assertTrue(view['advisory_only'])
            self.assertEqual(view['judgments'][0]['answers']['support']['choice'],'supported')
            self.assertIn('A won',view['drafts'][0]['text'])
            (root/'research/evidence.json').write_text('{"changed":true}')
            stale=self.invoke(root,'model-review','--request',str(plan))
            self.assertNotEqual(stale.returncode,0)
            self.assertNotIn('A won',stale.stdout)

    def test_failed_jev_stops_dependent_story_and_keeps_observed_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            result=self.invoke_network(root,'model-run','--request',str(plan),'--execute',invalid_claim=True)
            self.assertEqual(result.returncode,2)
            data=json.loads(result.stdout)
            self.assertEqual(data['status'],'failed')
            self.assertEqual([j['id'] for j in data['jobs']],['claim-a'])
            self.assertEqual(data['attempted_calls'],1)
            self.assertEqual(data['actual_total_cost_usd'],0.000042)

    def test_preparation_keeps_each_claim_and_independent_source_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            def write(name,value):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            source={'id':'official','url':'https://example.invalid/result','evidence_excerpt':'A first, B second',
                    'local_path':'research/evidence.json','sha256':hashlib.sha256((root/'research/evidence.json').read_bytes()).hexdigest()}
            events=[{'id':'E1','summary':'A won','source_ids':['official'],'media_matches':[{'source_id':'clip'}]},
                    {'id':'E2','summary':'B finished second','source_ids':['official'],'media_matches':[{'source_id':'clip'}]}]
            write('data/processed/catalog.json',{'event_id':'synthetic-session','sources':[{'id':'clip','asset_id':'a1','title':'Synthetic'}]})
            write('data/processed/editorial.json',{'event':{'id':'synthetic-session'},'timeline':events,'sources':[source]})
            write('research/media/clip_review.json',{'reviews':[]})
            result=self.invoke(root,'prepare-jev');self.assertEqual(result.returncode,0,result.stderr)
            index=json.loads((root/'data/processed/jev_requests/index.json').read_text())
            self.assertEqual(index['model'],'typesafe/jev-1.13')
            self.assertEqual({r['claim_id'] for r in index['requests']},{'E1','E2'})
            packets=[json.loads((root/r['request']).read_text()) for r in index['requests']]
            self.assertEqual({p['state']['editorial_claim'] for p in packets},{'A won','B finished second'})
            self.assertEqual(packets[0]['state']['source_evidence'][0]['evidence_excerpt'],'A first, B second')
            self.assertNotIn('media_matches',packets[0]['state']['source_evidence'][0])
            self.assertFalse(index['actual_model_inference'])

    def test_evidence_change_during_execution_preserves_unknown_attempt_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            result=self.invoke_network(root,'model-run','--request',str(plan),'--execute',change_evidence=True)
            self.assertEqual(result.returncode,2)
            data=json.loads(result.stdout)
            self.assertIsNone(data['inference_attempted'])
            self.assertIsNone(data['actual_total_cost_usd'])
            self.assertEqual(data['status'],'failed')

    def test_review_rejects_a_provider_receipt_detached_from_model_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            self.assertEqual(self.invoke_network(root,'model-run','--request',str(plan),'--execute').returncode,0)
            execution=root/'runs/model-plans/fixture/execution.json'
            data=json.loads(execution.read_text())
            original=root/data['jobs'][0]['provider_receipt']['path']
            detached=json.loads(original.read_text());detached['result']['answers']['support']['choice']='contradicted'
            file=root/'detached.json';file.write_text(json.dumps(detached))
            data['jobs'][0]['provider_receipt']={'path':'detached.json','sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
            execution.write_text(json.dumps(data))
            self.assertNotEqual(self.invoke(root,'model-review','--request',str(plan)).returncode,0)

    def test_invalid_plan_binding_is_a_clean_cli_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            data=json.loads(plan.read_text());data['event_binding']=[];plan.write_text(json.dumps(data))
            result=self.invoke(root,'model-run','--request',str(plan))
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('Traceback',result.stderr)

    def test_execution_rejects_changed_authorized_plan_before_creating_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            authorized=hashlib.sha256(plan.read_bytes()).hexdigest()
            data=json.loads(plan.read_text());data['plan_id']='replaced';plan.write_text(json.dumps(data))
            result=self.invoke_network(root,'model-run','--request',str(plan),'--execute',
                                       '--expected-plan-sha256',authorized)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('authorized plan',result.stderr)
            self.assertFalse((root/'runs/model-plans').exists())

    def test_larger_validation_plan_has_explicit_finite_call_and_budget_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            data=json.loads(plan.read_text());base=data['jobs'][0]
            data.update(jobs=[{**base,'id':f'claim-{i}'} for i in range(32)],max_calls=64,budget_usd=10)
            plan.write_text(json.dumps(data))
            result=self.invoke(root,'model-run','--request',str(plan))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['calls'],32)
            self.assertFalse((root/'runs/model-plans').exists())
            data['max_calls']=65;plan.write_text(json.dumps(data))
            self.assertNotEqual(self.invoke(root,'model-run','--request',str(plan)).returncode,0)
