#!/usr/bin/env python3
"""Verify committed HEAD in a disposable clone and standalone wheel environment.

Requires Python 3.11+, Git and package-index access. Keeps logs in ignored runs/;
never copies event archives or invokes a model. Commit source changes first.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tempfile,time
root=Path(__file__).resolve().parents[1]; reports=root/'runs/source-verification'
reports.mkdir(parents=True,exist_ok=True)
if subprocess.check_output(['git','status','--porcelain'],cwd=root):
    raise SystemExit('Commit source changes before verifying committed HEAD.')
result={'status':'failed','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'steps':[]}
env=os.environ.copy()
for key in ('F1_WORKSPACE','PYTHONPATH','TYPESAFE_API_KEY'):env.pop(key,None)
env['F1_PYTHON']=sys.executable
env['PIP_DISABLE_PIP_VERSION_CHECK']='1'
def run(name,args,cwd,environment=None):
    start=time.monotonic();p=subprocess.run([str(x) for x in args],cwd=cwd,env=environment or env,text=True,capture_output=True)
    (reports/(name+'.txt')).write_text(p.stdout+p.stderr)
    result['steps'].append({'name':name,'exit_code':p.returncode,'seconds':round(time.monotonic()-start,2)})
    print(name, 'PASS' if p.returncode==0 else 'FAIL',flush=True)
    if p.returncode:
        print((p.stdout+p.stderr)[-2500:],flush=True)
        raise RuntimeError(name)
    return p.stdout
try:
  with tempfile.TemporaryDirectory(prefix='f1-readiness-') as temp:
    tmp=Path(temp);clone=tmp/'source'
    run('clean-clone',['git','clone','--quiet','--no-local',root,clone],tmp)
    assert not any((clone/x).exists() for x in ['events','sites','research','data','media','outputs','config'])
    run('clone-bootstrap',['./scripts/bootstrap'],clone)
    check_env=env.copy();check_env.pop('F1_PYTHON',None)
    run('clone-offline-checks',['./scripts/check'],clone,check_env)
    run('clone-wheel-build',[clone/'.venv/bin/python','-m','pip','wheel','--no-deps','--wheel-dir',tmp/'wheels','.'],clone)
    wheel=next((tmp/'wheels').glob('f1_content_pipeline-*.whl'))
    run('clone-wheel-inspection',[clone/'.venv/bin/python',clone/'scripts/check_wheel.py',wheel],tmp)
    run('wheel-dependency',[clone/'.venv/bin/python','-m','pip','download','--only-binary=:all:','-r',clone/'requirements.txt','--dest',tmp/'wheels'],tmp)
    venv=tmp/'installed'
    run('wheel-environment',[sys.executable,'-m','venv',venv],tmp)
    run('wheel-install',[venv/'bin/python','-m','pip','install','--no-index','--find-links',tmp/'wheels',wheel],tmp)
    run('installed-doctor',[venv/'bin/f1-content','--workspace',clone/'examples/synthetic','doctor'],tmp)
    run('installed-jev-validation',[venv/'bin/f1-jev','--request',clone/'examples/synthetic/jev-request.json','--validate-only'],tmp)
    smoke="""from pathlib import Path
from importlib.resources import files
import json,sys
import f1_pipeline
from f1_pipeline import render,jev_adapter
assert Path(sys.prefix).resolve() in Path(f1_pipeline.__file__).resolve().parents
r=files('f1_pipeline').joinpath('resources')
for name in ('timeline.css','timeline.js'):
    assert len(r.joinpath(name).read_text())>100
jev_adapter.validate_request({'model':jev_adapter.MODEL,'state':'Synthetic','questions':json.loads(r.joinpath('jev_questions.json').read_text())})
print('Installed package imports and resource loading passed outside source checkout.')
"""
    run('installed-resources',[venv/'bin/python','-I','-c',smoke],tmp)
    workspace=tmp/'synthetic-event'
    docs={'config/event.json':json.loads((clone/'examples/synthetic/config/event.json').read_text()),
          'data/processed/catalog.json':{'sources':[{'id':'synthetic-clip','asset_id':'synthetic-asset','title':'Fictional clip with no visual evidence','url':'https://example.invalid/synthetic','caption_tracks':[]}]},
          'data/processed/editorial.json':{'timeline':[]},
          'research/media/clip_review.json':{'reviews':[]}}
    for path,value in docs.items():
        out=workspace/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(value))
    run('installed-jev-preparation',[venv/'bin/f1-content','--workspace',workspace,'prepare-jev'],tmp)
    prepared=json.loads((workspace/'data/processed/jev_requests/index.json').read_text())
    assert prepared['actual_model_inference'] is False and len(prepared['requests'])==1
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=clone)
    result.update(status='passed',archive_directories_absent=True,installed_outside_checkout=True,provider_inference=False,wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())
finally:
  (reports/'clean-clone-result.json').write_text(json.dumps(result,indent=2)+'\n')
