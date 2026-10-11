"""Public preparation boundary for a version-bound mobile review destination."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT


class ReviewDestinationTests(unittest.TestCase):
    def fixture(self, root):
        (root/'config').mkdir()
        (root/'config/event.json').write_text((PROJECT/'examples/synthetic/config/event.json').read_text())
        output=root/'outputs/versions/example';output.mkdir(parents=True)
        for name in ('video.mp4','poster.jpg','script.txt','captions.srt'):
            (output/name).write_bytes(('synthetic '+name).encode())
        digest=lambda p:hashlib.sha256((root/p).read_bytes()).hexdigest()
        evidence = ('config/event.json', 'research/event/video_plan.json',
                    'research/event/event_bundle.json', 'research/media/clip_review.json',
                    'data/processed/catalog.json', 'data/processed/editorial.json')
        for path in evidence[1:]:
            file = root/path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('{"synthetic":true}')
        inputs = {path: digest(path) for path in evidence}
        edl = 'outputs/versions/example/edit-plan.json'
        (root/edl).write_text('{"event_id":"synthetic-session","edits":{}}')
        paths={'path':'outputs/versions/example/video.mp4','thumbnail':'outputs/versions/example/poster.jpg',
               'script':'outputs/versions/example/script.txt','captions':'outputs/versions/example/captions.srt'}
        video={'format':'vertical','title':'Synthetic phone pilot',**paths,'sha256':digest(paths['path']),
               'duration':46.8,'width':720,'height':1280,'input_hashes':inputs,
               'companion_sha256':{k:digest(paths[k]) for k in ('thumbnail','script','captions')}}
        manifest={'event_id':'synthetic-session','run_id':'example','videos':[video],
                  'input_hashes':inputs,'edit_plan':edl,'edit_plan_sha256':digest(edl)}
        (root/'outputs/manifest.json').write_text(json.dumps(manifest))
        (root/'outputs/qa.json').write_text(json.dumps({'status':'passed','errors':[],
            'event_id':'synthetic-session','edit_plan_sha256':digest(edl),
            'videos':[{'format':'vertical','sha256':video['sha256']}],
            'input_hashes':{**inputs,'outputs/manifest.json':digest('outputs/manifest.json')}}))
        return video

    def invoke(self, root, site, package_root=None):
        env=dict(os.environ,PYTHONPATH=str(package_root or PACKAGE_ROOT));env.pop('F1_WORKSPACE',None)
        return subprocess.run([sys.executable,'-B','-m','f1_pipeline','--workspace',str(root),
            'prepare-review-site','--site-directory',str(site)],env=env,cwd=root.parent,text=True,capture_output=True)

    def status(self, root):
        env=dict(os.environ,PYTHONPATH=str(PACKAGE_ROOT));env.pop('F1_WORKSPACE',None)
        return subprocess.run([sys.executable,'-B','-m','f1_pipeline','--workspace',str(root),
            'review-site-status'],env=env,cwd=root.parent,text=True,capture_output=True)

    def test_mobile_destination_contains_only_bound_review_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            video=self.fixture(root)
            result=self.invoke(root,site)
            self.assertEqual(result.returncode,0,result.stderr)
            prepared=json.loads(result.stdout)
            pilot=json.loads((site/'app/data/pilot.json').read_text())
            self.assertEqual(pilot['videoSha256'],video['sha256'])
            self.assertEqual(pilot['eventId'],'synthetic-session')
            self.assertEqual(pilot['format'],'vertical')
            self.assertEqual(pilot['reviewLabel'],'01 / REFERENCE')
            self.assertFalse(pilot['credentialHandoffEnabled'])
            self.assertTrue((site/'public'/pilot['videoUrl'].lstrip('/')).is_file())
            self.assertEqual(prepared['status'],'prepared_awaiting_web_checks')
            self.assertNotIn(str(root),(site/'app/data/pilot.json').read_text())
            self.assertFalse(json.loads((site/'app/data/credential-operation.json').read_text())['enabled'])
            templates = Path(PACKAGE_ROOT)/'f1_pipeline/resources/mobile-review-site'
            for source in templates.rglob('*'):
                if source.is_file():
                    self.assertEqual((site/source.relative_to(templates)).read_bytes(), source.read_bytes())
            for name in ('app/review.tsx', 'app/api/feedback/route.ts',
                         'app/api/credential/route.ts', 'app/api/operator/credential/route.ts'):
                self.assertTrue((site/name).is_file(), name)

    def test_incomplete_templates_fail_before_changing_the_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            self.fixture(root)
            package=Path(tmp)/'incomplete-package'
            shutil.copytree(Path(PACKAGE_ROOT)/'f1_pipeline', package/'f1_pipeline',
                            ignore=shutil.ignore_patterns('__pycache__'))
            (package/'f1_pipeline/resources/mobile-review-site/app/api/feedback/route.ts').unlink()
            (site/'sentinel.txt').write_text('existing starter')
            result=self.invoke(root,site,package)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('templates are missing',result.stderr)
            self.assertEqual([p.name for p in site.iterdir()],['sentinel.txt'])
            self.assertFalse((root/'runs/pilot/review-destination.json').exists())

    def test_packaged_script_input_is_resolved_outside_the_event_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            self.fixture(root)
            (root/'research/event/video_plan.json').unlink()
            key='f1_pipeline/video_plan.py'
            sha=hashlib.sha256((Path(PACKAGE_ROOT)/key).read_bytes()).hexdigest()
            manifest_path=root/'outputs/manifest.json'
            manifest=json.loads(manifest_path.read_text())
            for bindings in (manifest['input_hashes'],manifest['videos'][0]['input_hashes']):
                bindings.pop('research/event/video_plan.json');bindings[key]=sha
            manifest_path.write_text(json.dumps(manifest))
            qa_path=root/'outputs/qa.json';qa=json.loads(qa_path.read_text())
            qa['input_hashes'].pop('research/event/video_plan.json');qa['input_hashes'][key]=sha
            qa['input_hashes']['outputs/manifest.json']=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            qa_path.write_text(json.dumps(qa))
            result=self.invoke(root,site)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_edit_plan_and_required_qa_bindings_must_remain_current(self):
        for change in ('edit_plan', 'qa_edit_plan_hash', 'missing_qa_input'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
                self.fixture(root)
                result=self.invoke(root,site);self.assertEqual(result.returncode,0,result.stderr)
                self.record_web_checks(root)
                self.assertEqual(self.status(root).returncode,0)
                previous={p.relative_to(site):p.read_bytes() for p in site.rglob('*') if p.is_file()}
                if change=='edit_plan':
                    (root/'outputs/versions/example/edit-plan.json').write_text('{"changed":true}')
                else:
                    qa_path=root/'outputs/qa.json';qa=json.loads(qa_path.read_text())
                    if change=='qa_edit_plan_hash':qa['edit_plan_sha256']='0'*64
                    else:qa['input_hashes'].pop('research/event/event_bundle.json')
                    qa_path.write_text(json.dumps(qa))
                self.assertNotEqual(self.invoke(root,site).returncode,0)
                self.assertEqual({p.relative_to(site):p.read_bytes() for p in site.rglob('*') if p.is_file()},previous)
                status=self.status(root)
                self.assertEqual(status.returncode,2)
                self.assertFalse(json.loads(status.stdout)['ready_for_human_review'])

    def test_mobile_key_form_requires_unchanged_bounded_execution_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            video=self.fixture(root)
            pilot_dir=root/'runs/pilot';pilot_dir.mkdir(parents=True)
            request=pilot_dir/'request.json'
            request.write_text((PROJECT/'examples/synthetic/hosted-request.json').read_text())
            binding={'path':str(request.relative_to(root)),'sha256':hashlib.sha256(request.read_bytes()).hexdigest()}
            auth={'source':{'kind':'human'},'provider':'openrouter','model':'deepseek/deepseek-v4.1-flash',
                  'max_calls':1,'budget_usd':0.3244032,'request_binding':binding}
            authorization=pilot_dir/'authorization.json';authorization.write_text(json.dumps(auth))
            authorization_binding={'path':str(authorization.relative_to(root)),
                'sha256':hashlib.sha256(authorization.read_bytes()).hexdigest()}
            state={'manifest_sha256':hashlib.sha256((root/'outputs/manifest.json').read_bytes()).hexdigest(),
                   'video':{'sha256':video['sha256']},
                   'active_hosted_candidate':{'request':binding,'spending_authorization':authorization_binding}}
            (pilot_dir/'pilot-state.json').write_text(json.dumps(state))
            result=self.invoke(root,site);self.assertEqual(result.returncode,0,result.stderr)
            operation=json.loads((site/'app/data/credential-operation.json').read_text())
            self.assertTrue(operation['enabled']);self.assertEqual(operation['budgetUsd'],0.3244032)
            previous=(site/'app/data/credential-operation.json').read_bytes()
            authorization.write_text('changed authorization')
            result=self.invoke(root,site)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((site/'app/data/credential-operation.json').read_bytes(),previous)

    def test_changed_or_unvalidated_video_cannot_be_prepared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            video=self.fixture(root)
            (root/video['path']).write_bytes(b'changed source')
            result=self.invoke(root,site)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Changed or unbound review asset', result.stderr)
            self.assertFalse((site/'app/data/pilot.json').exists())

    def test_candidate_context_is_bound_to_the_selected_output_without_key_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            video=self.fixture(root)
            pilot_dir=root/'runs/pilot';pilot_dir.mkdir(parents=True)
            state={'manifest_sha256':hashlib.sha256((root/'outputs/manifest.json').read_bytes()).hexdigest(),
                   'video':{'sha256':video['sha256']},'review_label':'02 / CANDIDATE',
                   'authoring_note':'Synthetic hosted draft with subscription editorial revision.'}
            state_path=pilot_dir/'pilot-state.json';state_path.write_text(json.dumps(state))
            result=self.invoke(root,site);self.assertEqual(result.returncode,0,result.stderr)
            pilot=json.loads((site/'app/data/pilot.json').read_text())
            self.assertEqual(pilot['reviewLabel'],'02 / CANDIDATE')
            self.assertEqual(pilot['authoringNote'],state['authoring_note'])
            self.assertFalse(pilot['credentialHandoffEnabled'])
            previous=(site/'app/data/pilot.json').read_bytes()
            state['authoring_note']=['invalid context'];state_path.write_text(json.dumps(state))
            self.assertNotEqual(self.invoke(root,site).returncode,0)
            self.assertEqual((site/'app/data/pilot.json').read_bytes(),previous)

    def test_stale_qa_and_missing_web_checks_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            self.fixture(root)
            result=self.invoke(root,site)
            self.assertEqual(result.returncode,0,result.stderr)
            status=self.status(root)
            self.assertEqual(status.returncode,2)
            self.assertFalse(json.loads(status.stdout)['ready_for_human_review'])
            qa=root/'outputs/qa.json';data=json.loads(qa.read_text())
            data['input_hashes']['outputs/manifest.json']='0'*64;qa.write_text(json.dumps(data))
            result=self.invoke(root,site)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('validation is stale',result.stderr)

    def test_recorded_web_checks_never_cover_changed_companions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'event';site=Path(tmp)/'site';root.mkdir();site.mkdir()
            video=self.fixture(root)
            result=self.invoke(root,site);self.assertEqual(result.returncode,0,result.stderr)
            self.record_web_checks(root)
            self.assertEqual(self.status(root).returncode,0)
            (root/video['script']).write_text('changed narration')
            status=self.status(root)
            self.assertEqual(status.returncode,2)
            self.assertFalse(json.loads(status.stdout)['ready_for_human_review'])

    def record_web_checks(self, root):
        record_path=root/'runs/pilot/review-destination.json'
        record=json.loads(record_path.read_text())
        # Construct a synthetic platform URL; live private addresses stay out of source.
        record.update(project_id='synthetic-site',url='https://' + 'synthetic' + '.chatgpt.site')
        checks={'manifest_sha256':record['manifest_sha256'],'video_sha256':record['video_sha256'],
                    'project_id':record['project_id'],'url':record['url'],'site_commit_sha':'synthetic-commit',
                    'checks':[{'check':name,'status':'passed'} for name in (
                        'mobile_layout','video_playback','video_seek','captions_unobscured',
                        'annotation_persistence','decision_history','chat_copy','version_rejection',
                        'authentication','hosted_page_and_media')]}
        deployment={'project_id':record['project_id'],'url':record['url'],'status':'succeeded',
                        'id':'synthetic-deployment','version_id':'synthetic-version',
                        'commit_sha':'synthetic-commit','audience':'owner_private'}
        for key,data in (('browser_checks',checks),('deployment_receipt',deployment)):
            path=root/('runs/pilot/'+key+'.json');path.write_text(json.dumps(data))
            record[key]={'path':str(path.relative_to(root)),
                             'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        record_path.write_text(json.dumps(record))
