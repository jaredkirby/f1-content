from .core import ROOT, config, digest, log, now, read_json, write_json, safe_relative
from .validate import (QA_BASE_INPUTS, legacy_release, verify_bindings, verify_companions,
                       verify_render_bindings)

def finalize():
    qa=read_json(ROOT/"outputs/qa.json",{})
    visual=read_json(ROOT/"outputs/visual-review.json",{})
    audio=read_json(ROOT/"outputs/audio-quality.json",[])
    review=read_json(ROOT/"research/event/editorial_review.json",{})
    manifest=read_json(ROOT/"outputs/manifest.json",{})
    if qa.get("status")!="passed" or qa.get("errors"):
        raise ValueError("Technical QA has not passed")
    from pathlib import Path
    script_key='research/event/video_plan.json' if (ROOT/'research/event/video_plan.json').exists() else 'f1_pipeline/video_plan.py'
    script_path=ROOT/script_key if script_key.startswith('research/') else Path(__file__).with_name('video_plan.py')
    if review.get("overall_status")!="pass" or review.get("input_hashes",{}).get(script_key)!=digest(script_path):
        raise ValueError("Editorial review does not match the current script")
    if review.get("input_hashes",{}).get("research/event/event_bundle.json")!=digest(ROOT/"research/event/event_bundle.json"):
        raise ValueError("Event research changed since editorial review")
    if visual.get("status")!="passed":
        raise ValueError("Rendered visual/playback review missing")
    if manifest.get('event_id')!=config()['id'] or qa.get('event_id')!=config()['id']:
        raise ValueError('Finalization event identity mismatch')
    legacy=legacy_release(manifest)
    captured=verify_render_bindings(manifest)
    required_qa=set() if legacy else QA_BASE_INPUTS|set(captured)
    verify_bindings(qa.get('input_hashes',{}),required_qa,'Technical review')
    for relative,sha in captured.items():
        if not legacy and qa['input_hashes'].get(relative)!=sha:
            raise ValueError('Technical review did not validate render input: '+relative)
    plan_path=safe_relative(manifest.get('edit_plan','outputs/edit-plan.json'))
    if (not legacy or manifest.get('edit_plan')) and (qa.get('edit_plan_sha256')!=digest(plan_path)
            or manifest.get('edit_plan_sha256')!=digest(plan_path)):
        raise ValueError('Technical edit-plan review is stale')
    formats=config().get('formats',['vertical','landscape'])
    if {v["format"] for v in manifest.get("videos",[])}!=set(formats) or len(manifest.get('videos',[]))!=len(formats):
        raise ValueError("Every requested edit must exist exactly once")
    catalog=read_json(ROOT/"data/processed/catalog.json")
    editorial=read_json(ROOT/"data/processed/editorial.json")
    counts={'source_records':len(catalog['sources']),'downloaded_videos':len(catalog['assets']),
            'timeline_segments':len(editorial['timeline']),'ranked_ideas':len(editorial['ideas'])}
    for video in manifest["videos"]:
        sha=digest(safe_relative(video["path"]))
        if sha!=video["sha256"] or not any(v["sha256"]==sha and v.get('format')==video['format'] for v in qa.get("videos",[])):
            raise ValueError("Technical review is stale")
        if not any(v["video_sha256"]==sha for v in visual.get("videos",[])):
            raise ValueError("Visual review is stale")
        if not any(a.get("video_sha256")==sha and a.get("status")=="passed" for a in audio):
            raise ValueError("Audio review is absent or stale")
        verify_companions(video)
        video["status"]="finalized_local_review"
        video["finalized_at"]=now()
    write_json(safe_relative("outputs/manifest.json"),manifest)
    # Finalization only changes release status; update QA's manifest binding to that exact state.
    if 'input_hashes' in qa:
        qa['input_hashes']['outputs/manifest.json']=digest(ROOT/'outputs/manifest.json')
        write_json(ROOT/'outputs/qa.json',qa)
    result={"at":now(),"event_id":config()["id"],"status":"complete_local_delivery","videos":manifest["videos"],
            **counts,
            "qa":"outputs/qa.json","visual_review":"outputs/visual-review.json","actual_jev_inference":False,
            "scope":"Bounded public-source collection with documented social/broadcaster access gaps. No exhaustive coverage claim.",
            "publication":"Not published; source footage reuse clearance unverified", "user_playback_acceptance":"Not inferred; user can review finished edits"}
    write_json(safe_relative("outputs/delivery.json"),result)
    log("finalize","complete",videos=len(manifest['videos']),source_records=len(catalog["sources"]),assets=len(catalog["assets"]))
    return result
