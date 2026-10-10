"""Build a portable timeline from the canonical session evidence and reviewed media."""
from pathlib import Path
from importlib.resources import files
import hashlib
import html
import json
import re
import shutil
import uuid
from .core import ROOT, config, digest, ensure_space, probe, read_json, run, safe_relative, write_json

def esc(value):return html.escape(str(value or ''),quote=True)
def link(url,label,cls=''):return f'<a href="{esc(url)}" class="{esc(cls)}">{esc(label)}</a>'
def stamp(n):
    ms=round(n*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
def secs(s):return sum(float(n)*60**i for i,n in enumerate(reversed(s.replace(',','.').split(':'))))
def trim_captions(source,start,end,target):
    tracks=[t for t in source.get('caption_tracks',[]) if t.get('status')=='downloaded']
    if not tracks:return False
    path=safe_relative(tracks[0]['local_path'])
    if not path.is_file() or not tracks[0].get('sha256') or digest(path)!=tracks[0]['sha256']:raise ValueError('Caption integrity mismatch')
    text=path.read_text()
    rx=r'((?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s+-->\s+((?:\d{2}:)?\d{2}:\d{2}\.\d{3})[^\n]*\n(.*?)(?=\n\s*\n|\Z)'
    cues=[]
    for a,b,words in re.findall(rx,text,re.S):
        left,right=max(start,secs(a)),min(end,secs(b))
        if right>left:cues.append(f'{stamp(left-start)} --> {stamp(right-start)}\n{words.strip()}')
    if cues:target.write_text('WEBVTT\n\n'+'\n\n'.join(cues)+'\n')
    return bool(cues)

def viewing_copy(source,target,start=0,end=None,width=480,maxrate="250k",audio_rate="40k"):
    info=probe(source);duration=float(info['format']['duration']) if end is None else end-start
    recipe={'source_sha256':digest(source),'start':start,'end':end,'width':width,'crf':29,'maxrate':maxrate,'bufsize':'700k','audio_bitrate':audio_rate,'version':2}
    receipt=target.with_suffix('.receipt.json');old=read_json(receipt,{})
    if target.is_file() and old.get('recipe')==recipe and old.get('sha256')==digest(target):return old
    ensure_space(80*1024**2)
    pending=target.with_name('.'+target.stem+'-'+uuid.uuid4().hex[:8]+'.mp4')
    try:
        args=['ffmpeg','-v','error','-xerror','-y','-ss',str(start)]
        if end is not None:args+=['-t',str(end-start)]
        args+=['-i',source,'-vf',f'scale={width}:-2','-c:v','libx264','-preset','fast','-crf','29','-maxrate',maxrate,'-bufsize','700k','-pix_fmt','yuv420p','-c:a','aac','-b:a',audio_rate,'-movflags','+faststart',pending]
        run(args)
        actual=float(probe(pending)['format']['duration'])
        if abs(actual-duration)>.3:raise ValueError('Viewing copy duration mismatch')
        if pending.stat().st_size>=25*1024**2:raise ValueError('Viewing copy exceeds hosting file limit')
        run(['ffmpeg','-v','error','-xerror','-i',pending,'-f','null','-'])
        pending.replace(target)
        result={'recipe':recipe,'sha256':digest(target),'bytes':target.stat().st_size,'duration':actual,'validation':'full_decode'}
        write_json(receipt,result);return result
    finally:pending.unlink(missing_ok=True)

def build():
    cfg=config()
    if cfg['id']!='2026-singapore-qualifying':raise ValueError('This curated timeline presentation requires Singapore Main Qualifying; provide a session-specific presentation before reuse')
    editorial=read_json(ROOT/'data/processed/editorial.json');catalog=read_json(ROOT/'data/processed/catalog.json')
    manifest=read_json(ROOT/'outputs/manifest.json',{})
    if editorial['event']['id']!=cfg['id'] or catalog['event_id']!=cfg['id']:raise ValueError('Timeline input identity mismatch')
    if manifest and manifest.get('event_id')!=cfg['id']:raise ValueError('Timeline render identity mismatch')
    from .validate import verify_render_bindings, verify_bindings, QA_BASE_INPUTS
    if manifest:
        captured=verify_render_bindings(manifest)
        required=set(cfg.get('formats',['vertical','landscape']))
        if {v['format'] for v in manifest['videos']}!=required or len(manifest['videos'])!=len(required):raise ValueError('Timeline requires every requested format')
        if all(v.get('status','').startswith('finalized') for v in manifest['videos']):
            qa=read_json(ROOT/'outputs/qa.json',{})
            if qa.get('status')!='passed' or qa.get('errors') or qa.get('event_id')!=cfg['id']:raise ValueError('Timeline finalization lacks current QA')
            verify_bindings(qa.get('input_hashes',{}),QA_BASE_INPUTS|set(captured),'Timeline technical QA')
            if qa.get('edit_plan_sha256')!=manifest.get('edit_plan_sha256') or digest(safe_relative(manifest['edit_plan']))!=manifest.get('edit_plan_sha256'):raise ValueError('Timeline QA has stale edit plan')
    site=ROOT/'sites/timeline';out=site/'dist'
    for name in ('clips','posters','captions','edits','data'):(out/name).mkdir(parents=True,exist_ok=True)
    assets={a['id']:a for a in catalog['assets']};sources={s['id']:s for s in catalog['sources']};evidence={s['id']:s for s in editorial['sources']}
    clips=[];seen={}
    from .analyze_session import within_review
    review_sha=digest(ROOT/'research/media/clip_review.json')
    for event in editorial['timeline']:
        for match in event['media_matches']:
            asset=assets[match['asset_id']];source=sources[match['source_id']]
            if match.get('source_sha256')!=digest(safe_relative(asset['original'])) or match.get('review_receipt_sha256')!=review_sha or asset.get('review_receipt_sha256')!=review_sha or not within_review(asset,match['in'],match['out']):
                raise ValueError('Stale or unreviewed timeline clip')
            key=(match['source_id'],match['in'],match['out'])
            if key in seen:
                seen[key]['event_ids'].append(event['id']);continue
            cid='clip-'+hashlib.sha256(repr(key).encode()).hexdigest()[:12]
            target=out/'clips'/f'{cid}.mp4'
            receipt=viewing_copy(safe_relative(asset['original']),target,match['in'],match['out'])
            poster=out/'posters'/f'{cid}.jpg'
            poster_receipt=poster.with_suffix('.receipt.json')
            if not poster.is_file() or read_json(poster_receipt,{}).get('clip_sha256')!=receipt['sha256'] or read_json(poster_receipt,{}).get('sha256')!=digest(poster):
                run(['ffmpeg','-v','error','-y','-ss',str(min(3,(match['out']-match['in'])/2)),'-i',target,'-frames:v','1','-vf','scale=800:-2',poster])
                write_json(poster_receipt,{'clip_sha256':receipt['sha256'],'sha256':digest(poster)})
            caption=f'captions/{cid}.vtt'
            if not trim_captions(source,match['in'],match['out'],out/caption):caption=None
            clip={'id':cid,'src':f'clips/{cid}.mp4','poster':f'posters/{cid}.jpg','caption':caption,'event_ids':[event['id']],
                  'title':match.get('label','Selected highlight').replace('_',' ').capitalize(),'note':match.get('observation',''),
                  'source_id':source['id'],'source_url':source['url'],'source_title':source.get('title','Formula 1'),
                  'source_in':match['in'],'source_out':match['out'],'duration':round(match['out']-match['in'],2),
                  'original_sha256':asset['sha256'],'sha256':receipt['sha256']}
            clips.append(clip);seen[key]=clip
            print('Timeline clip:',clip['title'],flush=True)
    edits=[]
    for video in manifest.get('videos',[]):
        if digest(safe_relative(video['path']))!=video['sha256']:raise ValueError('Rendered video changed')
        shape=video['format'];src=f'edits/{shape}.mp4'
        viewing_copy(safe_relative(video['path']),out/src,width=540 if shape=='vertical' else 960,maxrate='350k',audio_rate='48k')
        for field,folder,suffix in [('thumbnail','posters','.jpg'),('script','edits','-script.txt')]:shutil.copyfile(safe_relative(video[field]),out/f'{folder}/{shape}{suffix}')
        srt=safe_relative(video['captions']).read_text()
        (out/f'captions/{shape}.vtt').write_text('WEBVTT\n\n'+re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})',r'\1.\2',srt))
        edits.append({'id':shape,'src':src,'poster':f'posters/{shape}.jpg','caption':f'captions/{shape}.vtt','title':video['title'],
                      'duration':video['duration'],'note':'Original narrated summary. Broadcast footage credited in the edit.','format':shape,'finalized':video.get('status','').startswith('finalized')})
    data=[]
    for original in editorial['data_assets']:
        item=dict(original);item['files']=[]
        paths=item.get('local_paths',[])+([item['local_path']] if item.get('local_path') else [])
        for path in dict.fromkeys(paths):
            source=safe_relative(path);name='data/'+item['id'].lower()+'-'+source.name
            shutil.copyfile(source,out/name);item['files'].append({'path':name,'name':source.name,'sha256':digest(source)})
        data.append(item)
    for name,key in [('timeline','timeline'),('results','results'),('ranked-stories','ideas')]:write_json(out/f'data/{name}.json',editorial[key])
    write_json(out/'data/clip-manifest.json',clips)
    write_json(out/'data/source-index.json',[{k:s.get(k) for k in ('id','title','url','publisher','kind','sha256')} for s in editorial['sources']+catalog['sources']])
    data_by_id={a['id']:a for a in data};events={e['id']:e for e in editorial['timeline']};ideas=sorted(editorial['ideas'],key=lambda a:a['rank'])
    anchors={i['anchor_event_id']:i for i in ideas};highlights={'Q02','Q06','Q08','Q10','Q12'}
    def figure(c):
        track=f'<track kind="captions" src="{esc(c["caption"])}" srclang="en" label="English">' if c.get('caption') else ''
        credit=link(c['source_url'],'Formula 1 · Original source ↗') if c.get('source_url') else link(c['src'],'Download MP4 ↗')
        provenance=f'Source {c["source_in"]:g}–{c["source_out"]:g}s · ' if 'source_in' in c else ''
        return f'<figure class="clip {esc(c.get("format",""))}"><video controls playsinline preload="none" poster="{esc(c["poster"])}" src="{esc(c["src"])}">{track}</video><figcaption><strong>{esc(c["title"])}</strong><span class="clip-meta">{provenance}{c["duration"]:.1f}s</span><span class="credit">{credit}</span><p class="clip-note">{esc(c["note"])}</p><p class="video-error" hidden>Playback failed. {link(c["src"],"Open the video directly")}</p></figcaption></figure>'
    def data_block(ids):
        selected={a for eid in ids for a in events[eid].get('required_asset_ids',[]) if a in data_by_id}
        rows=[]
        for aid in sorted(selected):
            a=data_by_id[aid]
            title=a.get('title') or a.get('description',aid)
            rows.append('<li><strong>'+esc(title)+'</strong>'+''.join('<small>'+link(f['path'],f['name']+' ↗')+'</small>' for f in a['files'])+'</li>')
        claims={sid for eid in ids for sid in events[eid]['source_ids']}
        return '<div class="detail-block"><p class="label">Supporting data & documents</p><ul class="asset-list">'+''.join(rows)+'</ul><div class="source-links">'+''.join(link(evidence[sid]['url'],evidence[sid].get('title',sid)+' ↗') for sid in sorted(claims))+'</div></div>'
    edl=read_json(safe_relative(manifest['edit_plan']),{}) if manifest.get('edit_plan') else {}
    def story_block(idea):
        beats='';offset=0
        for beat in idea['outline']:
            duration=beat.get('duration_seconds',0)
            beats+=f'<li class="beat"><span class="beat-time">{offset:02}–{offset+duration:02}s</span><div><strong>{esc(beat["segment"])}</strong><p>{esc(beat["narration"])}</p>'+''.join(link('#'+e,events[e]['phase']+' · '+events[e]['title']) for e in beat['event_ids'])+'</div></li>'
            offset+=duration
        return '<div class="detail-block"><p class="label">The story</p><p class="story-copy">'+esc(idea['story'])+'</p><p class="label">Editorial outline · proposed beat lengths</p><ol class="beat-list">'+beats+'</ol></div>'
    def event_html(e):
        idea=anchors.get(e['id']);ids=idea['event_ids'] if idea else [e['id']]
        classes='event'+(' highlight' if e['id'] in highlights else '')+(' featured' if e['id'] in {'Q08','Q10'} else '')
        tm=e.get('local_time') or 'Phase only'
        if 'T' in tm:tm=tm.split('T')[1].split('+')[0][:8]
        phase_label={'pre_session':'Session opens','post_session':'After qualifying'}.get(e['phase'],e['phase'])
        precision_label={'session_started_message':'Session start','phase_only':'Phase only','derived_best_lap_finish':'Derived lap finish','embedded_incident_time_in_later_message':'Incident time','provisional_grid_document_issue_time':'11 Oct · Document issued'}.get(e.get('time_precision'),e.get('time_precision','Phase only').replace('_',' '))
        teaser=''
        teaser_copy=(idea['angle'].split('. ')[0]+'.') if idea else ''
        if idea:teaser=f'<div class="story-teaser" id="story-{idea["id"]}"><span class="rank">{idea["rank"]:02}</span><div><p class="label">Recommended story</p><h4>{esc(idea["title"])}</h4><p>{esc(teaser_copy)}</p><p class="story-status">'+('Two summary edits below' if idea['id']=='QI01' else 'Proposed story · ready for editorial assembly')+'</p></div></div>'
        selected=[c for c in clips if set(c['event_ids'])&set(ids)]
        media='<div class="detail-block"><p class="label">Selected video & reactions</p><div class="media-grid">'+''.join(figure(c) for c in selected)+'</div></div>' if selected else '<div class="detail-block"><p>No separately reviewed footage is matched to this event. Use the supporting data and original graphics.</p></div>'
        if e['id']=='Q06':media='<p class="fine">The selected interview is Sainz’s account. No on-track clip of the impediment was acquired; the finding and outcome come from the FIA decision.</p>'+media
        related=[i for i in ideas if e['id'] in i['event_ids'] and i is not idea]
        return f'<li class="{classes}" id="{e["id"]}" data-highlight="{str(e["id"] in highlights).lower()}" data-story="{str(bool(idea)).lower()}"><div class="event-clock"><b>{esc(tm)}</b><span>{esc(phase_label)}</span><em>{esc(precision_label)}</em></div><article class="event-shell"><div class="event-intro"><div class="label">{esc(phase_label)}'+(' <span class="tag">Highlight</span>' if e['id'] in highlights else '')+f'</div><h3>{esc(e["title"])}</h3><p>{esc(e.get("narrative",e["summary"]))}</p><p class="consequence">{esc(e.get("consequence",""))}</p></div>'+teaser+'<details class="event-details"><summary>'+('Explore story, outline, video & data' if idea else 'Explore video & evidence')+'</summary><div class="detail-body">'+(story_block(idea) if idea else '')+media+data_block(ids)+('<p class="related">Also in: '+', '.join(link('#story-'+i['id'],i['title']) for i in related)+'</p>' if related else '')+'</div></details></article></li>'
    rendered_outline=''
    if edl:
        write_json(out/'data/edit-plan.json',edl)
        for shape,scenes in edl.get('edits',{}).items():
            sequence=''.join(f'<li class="beat"><span class="beat-time">{a["timeline_in"]:.0f}–{a["timeline_out"]:.0f}s</span><div><strong>{esc(a["title"].replace(chr(10)," "))}</strong><p>{esc(a["narration"])}</p></div></li>' for a in scenes)
            rendered_outline+=f'<details class="event-details"><summary>{shape.capitalize()} · final narration and edit sequence</summary><div class="detail-body"><ol class="beat-list">{sequence}</ol><div class="source-links">'+link(f'edits/{shape}-script.txt','Narration script ↗')+link(f'captions/{shape}.vtt','Captions ↗')+link('data/edit-plan.json','Source edit decisions ↗')+'</div></div></details>'
    nav=''.join(link('#story-'+i['id'],f'{i["rank"]:02}  {i["title"]}') for i in ideas)
    rows=''.join('<tr><td>'+str(r['position'] if r.get('classified',True) else 'NC')+'</td><td>'+esc(r['driver'])+'</td>'+''.join('<td class="mono">'+esc(r.get(q) or '—')+'</td>' for q in ('q1','q2','q3'))+'</tr>' for r in editorial['results'])
    resources=files('f1_pipeline').joinpath('resources')
    css=resources.joinpath('timeline.css').read_text(encoding='utf-8');js=resources.joinpath('timeline.js').read_text(encoding='utf-8')
    css+='\n.event-clock em{overflow-wrap:anywhere}.event-clock b{overflow-wrap:anywhere}.asset-list strong{font-size:13px}.table-wrap{overflow-x:auto}.clip-note{overflow-wrap:anywhere}\n'
    finalized=bool(edits) and all(e['finalized'] for e in edits)
    release='Finalized recaps' if finalized else 'Review copies'
    page=f'''<!doctype html><html lang="en" data-theme="auto"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>Singapore Qualifying · 54 thousandths</title><meta name="description" content="A sourced timeline of Singapore main qualifying. Explore the pole battle, recommended stories, reviewed video and official data."><style>{css}</style></head><body><a class="skip" href="#race-timeline">Skip to the session timeline</a><header class="top"><div class="top-inner"><a class="brand" href="#overview"><span class="brand-mark"></span>Session notes / Singapore</a><div class="theme js-only" role="group" aria-label="Color theme"><button data-set-theme="light">Light</button><button data-set-theme="dark">Dark</button><button data-set-theme="auto">Auto</button></div></div></header><div class="layout"><aside class="side"><p class="label">MAIN QUALIFYING / 10.10.26</p>{link('#race-timeline','The session timeline')}{link('#finished-edits','Watch the recaps')}<nav aria-label="Recommended stories"><p class="label">Stories by priority</p>{nav}</nav>{link('#classification','Final classification')}{link('#sources','Sources & coverage')}<p class="side-note">Q1 → Q2 → Q3<br>Marina Bay, Singapore.<br>All times UTC+8.<br><br>{len(events)} identified events.<br>{len(ideas)} prioritized stories.</p></aside><main><section class="hero" id="overview"><p class="label">10 October 2026 / Marina Bay Street Circuit</p><h1>Singapore qualifying.<br>54 thousandths.</h1><p class="lead">Hamilton led the opening phases. Verstappen delivered the lap that held. Leclerc came within a breath of pole.</p><p class="sublead">Follow the session from the first green light to the final classification. Open a recommended segment for its story, edit outline, video and supporting data.</p><div class="actions">{link('#race-timeline','Follow qualifying ↓','button primary')}{link('#finished-edits','Watch the recaps ↗','button')}</div><div class="hero-meta"><span><strong>0.054s</strong> pole margin</span><span><strong>{len(events)}</strong> events</span><span><strong>{len(ideas)}</strong> stories</span><span>Main Qualifying · session 11384</span></div></section><nav class="moments" aria-label="Key moments"><a class="moment" href="#Q03"><span class="label">Q1 + Q2</span><strong>Hamilton sets the pace ↗</strong><small>Ferrari leads both opening phases.</small></a><a class="moment" href="#Q08"><span class="label">Q3</span><strong>One lap that holds ↗</strong><small>Verstappen’s first run takes pole.</small></a><a class="moment" href="#Q12"><span class="label">After qualifying</span><strong>A different race grid ↗</strong><small>Russell’s penalty changes his starting place.</small></a></nav><details class="mobile-jump"><summary>Jump to a recommended story</summary><nav>{nav}</nav></details><section class="timeline-section" id="race-timeline"><div class="section-head"><div><p class="label">01 / Session timeline</p><h2>Qualifying, in sequence.</h2><p>Highlights mark decisive moments. Numbered story strips show the editorial priorities.</p></div><span class="fine">Session order · not to time scale</span></div><div class="filters js-only" role="group" aria-label="Filter timeline"><button class="filter" data-filter="all" aria-pressed="true">All events <span>{len(events)}</span></button><button class="filter" data-filter="highlight">Highlights <span>{len(highlights)}</span></button><button class="filter" data-filter="story">Stories <span>{len(ideas)}</span></button></div><p class="view-count" id="view-count" aria-live="polite">Showing {len(events)} of {len(events)} identified events · Times in Singapore (UTC+8)</p><ol class="timeline">{''.join(event_html(e) for e in editorial['timeline'])}</ol></section><section class="bottom-section" id="finished-edits"><p class="label">02 / {release}</p><h2>The story, assembled.</h2><p>Two versions of the lead story: a vertical recap and a longer breakdown of the pole battle, cutoffs and decisions.</p><div class="edit-grid">{''.join(figure(e) for e in edits)}</div><p class="fine">English narration and captions. The published viewing copies are compressed for phone playback; the full-resolution masters remain in the local collection.</p>{rendered_outline}</section><section class="bottom-section" id="classification"><p class="label">03 / Official result</p><h2>The final qualifying order.</h2><p>Verstappen takes pole in 1:31.373. Leclerc is 0.054 seconds behind; Hamilton is 0.123 behind. Qualifying results and the provisional race grid are separate documents.</p><div class="table-wrap"><table><caption>FIA final qualifying classification · Document 74</caption><thead><tr><th>Pos.</th><th>Driver</th><th>Q1</th><th>Q2</th><th>Q3</th></tr></thead><tbody>{rows}</tbody></table></div><p class="fine">NC: Hadjar recorded no valid qualifying time. He was permitted to start. Russell qualified sixth and appears twenty-first on the provisional race grid after a 40-place power-unit penalty.</p>{data_block(['Q11','Q12'])}</section><section class="bottom-section" id="sources"><p class="label">04 / Evidence & coverage</p><h2>A traceable story.</h2><div class="source-summary"><div><h3>What is here</h3><p>{len(events)} researched events, {len(ideas)} prioritized ideas, {len(clips)} selected excerpts and {len(edits)} edited recaps. The local media collection contains {len(catalog['assets'])} original videos and {len(catalog['sources'])} source records.</p><p>Ranks reflect editorial judgment about consequence, clarity, evidence and available media. The lead story is produced; the remaining stories have proposed outlines.</p></div><div><h3>How to read it</h3><p>Exact clocks appear only where supported. Phase-only events are not assigned invented timestamps. A car’s lap number is session-specific. Sector comparisons use the drivers’ different best Q3 laps.</p><p>Video ranges use seconds within the source video. Reviews combine sampled images and publisher captions. Driver reactions are attributed accounts; FIA documents establish official decisions.</p></div></div><div class="source-links">{link('data/timeline.json','Full timeline · JSON ↗')}{link('data/results.json','Qualifying results · JSON ↗')}{link('data/ranked-stories.json','Ranked story outlines · JSON ↗')}{link('data/clip-manifest.json','Clip provenance · JSON ↗')}{link('data/source-index.json','Source index · JSON ↗')}</div><p class="fine" style="margin-top:24px">Research snapshot: 10 October 2026 UTC. Final classification and provisional grid were issued early 11 October in Singapore. Collection is bounded by source access and storage; it does not claim every public or social post. Footage credit: Formula 1. Private research access does not establish redistribution permission.</p></section><footer class="footer"><span>Session notes / Singapore Qualifying 2026</span>{link('#overview','Back to top ↑')}</footer></main></div><script>{js}</script></body></html>'''
    (out/'index.html').write_text(page)
    write_json(out/'data/page-data.json',{'event':editorial['event'],'timeline':editorial['timeline'],'ideas':ideas,'data_assets':data,'clips':clips,'edits':edits})
    (ROOT/'outputs/index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=../sites/timeline/dist/index.html"><title>Singapore qualifying timeline</title><a href="../sites/timeline/dist/index.html">Open the Singapore qualifying timeline</a></html>')
    (site/'README.md').write_text('# Singapore Main Qualifying timeline\n\nBuildless HTML with local video, captions and retained data. Rebuild from the event workspace with `scripts/f1 --workspace events/2026-singapore-qualifying timeline` in the parent project.\n')
    package_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    if package_bytes>60*1024**2:raise ValueError('Phone package exceeds 60 MiB transfer budget; reduce viewing-copy bitrate or selected clips before publication')
    write_json(ROOT/'outputs/timeline-build.json',{'event_id':cfg['id'],'clips':len(clips),'events':len(events),'stories':len(ideas),'edits':len(edits),'finalized':finalized,'html_sha256':digest(out/'index.html'),'input_hashes':{p:digest(ROOT/p) for p in ['data/processed/editorial.json','data/processed/catalog.json','outputs/manifest.json','research/media/clip_review.json']},'bytes':package_bytes,'package_budget_bytes':60*1024**2})
    print('Timeline written:',out/'index.html',flush=True)
    return {'path':str(out/'index.html'),'clips':len(clips),'edits':len(edits)}
