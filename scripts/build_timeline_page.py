"""Render a portable static HTML view from the retained race research."""
import json
from html import escape as esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'sites/singapore-sprint-timeline'
OUT = SITE / 'dist'
d = json.loads((OUT/'data/page-data.json').read_text())
events = {e['id']:e for e in d['timeline']}
ideas = {i['id']:i for i in d['ideas']}
sources = {s['id']:s for s in d['sources']}
data_assets = {a['id']:a for a in d['data_assets']}
clips = {c['id']:c for c in d['clips']}
edit = json.loads((ROOT/'outputs/edit-plan.json').read_text())

# Editorial treatment of the already verified research. Recommendations remain drafts.
stories = {
 'I01': {'anchor':'E04','short':'Three turning points','duration':'69 sec + 2:47','hook':'A lost lead. A drying track. A collision on the last lap.',
  'copy':'Verstappen’s victory began with a setback: Russell beat him into Turn 1. Russell’s opening-lap crash returned the lead, and the drying track made the middle phase a question of pace and tyre life. A final-lap McLaren collision then reshaped the points behind a Red Bull–Ferrari podium. Follow those three turns in the story, then land on the official result.',
  'why':'The clearest complete race story, with reviewed footage and two finished edits.'},
 'I02': {'anchor':'E11','short':'McLaren’s last-lap cost','duration':'55 sec proposed','hook':'A podium chase ends with one point between two cars.',
  'copy':'Leclerc’s worn front tyres brought the McLarens into the podium fight. At Turn 5 on the final lap, Norris tried the inside line and the two cars made contact. Norris recovered to eighth and one point; Piastri stopped and was classified fourteenth after nineteen laps. Close on the actual ruling: the stewards took no further action.',
  'why':'A strong visual incident with a clear consequence and a published ruling.',
  'beats':[(12,'Set up the podium chase','Leclerc is under pressure; establish why Piastri and Norris are fighting here.',['E10']),
           (15,'Show the contact','Use the trackside, onboard and overhead views in order. Describe the sequence without assigning unsupported intent.',['E11']),
           (13,'Show what changed','Norris finishes P8; Piastri is a classified DNF in P14. McLaren takes one Sprint point.',['E11','E12']),
           (15,'End with the ruling','Place the no-further-action decision on screen and link the FIA document.',['E11'])]},
 'I03': {'anchor':'E03','short':'Ferrari’s two podium routes','duration':'60 sec proposed','hook':'Hamilton gains at the start. Leclerc holds on at the finish.',
  'copy':'Ferrari’s double podium came through two different races. Hamilton’s launch moved him from sixth to third, and Russell’s retirement promoted him to second. Leclerc’s late race was defensive: worn front tyres brought the McLarens closer, before he held third by just 0.367 seconds from Antonelli. Connect the opening gain to the final margin.',
  'why':'Combines an immediately visible launch with a measurable finish-line payoff.',
  'beats':[(18,'The launch','Show Hamilton going from P6 to P3, with the final grid as the starting reference.',['E03']),
           (15,'The pursuit','After Russell retires, Hamilton follows Verstappen; show how the gap grows in the middle phase.',['E04','E09']),
           (17,'The defence','Leclerc’s front tyre wear brings the chasing group into play. Keep the focus on the fight for third.',['E10']),
           (10,'Two Ferraris, two outcomes','Hamilton takes P2, Leclerc P3. Finish on the 0.367-second Leclerc–Antonelli margin.',['E12'])]},
 'I04': {'anchor':'E13','short':'The 89-point consequence','duration':'40 sec proposed','hook':'The championship moves five points while everyone watches the chaos.',
  'copy':'Russell led at the first corner and left the Sprint with no points. Antonelli finished fourth, taking five. Their championship totals became 325 and 236, extending Antonelli’s advantage from 84 to 89. The visual hook is Russell’s lost lead; the payoff is a simple before-and-after points graphic.',
  'why':'A compact data story with a direct link between the opening lap and the championship.',
  'beats':[(12,'The opportunity disappears','Open on Russell’s launch, then the opening-lap crash and retirement.',['E03','E04']),
           (12,'Antonelli reaches fourth','Show the final classification: Antonelli takes five points, Russell none.',['E12']),
           (16,'84 becomes 89','Animate the gap from 84 to 89 and show the post-Sprint totals of 325 and 236.',['E13'])]},
 'I05': {'anchor':'E07','short':'The restart chain reaction','duration':'45 sec proposed','hook':'One compressed queue, three cars in contact.',
  'copy':'As the field prepared to restart, Albon contacted Bortoleto at Turn 16 and Bottas then hit Albon. Bortoleto and Bottas retired after the incident; Albon continued before retiring later. Explain the order of contact with the available replay and the two FIA decisions. Keep any claim about individual braking inputs out of the narration: those traces have not been validated.',
  'why':'A replay-led explainer grounded in the stewards’ written account.',
  'beats':[(10,'Establish the queue','Show the field behind the Safety Car approaching the restart.',['E07']),
           (18,'Walk through the contact','Identify Albon, Bortoleto and Bottas; use the replay to show the sequence once at normal speed.',['E07']),
           (17,'Separate the consequences','Bortoleto and Bottas stop; Albon continues, then retires later. Display both FIA decisions.',['E07','E08'])]},
 'I06': {'anchor':'E12','short':'The midfield takes its points','duration':'45 sec proposed','hook':'Away from the podium, the finish rewards survival.',
  'copy':'Bearman’s pass on Gasly supplies the action opening. Then move to the final classification: Lawson finishes fifth, Bearman sixth and Hulkenberg seventh, collecting four, three and two points. The McLaren collision leaves Norris eighth with one. End on the official points table, keeping the observed pass and the later finish positions distinct.',
  'why':'Extends the recap beyond the headline incidents with a concrete points payoff.',
  'beats':[(15,'Bearman makes the move','Use the Turns 1–3 pass on Gasly as the action hook.',['E08']),
           (18,'Follow the final order','Show Lawson P5, Bearman P6 and Hulkenberg P7, followed by Norris in eighth.',['E11','E12']),
           (12,'Turn positions into points','4, 3, 2, 1: close with the official Sprint points for fifth through eighth.',['E12'])]}
}

treatment = {
 'E01':('PRE-RACE','Before 17:00','Approximate','The weather sets the terms','Rain arrives before the scheduled start, leaving different parts of the circuit in different conditions. Use the wet grid to establish the setting, then move quickly to the delayed start.','A delayed start and intermediate tyres frame the afternoon.'),
 'E02':('FORMATION','17:30','Reported minute','Two laps before the launch','The Safety Car leads the field away at 17:30. Two formation laps precede the standing start, so distinguish the formation sequence from the beginning of racing.','The actual race start follows at 17:36:30.'),
 'E03':('LAP 01','17:36:30','Session start','The launch changes the order','Russell takes the lead into Turn 1. Behind him, Hamilton’s move from sixth to third sets up Ferrari’s result before the first lap is complete. The timestamp is the recorded session start, not the precise instant of the pass.','Hamilton gains three positions at the start.'),
 'E04':('LAP 01','Final corner','Lap verified','A lead lost in one corner','Russell’s strong getaway is undone at the final corner of the opening lap. His crash hands the lead back to Verstappen and moves Hamilton into second. This is the first decisive reversal at the front.','Verstappen inherits the lead; Russell scores no points.'),
 'E05':('LAP 01','17:38:19','Incident time','Two Sprints end at Turn 16','Perez and Stroll make contact and both retire. The later FIA decision finds Perez predominantly at fault but applies no penalty. Pair the clip with that decision rather than treating the race-control announcement time as the incident time.','Both drivers retire; no penalty is applied.'),
 'E06':('EARLY LAPS','Safety Car','Grouped sequence','The field keeps shrinking','Hadjar and Colapinto stop in the early laps, while Lindblad spins during neutralisation. The selected clip shows Hadjar’s retirement on lap 3; it is not a visual record of every event in this grouped sequence.','Separate retirements and spins from a single assumed cause.'),
 'E07':('RESTART','17:51:17','Incident time','Contact before racing resumes','A concertina at Turn 16 catches Albon, Bortoleto and Bottas while the field prepares for the restart. The order of contact is established by the replay and stewards’ accounts. Their eventual retirements do not all happen at the same moment.','Bortoleto and Bottas retire; Albon continues before retiring later.'),
 'E08':('END LAP 06','Restart','Lap verified','The race gets moving again','The Safety Car comes in at the end of lap 6. In the racing that follows, Bearman passes Gasly through Turns 1–3. The two clips distinguish the restart from the overtake, whose exact lap has not been separately verified in the research timeline.','The pace battle resumes, with points still available further back.'),
 'E09':('LAPS 13–16','Drying track','Reported laps','Verstappen finds breathing room','Verstappen extends the lead to around three seconds by lap 13 and five by lap 16 as the intermediate tyres wear. The linked lap-finish data tracks the changing margin; it cannot by itself isolate the contribution of tyres, traffic or driver input.','A growing margin gives Verstappen room to manage the finish.'),
 'E10':('LATE RACE','Podium fight','Exact lap unverified','Leclerc has company','Leclerc reports worn front tyres as Piastri and Norris close. This is the setup for the final-lap collision: a tightening fight over the last podium position, with Antonelli also in contention.','The closing group turns the last lap into a points opportunity.'),
 'E11':('LAP 20','18:15:05','Incident time','McLaren’s last-lap collision','Norris attempts an inside pass at Turn 5 and both McLarens spin after contact. Norris recovers to finish eighth; Piastri stops and is classified fourteenth after nineteen laps. The stewards take no further action.','McLaren leaves the Sprint with one point.'),
 'E12':('LAP 20','18:16:19','Chequered flag','Verstappen wins. Ferrari follows.','Verstappen beats Hamilton by 2.591 seconds. Leclerc completes the podium, only 0.367 seconds ahead of Antonelli. Thirteen drivers complete all twenty laps; the classification records nine DNFs, including the classified Piastri.','VER 8 points · HAM 7 · LEC 6 · ANT 5'),
 'E13':('POST-RACE','Championship','Published totals','The gap grows to 89','Antonelli’s fourth place adds five points while Russell’s retirement yields none. Their totals after the Sprint are 325 and 236. The championship lead therefore grows from 84 points to 89.','Antonelli adds five points to his advantage over Russell.')
}

def fmt(value):
    return f'{int(value)//60:02}:{int(value)%60:02}'

def link(url,label,cls=''):
    remote=url.startswith('https:')
    return f'<a href="{esc(url,quote=True)}" class="{cls}"'+(' target="_blank" rel="noopener noreferrer"' if remote else '')+f'>{esc(label)}</a>'

def video(c):
    caption = f'<track kind="captions" src="{c["caption"]}" srclang="en" label="English">' if c.get('caption') else ''
    return f'''<figure class="clip"><div class="player"><video controls playsinline preload="none" poster="{c['poster']}" aria-label="{esc(c['title'])}" src="{c['src']}">{caption}</video></div>
      <figcaption><strong>{esc(c['title'])}</strong><span class="clip-meta">{c['duration']:g} sec · source {fmt(c['source_in'])}–{fmt(c['source_out'])}</span>
      {link(c['source_url'],'Formula 1 · Original source ↗','credit')}
      {'<p class="clip-note">'+esc(c['note'])+'</p>' if c['note'] else ''}
      <p class="video-error" hidden>Playback could not load. {link(c['src'],'Open the clip directly ↗')} or use the original source above.</p></figcaption></figure>'''

def finished_edits():
    result='<div class="detail-block" id="finished-edits"><p class="label">Finished edits / Ready to watch</p><div class="edit-grid">'
    for shape,title,time in [('vertical','The short recap','1:09'),('landscape','The expanded story','2:47')]:
        result+=f'''<figure class="clip {shape}"><video controls playsinline preload="none" poster="posters/{shape}.jpg" src="edits/{shape}.mp4" aria-label="{title}"><track kind="captions" src="captions/{shape}.vtt" srclang="en" label="English"></video><figcaption><strong>{title}</strong><span class="clip-meta">{time} · {shape.title()} · English captions</span><div class="source-links">{link('edits/'+shape+'.mp4','Open / save video ↗')}{link('edits/'+shape+'-script.txt','Read narration ↗')}</div><p class="video-error" hidden>Playback could not load. Use the direct video link above.</p></figcaption></figure>'''
    return result+'</div><p class="fine" style="margin-top:18px">Original summary narration and data graphics with selected Formula 1 footage. The landscape file is a smaller viewing copy of the finished edit.</p></div>'

def story_body(iid):
    s=stories[iid]
    html='<div class="detail-block"><p class="label">The story</p><p class="story-copy">'+esc(s['copy'])+'</p><h4>'+('Finished short-video outline' if iid=='I01' else 'Recommended edit outline')+'</h4>'
    html+='<p class="fine">'+('Timing follows the finished vertical edit. Expanded analysis is also available below.' if iid=='I01' else 'Proposed timings and narration direction; this story has not yet been produced.')+'</p><ol class="beat-list">'
    beats=[]
    if iid=='I01':
        for scene in edit['edits']['vertical']:
            beats.append((scene['timeline_in'],scene['timeline_out'],scene['title'].replace('\n',' ').title(),scene['narration'],scene['event_ids']))
    else:
        elapsed=0
        for duration,title,copy,eids in s['beats']:
            beats.append((elapsed,elapsed+duration,title,copy,eids));elapsed+=duration
    for start,end,title,copy,eids in beats:
        refs=''.join(link('#'+eid,events[eid]['title']) for eid in eids)
        html+=f'<li class="beat"><span class="beat-time">{fmt(start)}<br>–{fmt(end)}</span><div><strong>{esc(title)}</strong><p>{esc(copy)}</p>{refs}</div></li>'
    return html+'</ol></div>'

def data_block(eids):
    required=[]
    source_ids=[]
    for eid in eids:
        for aid in events[eid]['required_asset_ids']:
            if aid.startswith('D_') and aid not in required: required.append(aid)
        for sid in events[eid]['source_ids']:
            if sid not in source_ids:source_ids.append(sid)
    if 'E13' in eids and 'D_RESULTS' not in required:required.append('D_RESULTS')
    html='<div class="detail-block"><p class="label">Data & supporting evidence</p><ul class="asset-list">'
    for aid in required:
        a=data_assets[aid]
        if aid=='D_STEWARDS':
            relevant=[sid for sid in source_ids if sid in ['fia_perez','fia_norris','fia_albon','fia_bottas']]
            files={'fia_perez':'fia_perez_decision.pdf','fia_norris':'fia_mclaren_norris_decision.pdf','fia_albon':'fia_albon_decision.pdf','fia_bottas':'fia_bottas_decision.pdf'}
            for sid in relevant:
                html+='<li>'+link('data/'+files[sid],sources[sid]['title']+' ↗')+'<span class="filetype">PDF</span><small>FIA stewards’ decision · retained source document</small></li>'
        else:
            for f in a['files']:
                filetype=Path(f['name']).suffix.lstrip('.').upper()
                title=a['description']
                if aid=='D_CAR_DATA': title='Lap 7 · '+('Verstappen' if 'VER' in f['name'] else 'Hamilton')+' · car data'
                note={'D_INTERVALS':'Derived from lap-end timestamps; not continuous timing intervals.',
                      'D_CAR_DATA':'Context only. These are not the restart-incident drivers.',
                      'D_GRID':'FIA · final starting grid','D_RESULTS':'FIA · official final classification',
                      'D_CHAMPIONSHIP':'FIA · post-Sprint points'}.get(aid,'OpenF1 · session 11383 · retained research data')
                html+='<li>'+link(f['path'],title+' ↗')+f'<span class="filetype">{filetype}</span><small>{esc(note)}</small></li>'
    html+='</ul>'
    if 'D_CAR_DATA' in required:
        html+='<p class="data-note">Evidence gap: braking traces for Albon, Bortoleto and Bottas have not been collected and validated. The sequence is supported by footage and FIA decisions; the available Verstappen/Hamilton telemetry does not establish its cause.</p>'
    html+='<div class="source-links">'+''.join(link(sources[s]['url'],sources[s]['title']+' ↗') for s in source_ids if s in sources)+'</div></div>'
    return html

def gap_chart():
    rows=[r for r in d['insights']['lap_finish_gaps'] if r['lap']>=7 and r.get('HAM') is not None]
    points=' '.join(f'{46+(r["lap"]-7)/13*416:.1f},{128-r["HAM"]/6*100:.1f}' for r in rows)
    return f'''<figure class="sparkline"><svg viewBox="0 0 500 160" role="img" aria-label="Hamilton’s gap to Verstappen grows through the middle phase, then narrows toward the finish"><g fill="none" stroke="currentColor" opacity=".18"><path d="M46 28H462M46 78H462M46 128H462"/></g><g font-family="monospace" font-size="10" fill="currentColor" opacity=".7"><text x="4" y="32">6 sec</text><text x="4" y="82">3 sec</text><text x="16" y="132">0</text><text x="46" y="153">Lap 7</text><text x="234" y="153">13</text><text x="434" y="153">20</text></g><polyline fill="none" stroke="currentColor" stroke-width="2" points="{points}"/></svg><figcaption>Hamilton’s gap to Verstappen at each lap finish, derived from OpenF1 timestamps. The derived final gap differs from the official 2.591 sec by 0.034 sec; use FIA classification for the result.</figcaption></figure>'''

def event_html(e):
    eid=e['id']; phase,time,precision,title,copy,consequence=treatment[eid]
    iid=next((i for i,s in stories.items() if s['anchor']==eid),None)
    highlight=eid in ['E03','E04','E07','E11','E12']
    classes='event'+(' highlight' if highlight else '')+(' featured' if eid in ['E04','E11'] else '')
    html=f'<li class="{classes}" id="{eid}" data-highlight="{str(highlight).lower()}" data-story="{str(bool(iid)).lower()}"><div class="event-clock"><b>{phase}</b><span>{time}</span><span>{precision}</span><em>{eid}</em></div><article class="event-shell" aria-labelledby="title-{eid}"><div class="event-intro"><div class="label">'+('<span class="tag">Selected highlight</span>' if highlight else '')+f'<span>{esc(e["phase"].replace("_"," "))}</span></div><h3 id="title-{eid}">{title}</h3><p>{esc(e["summary"])}</p><p class="consequence"><strong>{esc(consequence)}</strong></p></div>'
    if iid:
        s=stories[iid]; idea=ideas[iid]
        html+=f'<div class="story-teaser"><span class="rank">{idea["rank"]:02}</span><div><p class="label">Recommended story / Priority {idea["rank"]}</p><h4>{esc(idea["title"])}</h4><p>{esc(s["hook"])}</p><p class="story-status">'+('2 finished edits' if iid=='I01' else 'Story ready for assembly')+' · '+s['duration']+'</p></div></div>'
    detail_id='story-'+iid if iid else 'details-'+eid
    label='Expand story, video & data' if iid else 'Explore this moment'
    html+=f'<details class="event-details" id="{detail_id}"><summary>{label}</summary><div class="detail-body">'
    html+='<div class="detail-block"><p class="label">Race narrative</p><p>'+esc(copy)+'</p>'
    if eid=='E09':html+=gap_chart()
    if eid=='E13':html+='<div class="metric-pair"><div><strong>325</strong><span>Antonelli · after Sprint</span></div><div><strong>236</strong><span>Russell · after Sprint</span></div></div>'
    html+='</div>'
    eids=[eid]
    if iid:
        html+=story_body(iid)
        eids=list(dict.fromkeys([eid]+ideas[iid]['event_ids']))
        if iid=='I04':eids=['E13','E03','E04','E12']
        if iid=='I01':html+=finished_edits()
    selected=[c for c in d['clips'] if set(c['event_ids'])&set(eids)]
    curated={
      'I01':['e01','e03','e04','e09','e11','e12'],
      'I02':['e10','e11','reaction-1878659983550736553','reaction-1878659174045661976','e12'],
      'I03':['e03','e09','e10','e12','reaction-1878661529600619658'],
      'I04':['e03','e04','reaction-1878658023111854289','e12'],
      'I05':['e07','e08'],
      'I06':['bearman-pass','e11','e12']
    }
    if iid: selected=[clips[c] for c in curated[iid]]
    if selected:
        html+='<div class="detail-block"><p class="label">'+('Associated story footage' if iid else 'Selected footage')+f' / {len(selected)} clips</p><div class="media-grid">'+''.join(video(c) for c in selected)+'</div></div>'
    else:
        html+='<div class="detail-block"><p class="label">Media treatment</p><p>'+('Use the linked points document to make a before-and-after graphic.' if eid=='E13' else 'No separate formation-lap clip is selected. Use a simple two-lap graphic and the linked race report for this part of the story.')+'</p></div>'
    html+=data_block(eids)
    related=[k for k,i in ideas.items() if eid in i['event_ids'] and k!=iid]
    if related: html+='<p class="related">Also in: '+''.join(link('#story-'+i,stories[i]['short']) for i in related)+'</p>'
    return html+'</div></details></article></li>'

def results_table(results,label):
    html=f'<div class="table-wrap"><table><caption>{esc(label)}</caption><thead><tr><th scope="col">Pos.</th><th scope="col">Driver</th><th scope="col">Gap / status</th><th scope="col">Pts</th></tr></thead><tbody>'
    for r in results:
        position=r['position'] or 'NC'
        gap='39:48.162' if position==1 else (f'+{r["gap_seconds"]:.3f}' if r['status']=='Finished' else f'DNF · {r["laps_completed"]} laps')
        html+=f'<tr><td>{position}</td><td>{esc(r["driver"])}<small>{esc(r["team"])}</small></td><td class="mono">{gap}</td><td>{r["points"]}</td></tr>'
    return html+'</tbody></table></div>'

nav=''.join(link('#story-'+iid,f'{ideas[iid]["rank"]:02}  {s["short"]}') for iid,s in stories.items())
css=(ROOT/'f1_pipeline/resources/timeline.css').read_text()
js=(ROOT/'f1_pipeline/resources/timeline.js').read_text()
html=f'''<!doctype html>
<html lang="en" data-theme="auto"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>Singapore Sprint · The race in moments</title><meta name="description" content="A sourced vertical timeline of the 2026 Singapore Sprint: 13 race events, selected highlights, six recommended stories, footage and data."><meta name="theme-color" content="#171717"><meta property="og:title" content="Singapore Sprint · The race in moments"><meta property="og:description" content="Follow the race. Explore the stories. Watch the moments."><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23171717'/%3E%3Cpath d='M9 7h14v5H14v3h8v5h-8v5H9z' fill='white'/%3E%3C/svg%3E"><script>try{{const t=localStorage.getItem('f1-timeline-theme');document.documentElement.dataset.theme=['light','dark','auto'].includes(t)?t:'auto'}}catch(_){{}}</script><style>{css}</style></head>
<body><a class="skip" href="#race-timeline">Skip to the race timeline</a><header class="top"><div class="top-inner"><a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true"></span>Race notes / Singapore</a><div class="theme js-only" role="group" aria-label="Color theme"><button data-set-theme="light" aria-pressed="false">Light</button><button data-set-theme="dark" aria-pressed="false">Dark</button><button data-set-theme="auto" aria-pressed="true">Auto</button></div></div></header>
<div class="layout"><aside class="side"><p class="label">Singapore / 10.10.26</p>{link('#race-timeline','The race timeline')}{link('#finished-edits','Watch the finished edits')}<nav aria-label="Recommended stories"><p class="label">Stories by priority</p>{nav}</nav>{link('#classification','Final classification')}{link('#sources','Sources & coverage')}<p class="side-note">20 laps · Marina Bay<br>Times in Singapore, UTC+8.<br><br>13 identified events.<br>6 editorial storylines.<br>2 finished summary videos.</p></aside>
<main><section class="hero" id="overview"><p class="label">10 October 2026 / Marina Bay Street Circuit</p><h1>Singapore Sprint.<br>A race in moments.</h1><p class="lead">Rain, a lead lost, and a last-lap collision. Follow the events that shaped Verstappen’s win—and the stories worth telling.</p><p class="sublead">A sourced race outline with selected highlights. Open a recommended segment to read the story, follow its edit sequence, and explore the video and data behind it.</p><div class="actions">{link('#race-timeline','Follow the race ↓','button primary')}{link('#finished-edits','Watch the recaps ↗','button')}</div><div class="hero-meta"><span><strong>20</strong> laps</span><span><strong>13</strong> identified events</span><span><strong>6</strong> recommended stories</span><span>Final classification published</span></div></section>
<nav class="moments" aria-label="Key turning points"><a class="moment" href="#E04"><span class="label">Lap 01</span><strong>A lead lost in one corner ↗</strong><small>Russell out. Verstappen back in front.</small></a><a class="moment" href="#E11"><span class="label">Lap 20</span><strong>McLaren’s last-lap cost ↗</strong><small>Two cars in contact. One point.</small></a><a class="moment" href="#E13"><span class="label">Aftermath</span><strong>The 89-point consequence ↗</strong><small>Antonelli extends his advantage.</small></a></nav>
<details class="mobile-jump"><summary>Jump to a recommended story</summary><nav aria-label="Stories by priority on mobile">{nav}</nav></details>
<section class="timeline-section" id="race-timeline"><div class="section-head"><div><p class="label">01 / Race timeline</p><h2>The race, in sequence.</h2><p>Read down the line. Dark panels mark the biggest reversals; numbered story strips show the editorial priorities.</p></div><span class="fine">Chronological · not to time scale</span></div><div class="filters js-only" role="group" aria-label="Filter timeline"><button class="filter" data-filter="all" aria-pressed="true">All events <span>13</span></button><button class="filter" data-filter="highlight" aria-pressed="false">Highlights <span>5</span></button><button class="filter" data-filter="story" aria-pressed="false">Stories <span>6</span></button></div><p class="view-count" id="view-count" aria-live="polite">Showing 13 of 13 identified events · Times in Singapore (UTC+8)</p><noscript><p class="no-js">All events are shown. Expand any segment to see its story and assets.</p></noscript><ol class="timeline">{''.join(event_html(e) for e in d['timeline'])}</ol></section>
<section class="bottom-section" id="classification"><p class="label">02 / The result</p><h2>The points at the flag.</h2><p>Verstappen wins by 2.591 seconds. Hamilton and Leclerc complete the podium; Leclerc is just 0.367 seconds ahead of Antonelli.</p>{results_table(d['results'][:8],'Sprint points finishers · FIA final classification · 20 laps')}<details class="more-results"><summary>View the remaining 14 drivers</summary>{results_table(d['results'][8:],'Remaining classified drivers and retirements')}</details><p class="fine">13 drivers complete all 20 laps. Nine have DNF status, including Piastri, who is classified P14 with 19 completed laps. NC = not classified.</p><div class="source-links">{link('data/fia_final_classification.pdf','FIA final classification · PDF ↗')}{link('data/results.json','Results data · JSON ↗')}{link('data/fia_championship_after_sprint.pdf','Championship points · PDF ↗')}</div></section>
<section class="bottom-section" id="sources"><p class="label">03 / Sources & coverage</p><h2>A traceable story.</h2><p>The race narrative is based on FIA documents, Formula 1 reporting and selected official video, with OpenF1 timing and car data. Each expanded segment links to its supporting assets.</p><div class="source-summary"><div><h3>What is here</h3><p>All 13 events identified in the completed research, six prioritized ideas, 17 selected clips or reactions, and two finished recap videos. The wider collection contains 43 source records and 13 downloaded original videos.</p><p>Priority ranks are editorial judgments about story value, consequence, evidence and available footage. The first story has been produced; the other five have proposed outlines.</p></div><div><h3>How to read it</h3><p>Exact times are shown only where supported. Several events are grouped by lap or phase. Race-control announcements can come after the incident; the timeline uses the incident time when available.</p><p>Footage in/out points refer to each original source video, not the race clock. Clips retain their original color during playback. Media loads on demand.</p></div></div><div class="source-links">{link('data/timeline.json','Full event timeline · JSON ↗')}{link('data/clip-manifest.json','Clip sources & provenance · JSON ↗')}{link('data/ranked-stories.json','Ranked ideas · JSON ↗')}{link(sources['f1_report']['url'],'Formula 1 race report ↗')}{link(sources['fia_report']['url'],'FIA race report ↗')}</div><p class="fine" style="margin-top:24px">Research snapshot: 10 October 2026. Collection is bounded by discoverability and source access; it is not an exhaustive archive of every public or social post. Footage credit: Formula 1. This private research collection does not establish redistribution permission.</p></section>
<footer class="footer"><span>Race notes / Singapore Sprint 2026</span>{link('#overview','Back to top ↑')}</footer></main></div><script>{js}</script></body></html>'''
(OUT/'index.html').write_text(html)
(OUT/'data/story-treatments.json').write_text(json.dumps(stories,indent=2,ensure_ascii=False)+'\n')
manifest=json.loads((SITE/'.openai/hosting.json').read_text());manifest['static']={'directory':'dist'}
(SITE/'.openai/hosting.json').write_text(json.dumps(manifest,indent=2)+'\n')
(SITE/'README.md').write_text('# Singapore Sprint timeline\n\nA buildless, phone-friendly HTML timeline. Open `dist/index.html` or serve `dist/` with a static HTTP server. All page styling and behavior are inline. Videos, captions and evidence files live alongside it.\n\nGenerated from the retained F1 research by `scripts/build_timeline_assets.py` and `scripts/build_timeline_page.py` in the parent f1-content workspace. No runtime dependencies or external fonts.\n')
print(f'Created {OUT / "index.html"}: {len(html):,} characters, 13 events, 6 stories.')
