"""Receipts for actual stage execution and explicit required artifact contracts."""
from pathlib import Path
import uuid
from .core import ROOT, config, digest, log, now, read_json, safe_relative, write_json

CONTRACTS={
 'collect':(['config/event.json'],['data/processed/data_manifest.json']),
 'catalog':(['research/media/sources.json','research/media/clip_review.json'],['data/processed/catalog.json']),
 'analyze':(['research/event/event_bundle.json','research/event/media_matches.json','research/media/clip_review.json','data/processed/catalog.json','data/processed/data_manifest.json'],['data/processed/editorial.json','data/processed/decisions.json']),
 'prepare-jev':(['data/processed/editorial.json','data/processed/catalog.json','research/media/clip_review.json'],['data/processed/jev_requests/index.json']),
 'render':(['data/processed/editorial.json','data/processed/catalog.json','research/event/video_plan.json'],['outputs/manifest.json']),
 'validate':(['outputs/manifest.json','data/processed/catalog.json','data/processed/editorial.json'],['outputs/qa.json']),
 'finalize':(['outputs/qa.json','outputs/visual-review.json','outputs/audio-quality.json','research/event/editorial_review.json','outputs/manifest.json','data/processed/catalog.json','data/processed/editorial.json'],['outputs/delivery.json']),
 'report':(['data/processed/editorial.json','data/processed/catalog.json','outputs/manifest.json'],['outputs/index.html']),
 'timeline':(['data/processed/editorial.json','data/processed/catalog.json','outputs/manifest.json','research/media/clip_review.json'],['sites/timeline/dist/index.html'])}

PACKAGE_INPUTS={'f1_pipeline/video_plan.py','f1_pipeline/analyze.py'}

def artifact_path(path):
    if path in PACKAGE_INPUTS:
        return Path(__file__).with_name(Path(path).name)
    return safe_relative(path)

def hashes(paths,required=False):
    result={}
    for path in sorted(set(paths)):
        file=artifact_path(path)
        if not file.is_file():
            if required:raise ValueError('Required stage input is missing: '+path)
            continue
        result[path]=digest(file)
    return result

def authoritative_edl():
    manifest=read_json(safe_relative('outputs/manifest.json'),{})
    return manifest.get('edit_plan','outputs/edit-plan.json')

def contracts(name,cfg):
    inputs,outputs=CONTRACTS[name]
    required=set(inputs)|{'config/event.json'}
    optional=set()
    if cfg['id']=='2026-singapore-sprint':
        if name=='analyze':
            required.discard('research/event/media_matches.json')
            optional.add('research/event/media_matches.json')
            required.add('f1_pipeline/analyze.py')
        if name=='render' and not (ROOT/'research/event/video_plan.json').is_file():
            required.discard('research/event/video_plan.json')
            optional.add('research/event/video_plan.json')
            required.add('f1_pipeline/video_plan.py')
    if name=='render':
        from .validate import required_render_inputs
        required.update(required_render_inputs())
        if (ROOT/'outputs/manifest.json').is_file():
            required.update(('outputs/manifest.json',authoritative_edl()))
    if name in ('validate','finalize'):
        required.add(authoritative_edl())
    if name=='report':optional.add('outputs/qa.json')
    if name=='timeline':optional.add('outputs/qa.json')
    return required,optional,set(outputs)

def stage_outputs(name,base):
    result=set(base)
    if name=='render' and (ROOT/'outputs/manifest.json').is_file():
        result.add(authoritative_edl())
    return result

def stage(name,operation):
    cfg=config()
    receipt={'id':uuid.uuid4().hex,'event_id':cfg['id'],'stage':name,'started_at':now(),
             'input_hashes':{},'executor':'deterministic local code'}
    outputs=set(CONTRACTS[name][1]);before={}
    try:
        required,optional,outputs=contracts(name,cfg)
        receipt['required_inputs']=sorted(required)
        receipt['optional_inputs']=sorted(optional)
        receipt['missing_optional_inputs']=sorted(p for p in optional if not artifact_path(p).is_file())
        receipt['input_hashes']={**hashes(required,required=True),**hashes(optional)}
        before=hashes(stage_outputs(name,outputs))
        result=operation()
        if name=='validate' and (result.get('status')!='passed' or result.get('errors')):
            raise ValueError('Technical validation failed: '+'; '.join(result.get('errors',[])))
        if isinstance(result,dict) and result.get('status') in ('failed','error'):
            raise ValueError('Stage returned a failed result')
        outputs=stage_outputs(name,outputs)
        missing=[p for p in outputs if not artifact_path(p).is_file()]
        if missing:raise ValueError('Stage did not produce required output artifacts: '+', '.join(sorted(missing)))
        after=hashes(outputs,required=True)
        partial=name=='collect' and isinstance(result,dict) and (result.get('status')=='partial' or bool(result.get('failures')))
        receipt.update(status='partial' if partial else 'passed',output_hashes=after,
                       output_changes={p:'unchanged' if before.get(p)==sha else 'changed' if p in before else 'created'
                                       for p,sha in after.items()})
        if isinstance(result,dict):
            receipt['result_status']=result.get('status')
            if partial:receipt['source_failures']=result.get('failures',[])
        return result
    except Exception as exc:
        receipt.update(status='failed',error_type=type(exc).__name__,error=str(exc))
        try:receipt['output_hashes']=hashes(outputs)
        except (ValueError,OSError,TypeError) as observation_error:
            receipt.update(output_hashes={},output_observation_error=str(observation_error))
        raise
    finally:
        receipt['finished_at']=now()
        write_json(safe_relative(ROOT/'runs/stages'/f"{receipt['started_at'].replace(':','-')}-{name}-{receipt['id'][:6]}.json"),receipt)
        log('harness',receipt['status'],stage_name=name,receipt_id=receipt['id'])
