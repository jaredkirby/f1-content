import hashlib
import json
import math
from pathlib import Path
import re
import uuid
from PIL import Image, ImageDraw, ImageFont
from .core import ROOT, config, digest, ensure_space, log, now, probe, read_json, run, write_json, safe_relative
from .video_plan import plans

BG = (9, 17, 29, 255)
PANEL = (18, 31, 47, 255)
WHITE = (237, 243, 248, 255)
MUTED = (159, 180, 195, 255)
ACCENT = (183, 246, 93, 255)
ORANGE = (255, 175, 85, 255)
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)

def wrapped(draw, text, x, y, width, size, color=WHITE, bold=False, spacing=8):
    face = font(size, bold)
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split():
            proposed = (line + " " + word).strip()
            if line and draw.textlength(proposed, font=face) > width:
                draw.text((x,y),line,font=face,fill=color)
                y += size + spacing
                line = word
            else:
                line = proposed
        draw.text((x,y),line,font=face,fill=color)
        y += size + spacing
    return y

def chart(draw, kind, box, editorial):
    x,y,w,h=box
    draw.rounded_rectangle((x,y,x+w,y+h),radius=14,fill=PANEL)
    if kind in ('qualifying','q1','q2'):
        rows=editorial['results'][:5] if kind=='qualifying' else sorted([r for r in editorial['results'] if r.get(kind+'_seconds')],key=lambda r:r[kind+'_seconds'])[:5]
        draw.text((x+25,y+20),'QUALIFYING CLASSIFICATION' if kind=='qualifying' else kind.upper()+' / FASTEST FIVE',font=font(20,True),fill=MUTED)
        line_h=min(66,(h-90)/max(1,len(rows)))
        for i,row in enumerate(rows):
            yy=y+70+i*line_h
            draw.text((x+25,yy),f"{i+1:02d}",font=font(26,True),fill=ACCENT)
            label=row['driver'].split()[-1].upper()
            draw.text((x+85,yy),label,font=font(24,True),fill=WHITE)
            value=(row.get('q3') if row['position']==1 else f"+{row['gap_seconds']:.3f}s") if kind=='qualifying' else row[kind]
            tw=draw.textlength(value,font=font(23,True))
            draw.text((x+w-25-tw,yy),value,font=font(23,True),fill=WHITE)
        draw.text((x+25,y+h-35),'FIA final qualifying / not the race grid',font=font(16),fill=MUTED)
    elif kind=='sectors':
        comparison=editorial['insights']['sector_comparison']
        leclerc=next(r for r in comparison['comparisons'] if r['driver_number']==16)
        draw.text((x+25,y+20),'LECLERC RELATIVE TO VERSTAPPEN',font=font(20,True),fill=WHITE)
        draw.text((x+25,y+52),'Best Q3 laps / negative means faster',font=font(17),fill=MUTED)
        for i,value in enumerate(leclerc['delta_to_verstappen_seconds']):
            yy=y+112+i*66
            draw.text((x+25,yy),f'SECTOR {i+1}',font=font(23,True),fill=MUTED)
            text=f'{value:+.3f}s'; tw=draw.textlength(text,font=font(30,True))
            draw.text((x+w-25-tw,yy-5),text,font=font(30,True),fill=WHITE)
        draw.text((x+25,y+h-36),'Net +0.054s / OpenF1 laps + FIA result',font=font(17),fill=MUTED)
    elif kind=='decision':
        draw.text((x+25,y+22),'SAINZ / HULKENBERG / TURN 5',font=font(20,True),fill=MUTED)
        wrapped(draw,'IMPEDING FOUND.\nNO PENALTY APPLIED.',x+25,y+82,w-50,32,bold=True,spacing=12)
        wrapped(draw,'Extraordinary mitigation: inconsistent timing information supplied to the teams.',x+25,y+220,w-50,23,color=MUTED)
        draw.text((x+25,y+h-36),'FIA Doc 73 / published decision',font=font(17),fill=MUTED)
    elif kind in ("results", "podium"):
        rows=editorial["results"][:5] if kind=="results" else editorial["results"][2:4]
        draw.text((x+25,y+20),"FINAL CLASSIFICATION" if kind=="results" else "THE PODIUM MARGIN",font=font(20,True),fill=MUTED)
        line_h = min(66, (h-90)/len(rows))
        for i,row in enumerate(rows):
            yy=y+70+i*line_h
            draw.text((x+25,yy),f"{row['position']:02d}",font=font(28,True),fill=ACCENT)
            draw.text((x+85,yy),row["driver"],font=font(25,True),fill=WHITE)
            value="WINNER" if row["position"]==1 else f"+{row['gap_seconds']:.3f}s"
            tw=draw.textlength(value,font=font(24,True))
            draw.text((x+w-25-tw,yy+2),value,font=font(24,True),fill=ORANGE)
        draw.text((x+25,y+h-35),"FIA Doc 66 / 10 October 2026",font=font(17),fill=MUTED)
    elif kind=="gap":
        rows=[r for r in editorial["insights"]["lap_finish_gaps"] if r["lap"]>=7 and "HAM" in r]
        draw.text((x+25,y+18),"HAMILTON'S GAP TO VERSTAPPEN",font=font(20,True),fill=WHITE)
        draw.text((x+25,y+48),"Derived timing · seconds · official final gap 2.591s",font=font(16),fill=MUTED)
        left,top,right,bottom=x+60,y+105,x+w-40,y+h-65
        ceiling=max(6, max((r["HAM"] for r in rows),default=0)+.5)
        for value in (0,2,4,6):
            yy=bottom-(bottom-top)*value/ceiling
            draw.line((left,yy,right,yy),fill=(49,65,80),width=1)
            draw.text((x+25,yy-10),str(value),font=font(17),fill=MUTED)
        points=[(left+(r["lap"]-7)/13*(right-left),bottom-r["HAM"]/ceiling*(bottom-top)) for r in rows]
        if len(points)>1:draw.line(points,fill=ACCENT,width=5)
        for xx,yy in points:draw.ellipse((xx-4,yy-4,xx+4,yy+4),fill=ACCENT)
        for lap in (7,10,15,20):
            xx=left+(lap-7)/13*(right-left)
            draw.text((xx-12,bottom+14),str(lap),font=font(17),fill=MUTED)
        draw.text((x+w-75,y+h-30),"LAP",font=font(16,True),fill=MUTED)

def layout(format_name):
    if format_name=="vertical":
        return (720,1280),(0,285,720,406)
    return (1280,720),(36,145,832,468)

def overlay_image(format_name, scene, caption, index, total, editorial, progress, held):
    (w,h), video_box=layout(format_name)
    im=Image.new("RGBA",(w,h),BG); d=ImageDraw.Draw(im)
    vertical=format_name=="vertical"
    margin=36
    d.rectangle((margin,34,margin+44,40),fill=ACCENT)
    d.text((margin+58,24),"RACE NOTES  /  SINGAPORE",font=font(20,True),fill=WHITE)
    from datetime import date as date_type
    cfg=config()
    date=date_type.fromisoformat(cfg['event_date']).strftime('%d %b %Y').upper()
    if not vertical: date+='  ·  '+cfg['session_name'].upper()
    tw=d.textlength(date,font=font(16))
    d.text((w-margin-tw,52 if vertical else 28),date,font=font(16),fill=MUTED)
    if vertical:
        wrapped(d,scene["title"],margin,100,w-2*margin,45,bold=True,spacing=4)
        d.text((margin,238),scene["kicker"],font=font(18,True),fill=ACCENT)
    else:
        wrapped(d,scene["title"].replace("\n"," "),margin,71,w-2*margin,32,bold=True)
        d.text((margin,116),scene["kicker"],font=font(16,True),fill=ACCENT)
    x,y,vw,vh=video_box
    if scene.get("asset_id"):
        d.rectangle((x,y,x+vw-1,y+vh-1),fill=(0,0,0,0))
    else:
        chart(d,scene.get("chart") or ('qualifying' if cfg.get('session_type')=='qualifying' else 'results'),video_box,editorial)
    credit="Footage: Formula 1" if scene.get("asset_id") else "Original graphic · FIA / OpenF1 data"
    if held: credit += " · end frame held"
    d.text((margin,713 if vertical else 618),credit,font=font(16),fill=MUTED)
    if vertical:
        my=772
        for label,value in scene["metrics"][:2]:
            d.text((margin,my),label,font=font(17,True),fill=MUTED)
            wrapped(d,value,margin,my+27,w-2*margin,32,bold=True,color=ACCENT)
            my+=112
        d.rounded_rectangle((24,1022,w-24,1193),radius=14,fill=PANEL)
        wrapped(d,caption,42,1044,w-84,30,bold=True,spacing=7)
        d.text((margin,1215),f"{index+1:02d} / {total:02d}   {scene['id'].upper()}",font=font(17),fill=MUTED)
        bar_y=1264
    else:
        my=170
        for label,value in scene["metrics"][:3]:
            wrapped(d,label,902,my,340,15,bold=True,color=MUTED,spacing=5)
            wrapped(d,value,902,my+30,340,26,bold=True,color=ACCENT,spacing=5)
            my+=128
        d.rounded_rectangle((24,648,w-24,709),radius=12,fill=PANEL)
        wrapped(d,caption,42,658,w-84,24,bold=True,spacing=2)
        d.text((1122,615),f"{index+1:02d} / {total:02d}",font=font(16),fill=MUTED)
        bar_y=714
    d.rectangle((0,bar_y,int(w*progress),bar_y+6),fill=ACCENT)
    return im

def phrases(text, max_words=12):
    parts=[]
    for sentence in re.split(r"(?<=[.!?])\s+",text):
        words=sentence.split()
        while words:
            # Split long sentences near clause boundaries when possible.
            count=min(max_words,len(words))
            if len(words)>max_words:
                for i in range(max_words-1, max(4,max_words-5),-1):
                    if words[i-1].endswith((",",":",";")):
                        count=i;break
            parts.append(" ".join(words[:count]));words=words[count:]
    return parts

def srt_time(seconds):
    ms=round(seconds*1000);hours,ms=divmod(ms,3600000);minutes,ms=divmod(ms,60000);seconds,ms=divmod(ms,1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"

def concat_file(path, entries):
    path.write_text("ffconcat version 1.0\n"+"".join("file '"+str(p).replace("'", "'\\''")+"'\n"+(f"duration {dur:.6f}\n" if dur is not None else "") for p,dur in entries))

def checked_scene(scene,editorial,asset,require_bindings=False,review_sha=None):
    """Enforce editorial links and the explicitly reviewed range before rendering."""
    event_map={e['id']:e for e in editorial.get('timeline',[])}
    if not scene.get('event_ids') or set(scene['event_ids'])-event_map.keys():
        raise ValueError('Scene references unknown or missing event IDs')
    if not scene.get('narration','').strip():raise ValueError('Scene narration is empty')
    if not asset:return None
    start=scene.get('source_in',0)
    matches=[m for eid in scene['event_ids'] for m in event_map[eid].get('media_matches',[]) if m['source_id']==scene['source_id'] and m['in']<=start<m['out']]
    if not matches:raise ValueError('Scene has no reviewed event-to-footage association: '+scene['id'])
    for match in matches:
        if (match.get('source_sha256') is not None and match['source_sha256']!=asset.get('sha256')):
            raise ValueError('Scene association refers to different source bytes')
        if match.get('asset_id') is not None and match['asset_id']!=asset.get('id'):
            raise ValueError('Scene association refers to a different asset')
        if require_bindings and (match.get('source_sha256')!=asset.get('sha256')
                                 or match.get('asset_id')!=asset.get('id')
                                 or not review_sha or match.get('review_receipt_sha256')!=review_sha
                                 or asset.get('review_receipt_sha256')!=review_sha):
            raise ValueError('Scene association has missing or stale source/review bindings')
    allowed_end=scene.get('source_out_limit',max(m['out'] for m in matches))
    if (any(type(v) not in (int,float) or not math.isfinite(v) for v in (start,allowed_end))
            or not 0<=start<allowed_end<=asset['duration']+.025):
        raise ValueError('Scene source interval is outside the asset')
    if not any(start>=m['in'] and allowed_end<=m['out']+.001 for m in matches):
        raise ValueError('Scene exceeds associated reviewed interval')
    # New catalog receipts contain reviewed ranges; legacy Sprint matches remain supported.
    if 'reviewed_ranges' in asset and not any(r['in']<=start and allowed_end<=r['out']+.001 for r in asset['reviewed_ranges']):
        raise ValueError('Scene exceeds the visual review receipt')
    return allowed_end

def render_one(format_name, plan, editorial, catalog, output_dir=None):
    from .narration import selected_narration
    narration = selected_narration(format_name, ROOT)
    ensure_space(350*1024*1024)
    if format_name not in ('vertical','landscape'):raise ValueError('Unsupported render format')
    work=safe_relative(ROOT/"outputs/work"/format_name); work.mkdir(parents=True,exist_ok=True)
    asset_map={s["id"]: next((a for a in catalog["assets"] if a["id"]==s.get("asset_id")),None) for s in catalog["sources"]}
    scenes=plan["scenes"]
    edl=[]; caption_records=[]; elapsed=0; movies=[]
    for i,scene in enumerate(scenes):
        ensure_space(90*1024*1024)
        scene=dict(scene)
        if not re.fullmatch(r'[a-zA-Z0-9_-]+',scene.get('id','')):raise ValueError('Unsafe scene id')
        asset=asset_map.get(scene.get("source_id"))
        if scene.get("source_id") and not asset:
            raise ValueError(f"Required source not downloaded: {scene['source_id']}")
        allowed_end=checked_scene(scene,editorial,asset,require_bindings=True,
                                  review_sha=digest(safe_relative('research/media/clip_review.json')))
        if asset:
            scene['asset_id']=asset['id']
            scene['source_out_limit']=allowed_end
            scene['source_sha256']=asset['sha256']
            scene['review_receipt_sha256']=asset['review_receipt_sha256']
        speech=[]; duration=0
        if narration:
            row = narration['scenes'][i]
            if row['id'] != scene['id']:
                raise ValueError('Prepared narration scene order changed')
            wav = safe_relative(row['audio']['path'])
            duration = row['duration']
            cursor = 0
            for cue in row['captions']:
                if cue['start'] > cursor:
                    speech.append((wav, cue['start']-cursor, '', cursor))
                speech.append((wav, cue['end']-cue['start'], cue['text'], cue['start']))
                cursor = cue['end']
            if cursor < duration:
                speech.append((wav, duration-cursor, '', cursor))
            scene['narration_audio'] = row['audio']
            scene['narration_effect_receipt'] = narration['effect_receipt']
        else:
            chunks=phrases(scene["narration"])
            for j,text in enumerate(chunks):
                key=hashlib.sha256(("Samantha|172|"+text).encode()).hexdigest()[:16]
                aiff=work/f"voice-{key}.aiff"
                if not aiff.exists() or aiff.stat().st_size < 500:
                    run(["say","-v","Samantha","-r","172","-o",aiff,text],timeout=60)
                audio_info=probe(aiff)
                if not audio_info.get("streams") or not audio_info.get("format",{}).get("duration"):
                    aiff.unlink(missing_ok=True)
                    raise RuntimeError("macOS speech service unavailable; generate narration with approved system access")
                seconds=float(audio_info["format"]["duration"])
                speech.append((aiff,seconds,text,duration))
                duration+=seconds
            # All scene boundaries land on the output frame grid to prevent cumulative caption drift.
            duration = math.ceil(duration * 24) / 24
            audio_list=work/f"{i:02}-audio.ffconcat"
            concat_file(audio_list,[(p,None) for p,_,_,_ in speech])
            wav=work/f"{i:02}-narration.wav"
            run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i",audio_list,"-ar","48000","-ac","1",wav])
        overlays=[]
        available=allowed_end-scene["source_in"] if asset else duration
        for j,(_,seconds,text,offset) in enumerate(speech):
            png=work/f"{i:02}-overlay-{j:02}.png"
            overlay_image(format_name,scene,text,i,len(scenes),editorial,(i+(offset+seconds)/duration)/len(scenes),offset+seconds>available).save(png)
            overlays.append((png,seconds))
            if text:
                caption_records.append({"start":elapsed+offset,"end":elapsed+offset+seconds,"text":text})
        overlay_list=work/f"{i:02}-overlay.ffconcat"
        concat_file(overlay_list,overlays+[(overlays[-1][0],None)])
        movie=work/f"{i:02}-{scene['id']}.mov"
        (w,h),(x,y,vw,vh)=layout(format_name)
        args=["ffmpeg","-v","error","-y"]
        if asset:
            args += ["-ss",str(scene["source_in"]),"-t",str(available),"-i",safe_relative(asset["original"])]
            base=f"[0:v]setpts=PTS-STARTPTS,scale={vw}:{vh}:force_original_aspect_ratio=decrease,pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration={duration},pad={w}:{h}:{x}:{y}:color=black[base]"
        else:
            args += ["-f","lavfi","-i",f"color=c=0x09111d:s={w}x{h}:r=24:d={duration}"]
            base="[0:v]setpts=PTS-STARTPTS[base]"
        args += ["-f","concat","-safe","0","-i",overlay_list,"-i",wav,
                 "-filter_complex",base+";[base][1:v]overlay=0:0:format=auto:eof_action=repeat,format=yuv420p[v];[2:a]apad[a]",
                 "-map","[v]","-map","[a]","-t",f"{duration:.6f}","-r","24","-frames:v",str(round(duration*24)),"-c:v","libx264","-preset","fast","-crf","22","-c:a","pcm_s16le","-ar","48000","-video_track_timescale","24000","-movflags","+faststart",movie]
        run(args,timeout=600)
        movies.append(movie)
        scene.update(timeline_in=round(elapsed,3),timeline_out=round(elapsed+duration,3),duration=round(duration,3),
                     source_out=min(scene["source_in"]+duration,allowed_end) if asset else None,
                     footage_used_seconds=min(duration,available) if asset else 0,
                     held_end_frame_seconds=max(0,duration-available) if asset else 0,
                     claim_source_ids=sorted({s for e in editorial["timeline"] if e["id"] in scene["event_ids"] for s in e["source_ids"]}),
                     rendered_scene=str(movie.relative_to(ROOT)))
        edl.append(scene);elapsed+=duration
        print(f"{format_name}: {i+1}/{len(scenes)} {scene['id']} ({duration:.1f}s)",flush=True)
    joined=work/"scenes.ffconcat";concat_file(joined,[(p,None) for p in movies])
    outdir=safe_relative(output_dir or ROOT/'outputs')
    outdir.mkdir(parents=True,exist_ok=True)
    prefix=config().get('output_prefix','singapore-sprint-2026')
    if not re.fullmatch(r'[a-z0-9-]+',prefix):raise ValueError('Unsafe output prefix')
    out=outdir/f"{prefix}-{format_name}.mp4"
    pending=out.with_suffix(".rendering.mp4")
    # One audio normalization pass; per-scene narration is already aligned to its caption frames.
    run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i",joined,"-c:v","copy","-af","loudnorm=I=-16:TP=-1.5:LRA=11","-c:a","aac","-b:a","160k","-ar","48000","-movflags","+faststart",pending])
    if not probe(pending).get("streams"):
        raise ValueError("Final render has no streams")
    pending.replace(out)
    srt=out.with_suffix(".srt")
    srt.write_text("\n\n".join(f"{i+1}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}" for i,c in enumerate(caption_records))+"\n")
    script=out.with_suffix(".txt");script.write_text("\n\n".join(s["title"].replace("\n"," ")+"\n"+s["narration"] for s in scenes)+"\n")
    thumbnail=out.with_suffix(".jpg")
    run(["ffmpeg","-v","error","-y","-ss",str(min(2, elapsed/2)),"-i",out,"-frames:v","1",thumbnail])
    full_info=probe(out)
    record={"format":format_name,"title":plan["title"],"idea_id":plan["idea_id"],"path":str(out.relative_to(ROOT)),
            "captions":str(srt.relative_to(ROOT)),"script":str(script.relative_to(ROOT)),"thumbnail":str(thumbnail.relative_to(ROOT)),
            "sha256":digest(out),"bytes":out.stat().st_size,"duration":float(full_info["format"]["duration"]),"width":layout(format_name)[0][0],"height":layout(format_name)[0][1],
            "status":"rendered_awaiting_QA","narration":"macOS Samantha, original editorial script; phrase-aligned captions",
            "sources":sorted({s["source_id"] for s in edl if s.get("source_id")}),"publication_status":"local_review; footage reuse clearance unverified"}
    record['companion_sha256']={k:digest(ROOT/record[k]) for k in ('captions','script','thumbnail')}
    if narration:
        backend = {'say': 'macOS Samantha', 'imported': 'Imported narration', 'elevenlabs': 'ElevenLabs narration'}[narration['provider']['kind']]
        effect = 'Robot Voice Lab vocoder' if narration['effect']['kind'] == 'robot_vocoder' else 'clean voice'
        record['narration'] = f"{backend}; {effect}; measured caption timings"
        record['narration_receipts'] = [narration['source_result'], narration['effect_receipt']]
        record['model_runs'] = narration['model_runs']
    return record,edl

def render(selection="both"):
    global BG,PANEL,WHITE,MUTED,ACCENT,ORANGE
    if config().get('graphic_theme')=='monochrome':
        BG=(17,17,17,255);PANEL=(35,35,35,255);WHITE=(245,245,245,255)
        MUTED=(185,185,185,255);ACCENT=WHITE;ORANGE=WHITE
    editorial=read_json(ROOT/"data/processed/editorial.json")
    catalog=read_json(ROOT/"data/processed/catalog.json")
    if editorial.get("event",{}).get("id") != config()["id"] or catalog.get("event_id") != config()["id"]:
        raise ValueError("Render inputs have mismatched event identity")
    from .validate import required_render_inputs, input_path, verify_bindings
    inputs={path:digest(input_path(path)) for path in required_render_inputs()}
    # Read the actual render objects after capturing hashes; a concurrent edit
    # must fail the final recheck instead of receiving a hash for different text.
    editorial=read_json(ROOT/'data/processed/editorial.json')
    catalog=read_json(ROOT/'data/processed/catalog.json')
    if editorial.get('event',{}).get('id')!=config()['id'] or catalog.get('event_id')!=config()['id']:
        raise ValueError('Render inputs changed event identity')
    for asset in catalog["assets"]:
        if digest(safe_relative(asset["original"])) != asset["sha256"]:
            raise ValueError("Render input hash mismatch: " + asset["id"])
    manifest=read_json(ROOT/"outputs/manifest.json",{"event_id":config()["id"],"videos":[]})
    edit_plan=read_json(safe_relative(manifest.get('edit_plan','outputs/edit-plan.json')),{"event_id":config()["id"],"edits":{}})
    if manifest.get("event_id") != config()["id"] or edit_plan.get("event_id") != config()["id"]:
        raise ValueError("Existing output manifest or edit-plan event identity mismatch")
    requested=["vertical","landscape"] if selection=="both" else [selection]
    selected_plans=plans()
    for name in requested:
        if name not in selected_plans:raise ValueError('Requested format has no researched plan: '+name)
    run_id=uuid.uuid4().hex[:12]
    output_dir=safe_relative(ROOT/'outputs/versions'/run_id)
    output_dir.mkdir(parents=True,exist_ok=True)
    for name in requested:
        record,edl=render_one(name,selected_plans[name],editorial,catalog,output_dir)
        record['input_hashes']=dict(inputs)
        manifest["videos"]=[v for v in manifest["videos"] if v["format"]!=name]+[record]
        manifest["rendered_at"]=now();edit_plan["edits"][name]=edl
        log("render","complete",video=record)
    # Immutable output bundle; manifest is the single authoritative commit point.
    edl_path=output_dir/'edit-plan.json'
    write_json(edl_path,edit_plan)
    verify_bindings(inputs,required_render_inputs(),'Render inputs changed during assembly')
    manifest.update(run_id=run_id,edit_plan=str(edl_path.relative_to(ROOT)),edit_plan_sha256=digest(edl_path),input_hashes=inputs)
    write_json(safe_relative('outputs/manifest.json'),manifest)
    write_json(safe_relative('outputs/edit-plan.json'),edit_plan)  # convenient non-authoritative copy
    return manifest
