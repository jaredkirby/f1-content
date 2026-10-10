"""Prepare bounded, phone-sized assets and provenance for the race timeline."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'sites/singapore-sprint-timeline/dist'
for folder in ('clips', 'posters', 'data', 'captions', 'edits'):
    (OUT / folder).mkdir(parents=True, exist_ok=True)
editorial = json.loads((ROOT / 'data/processed/editorial.json').read_text())
catalog = json.loads((ROOT / 'data/processed/catalog.json').read_text())
assets = {a['id']: a for a in catalog['assets']}
sources = {s['id']: s for s in catalog['sources']}
clips = []

def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', *map(str,args)], check=True)

def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'

def seconds(s):
    p = s.replace(',', '.').split(':')
    return sum(float(n)*60**i for i,n in enumerate(reversed(p)))

def captions(source, start, stop, output):
    tracks = source.get('caption_tracks', [])
    if not tracks:
        return None
    path = ROOT / tracks[0]['local_path']
    text = path.read_text()
    cue = re.compile(r'((?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s+-->\s+((?:\d{2}:)?\d{2}:\d{2}\.\d{3})[^\n]*\n(.*?)(?=\n\s*\n|\Z)', re.S)
    selected = []
    for a,b,words in cue.findall(text):
        left,right = max(start,seconds(a)),min(stop,seconds(b))
        if right > left:
            selected.append(f'{stamp(left-start)} --> {stamp(right-start)}\n{words.strip()}')
    if selected:
        (OUT / output).write_text('WEBVTT\n\n'+'\n\n'.join(selected)+'\n')
        return output
    return None

def add_clip(clip_id, asset, start, stop, title, event_ids, note=''):
    source = sources[asset['source_id']]
    target = OUT / 'clips' / (clip_id+'.mp4')
    if not target.exists():
        ffmpeg('-ss',start,'-i',ROOT/asset['original'],'-t',stop-start,
               '-vf','scale=960:-2','-c:v','libx264','-preset','fast','-crf','27',
               '-pix_fmt','yuv420p','-c:a','aac','-b:a','80k','-movflags','+faststart',target)
    poster = OUT / 'posters' / (clip_id+'.jpg')
    if not poster.exists():
        ffmpeg('-ss',min(3,(stop-start)/2),'-i',target,'-frames:v','1','-vf','scale=800:-2','-q:v','4',poster)
    clips.append({'id':clip_id,'title':title,'event_ids':event_ids,'src':f'clips/{clip_id}.mp4',
                  'poster':f'posters/{clip_id}.jpg','caption':captions(source,start,stop,f'captions/{clip_id}.vtt'),
                  'duration':round(stop-start,2),'source_in':start,'source_out':stop,
                  'source_id':source['id'],'source_url':source['url'],'source_title':source['title'],
                  'publisher':source.get('publisher','Formula 1'),'original_sha256':asset['sha256'],
                  'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size,'note':note})
    print('Prepared',clip_id,flush=True)

notes={'E01':'Wet-grid context from the official highlights; this is not a timestamped view of the rainfall.',
       'E06':'Shows Hadjar retiring on lap 3. It does not depict every early retirement.',
       'E08':'Safety Car restart; the separate overtake clip shows Bearman and Gasly.',
       'E09':'Race footage supplies context. The lead values come from the report and linked lap data.'}
for event in editorial['timeline']:
    for i, match in enumerate(event['media_matches']):
        name=event['id'].lower() + (f'-{i+1}' if i else '')
        title=event['title'] if i==0 else 'Verstappen: post-Sprint reaction'
        add_clip(name,assets[match['asset_id']],match['in'],match['out'],title,[event['id']],notes.get(event['id'],'') if i==0 else 'Interview context: Verstappen discusses his start and the next session.')
highlight=next(a for a in assets.values() if a['source_id']=='f1-1878660960273042920')
add_clip('bearman-pass',highlight,215,248,'Bearman passes Gasly',['E08'])
for suffix,event_id,title in [('1878661529600619658','E12','Hamilton: post-Sprint reaction'),
                             ('1878658023111854289','E04','Russell: post-Sprint reaction'),
                             ('1878659983550736553','E11','Piastri: post-Sprint reaction'),
                             ('1878659174045661976','E11','Norris: post-Sprint reaction')]:
    a=next(a for a in assets.values() if a['source_id']=='f1-'+suffix)
    add_clip('reaction-'+suffix,a,0,a['duration'],title,[event_id],'Driver perspective; the stewards’ decision is linked separately.')

# Keep the finished vertical edit, and derive a smaller landscape viewing copy.
for shape in ('vertical','landscape'):
    source=ROOT/f'outputs/singapore-sprint-2026-{shape}.mp4'
    target=OUT/f'edits/{shape}.mp4'
    if not target.exists():
        if shape=='vertical': shutil.copyfile(source,target)
        else: ffmpeg('-i',source,'-vf','scale=960:-2','-c:v','libx264','-preset','fast','-crf','27',
                     '-c:a','aac','-b:a','96k','-movflags','+faststart',target)
    srt=(ROOT/f'outputs/singapore-sprint-2026-{shape}.srt').read_text()
    (OUT/f'captions/{shape}.vtt').write_text('WEBVTT\n\n'+re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})',r'\1.\2',srt))
    shutil.copyfile(ROOT/f'outputs/singapore-sprint-2026-{shape}.txt',OUT/f'edits/{shape}-script.txt')
    shutil.copyfile(ROOT/f'outputs/singapore-sprint-2026-{shape}.jpg',OUT/f'posters/{shape}.jpg')

# Publish only intended evidence files and clean source-page URLs, never CDN tokens.
data=[]
for item in editorial['data_assets']:
    item=dict(item)
    paths=item.get('local_paths', [item['local_path']] if item.get('local_path') else [])
    item['files']=[]
    for path in paths:
        file=ROOT/path
        target=OUT/'data'/file.name
        shutil.copyfile(file,target)
        item['files'].append({'path':'data/'+file.name,'name':file.name,'bytes':file.stat().st_size})
    data.append(item)
for source in editorial['sources']:
    if source['id'].startswith('fia_') and source['local_path'].endswith('.pdf'):
        file=ROOT/'research/event'/source['local_path']
        shutil.copyfile(file,OUT/'data'/file.name)
for leaf,key in [('timeline.json','timeline'),('results.json','results'),('ranked-stories.json','ideas')]:
    (OUT/'data'/leaf).write_text(json.dumps(editorial[key],indent=2,ensure_ascii=False)+'\n')
clean_sources=[{k:s.get(k) for k in ('id','title','url','publisher','kind','sha256')} for s in editorial['sources']]
payload={'event':editorial['event'],'timeline':editorial['timeline'],'ideas':editorial['ideas'],
         'results':editorial['results'],'insights':editorial['insights'],'data_assets':data,'sources':clean_sources,'clips':clips}
(OUT/'data'/'page-data.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
(OUT/'data'/'clip-manifest.json').write_text(json.dumps(clips,indent=2,ensure_ascii=False)+'\n')
total=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
print(f'Prepared {len(clips)} selected clips; total {total/1024/1024:.1f} MiB',flush=True)
