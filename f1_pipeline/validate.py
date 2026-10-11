import json
import math
from pathlib import Path
import re
import shutil
from .core import ROOT, config, digest, log, now, probe, read_json, run, safe_relative, write_json

COMPANIONS={'captions','script','thumbnail'}
QA_BASE_INPUTS={'data/processed/catalog.json','data/processed/editorial.json','outputs/manifest.json'}

def legacy_release(manifest, event_config=None):
    """Only the retained pre-versioned Sprint delivery predates render receipts."""
    selected=config() if event_config is None else event_config
    return (selected['id']=='2026-singapore-sprint'
            and manifest.get('event_id')=='2026-singapore-sprint'
            and not manifest.get('run_id') and not manifest.get('input_hashes')
            and all(v.get('path')==f"outputs/singapore-sprint-2026-{v.get('format')}.mp4"
                    for v in manifest.get('videos',[])))

def input_path(relative):
    # This fallback is package code, even when an event has a separate workspace.
    if relative=='f1_pipeline/video_plan.py':return Path(__file__).with_name('video_plan.py')
    return safe_relative(relative)

def required_render_inputs():
    from .narration import selection_inputs
    required={'config/event.json','research/event/event_bundle.json','research/media/clip_review.json',
              'data/processed/editorial.json','data/processed/catalog.json'}
    required.add('research/event/video_plan.json' if (ROOT/'research/event/video_plan.json').is_file()
                 else 'f1_pipeline/video_plan.py')
    for optional in ('research/event/media_matches.json','research/event/sector_comparison.json',
                     'data/processed/data_manifest.json'):
        if (ROOT/optional).is_file():required.add(optional)
    for asset in read_json(ROOT/'data/processed/catalog.json',{}).get('assets',[]):
        if asset.get('original'):required.add(asset['original'])
    required.update(selection_inputs(ROOT))
    return required

def verify_bindings(bindings,required,label):
    if not isinstance(bindings,dict) or not required.issubset(bindings):
        raise ValueError(label+': required input hash bindings missing')
    for relative,sha in bindings.items():
        if not isinstance(relative,str) or not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):
            raise ValueError(label+': malformed hash binding')
        path=input_path(relative)
        if not path.is_file() or digest(path)!=sha:
            raise ValueError(label+': input changed '+relative)
    return dict(bindings)

def verify_companions(video):
    bindings=video.get('companion_sha256')
    if not isinstance(bindings,dict) or set(bindings)!=COMPANIONS:
        raise ValueError('Required companion hash bindings missing')
    for key,sha in bindings.items():
        path=safe_relative(video[key])
        if not path.is_file() or digest(path)!=sha:
            raise ValueError('Companion file changed since render: '+key)

def verify_render_bindings(manifest):
    legacy=legacy_release(manifest)
    required=set() if legacy else required_render_inputs()
    captured=verify_bindings(manifest.get('input_hashes',{}),required,'render manifest')
    for video in manifest.get('videos',[]):
        bindings=verify_bindings(video.get('input_hashes',{}),required,video['format'])
        for relative,sha in bindings.items():
            if relative in captured and captured[relative]!=sha:
                raise ValueError('Output formats were rendered from different inputs: '+relative)
            captured[relative]=sha
        verify_companions(video)
    return captured

def srt_seconds(value):
    h,m,s,ms=map(int,re.split(r"[:,]",value));return h*3600+m*60+s+ms/1000

def validate():
    errors=[]; warnings=[]; checks=[]
    catalog=read_json(ROOT/"data/processed/catalog.json",{})
    editorial=read_json(ROOT/"data/processed/editorial.json",{})
    manifest=read_json(ROOT/"outputs/manifest.json",{})
    legacy=legacy_release(manifest)
    captured={}
    try:captured=verify_render_bindings(manifest)
    except (ValueError,KeyError,OSError) as exc:errors.append(str(exc))
    plan_path=safe_relative(manifest.get('edit_plan','outputs/edit-plan.json'))
    plan=read_json(plan_path,{})
    edits=plan.get('edits',{})
    if plan.get('event_id')!=config()['id']:errors.append('edit plan: event identity mismatch')
    if (not legacy and not manifest.get('edit_plan_sha256')) or (manifest.get('edit_plan_sha256') and digest(plan_path)!=manifest['edit_plan_sha256']):
        errors.append('Edit plan hash mismatch')
    for name,obj,event in (("catalog",catalog,catalog.get("event_id")),("editorial",editorial,editorial.get("event",{}).get("id")),("render",manifest,manifest.get("event_id"))):
        if event!=config()["id"]:errors.append(name+": event identity mismatch")
    sources={s["id"]:s for s in catalog.get("sources",[])}
    assets={a["id"]:a for a in catalog.get("assets",[])}
    events={e["id"]:e for e in editorial.get("timeline",[])}
    evidence={s["id"] for s in editorial.get("sources",[])}
    for source in editorial.get("sources",[]):
        if source.get("local_path") and source.get("sha256"):
            local=source['local_path']
            path=safe_relative(local) if local.startswith(('research/','data/')) else (ROOT/'research/event'/local).resolve()
            if ROOT not in path.parents or not path.exists() or digest(path)!=source["sha256"]:
                errors.append("Research source integrity mismatch: "+source["id"])
    checks.append({"check":"primary_research_source_hashes","sources":len(evidence)})
    for asset in assets.values():
        for path_key,sha_key in (("original","sha256"),("proxy","proxy_sha256")):
            path=safe_relative(asset[path_key])
            if not path.exists() or digest(path)!=asset[sha_key]:errors.append(f"Hash mismatch: {asset['id']} {path_key}")
        if asset["source_id"] not in sources:errors.append("Orphan asset: "+asset["id"])
    checks.append({"check":"source_and_derivative_hashes","assets":len(assets)})
    for event in events.values():
        if not event.get("source_ids") or set(event["source_ids"])-evidence:errors.append("Unlinked timeline claim: "+event["id"])
        for match in event.get("media_matches",[]):
            asset=assets.get(match["asset_id"])
            if not asset or not 0<=match["in"]<match["out"]<=asset["duration"]+.05:errors.append("Invalid clip bounds: "+event["id"])
            if asset and not legacy:
                review_sha=digest(safe_relative('research/media/clip_review.json'))
                if (match.get('source_sha256')!=asset['sha256'] or match.get('review_receipt_sha256')!=review_sha
                        or asset.get('review_receipt_sha256')!=review_sha):
                    errors.append('Stale reviewed media association: '+event['id'])
    checks.append({"check":"timeline_provenance_and_clip_bounds","segments":len(events)})
    video_checks=[]
    for video in manifest.get("videos",[]):
        name=video["format"]; path=safe_relative(video["path"])
        if not path.exists() or digest(path)!=video["sha256"]:
            errors.append("Final video hash mismatch: "+name);continue
        try:
            info=probe(path);streams=info["streams"]
            vs=next(s for s in streams if s["codec_type"]=="video")
            aus=next(s for s in streams if s["codec_type"]=="audio")
            duration=float(info["format"]["duration"])
            if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid encoded duration')
            if vs["codec_name"]!="h264" or aus["codec_name"]!="aac" or vs["pix_fmt"]!="yuv420p":errors.append(name+": unexpected encoding")
            if (vs["width"],vs["height"])!=(video["width"],video["height"]):errors.append(name+": size mismatch")
            stream_difference=abs(float(vs.get("duration",duration))-float(aus.get("duration",duration)))
            if stream_difference>.12:errors.append(name+": audio/video end drift")
            run(["ffmpeg","-v","error","-xerror","-i",path,"-f","null","-"],timeout=600)
            caption_text=safe_relative(video["captions"]).read_text()
            ranges=re.findall(r"(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})",caption_text)
            previous=0
            for start,end in ranges:
                start,end=srt_seconds(start),srt_seconds(end)
                if start<previous-.001 or end<=start or end>duration+.1:errors.append(name+": invalid captions")
                previous=end
            if not ranges:errors.append(name+": missing captions")
            scene_list=edits.get(name,[])
            expected=sum(s["duration"] for s in scene_list)
            drift=abs(duration-expected)
            if drift>.12:errors.append(name+f": EDL duration drift {drift:.3f}s")
            for scene in scene_list:
                if not scene.get("event_ids") or set(scene["event_ids"])-events.keys():errors.append(name+": scene has no valid events")
                if not scene.get("claim_source_ids") or set(scene["claim_source_ids"])-evidence:errors.append(name+": scene has no evidence")
                if scene.get("asset_id") not in assets and scene.get("source_id"):errors.append(name+": missing scene asset")
                if scene.get('source_id') and scene.get('asset_id') in assets:
                    asset=assets[scene['asset_id']]
                    if sources.get(scene['source_id'],{}).get('asset_id')!=scene['asset_id']:
                        errors.append(name+': scene source and asset disagree')
                    if not legacy and (scene.get('source_sha256')!=asset['sha256']
                                       or scene.get('review_receipt_sha256')!=asset.get('review_receipt_sha256')):
                        errors.append(name+': missing or stale scene provenance')
                    if scene.get('source_sha256') and scene['source_sha256']!=asset['sha256']:errors.append(name+': stale scene source hash')
                    if scene.get('source_out_limit') is not None and not 0<=scene['source_in']<scene['source_out']<=scene['source_out_limit']+.001:
                        errors.append(name+': scene exceeds selected source interval')
                    if 'reviewed_ranges' in asset and not any(r['in']<=scene['source_in'] and scene['source_out']<=r['out']+.001 for r in asset['reviewed_ranges']):
                        errors.append(name+': scene exceeds reviewed footage')
                    matches=[m for eid in scene['event_ids'] for m in events.get(eid,{}).get('media_matches',[])
                             if m.get('source_id')==scene['source_id'] and m.get('asset_id')==scene['asset_id']]
                    if not legacy and not any(m['in']<=scene['source_in']<scene['source_out']<=m['out']+.001 for m in matches):
                        errors.append(name+': scene exceeds associated event footage')
            video_checks.append({"format":name,"duration":duration,"dimensions":[vs["width"],vs["height"]],"decode":"passed", "audio_video_end_difference_seconds":round(stream_difference,4),
                                 "edl_difference_seconds":round(drift,4),"caption_cues":len(ranges),"sha256":video["sha256"]})
        except Exception as exc:errors.append(name+": "+str(exc))
    expected_formats=set(config().get('formats',['vertical','landscape']))
    if {v['format'] for v in video_checks}!=expected_formats or len(video_checks)!=len(expected_formats):errors.append('Requested video formats are missing, duplicated or invalid')
    review=read_json(ROOT/"research/event/editorial_review.json",{})
    if not review:warnings.append("Independent editorial review missing")
    if any("unverified" in a.get("rights_status","") or a.get("rights_status")=="unknown" for a in assets.values()):
        warnings.append("Local review outputs contain copyrighted source footage; reuse clearance is unverified")
    decisions=read_json(ROOT/"data/processed/decisions.json",{})
    if not decisions.get("actual_jev_inference"):warnings.append("Jev adapter contract-tested; no live Jev inference was performed")
    dm=read_json(ROOT/"data/processed/data_manifest.json",{})
    for failure in dm.get("failures",[]):warnings.append("Data source gap: "+failure["endpoint"]+" (FIA final grid is available separately)" if failure["endpoint"]=="starting_grid" else "Data source gap: "+failure["endpoint"])
    free=shutil.disk_usage(ROOT).free
    if free<config()["reserve_bytes"]:errors.append("Disk reserve not maintained")
    result={"at":now(),"event_id":config()["id"],"status":"passed" if not errors else "failed","checks":checks,"videos":video_checks,
            "errors":errors,"warnings":warnings,"disk_free_bytes":free,"visual_review":read_json(ROOT/"outputs/visual-review.json",{"status":"pending"})}
    # Preserve all render input bindings, not just files directly decoded by QA.
    checked_paths=set(QA_BASE_INPUTS)
    for asset in assets.values():
        checked_paths.update(asset[key] for key in ('original','proxy') if asset.get(key))
    for source in editorial.get('sources',[]):
        if source.get('local_path') and source.get('sha256'):
            local=source['local_path']
            checked_paths.add(local if local.startswith(('research/','data/')) else 'research/event/'+local)
    result['input_hashes']={**captured,**{path:digest(safe_relative(path)) for path in checked_paths if safe_relative(path).is_file()}}
    result['compatibility']='pre-versioned-singapore-sprint' if legacy else 'versioned-release-v1'
    result['edit_plan_sha256']=digest(plan_path) if plan_path.exists() else None
    write_json(ROOT/"outputs/qa.json",result)
    log("validate",result["status"],errors=errors,videos=len(video_checks))
    return result
