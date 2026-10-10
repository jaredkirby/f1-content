"""Session-aware qualifying analysis with explicit source and review contracts."""
from datetime import datetime, timedelta
import math
import os
from .core import ROOT, config, read_json, write_json, safe_relative, digest, now, log

def unique(rows,key,label):
    values=[r.get(key) for r in rows]
    if None in values or len(values)!=len(set(values)):
        raise ValueError(f'{label}: missing or duplicate {key}')
    return {r[key]:r for r in rows}

def reconcile_qualifying(official,api):
    """Compare every driver and every valid session time, not race points/gaps."""
    left=unique(official,'driver_number','FIA results')
    right=unique(api,'driver_number','API results')
    errors=[]
    if left.keys()!=right.keys():
        errors.append(f'Driver sets differ: missing={sorted(left.keys()-right.keys())}, extra={sorted(right.keys()-left.keys())}')
    for number,row in left.items():
        other=right.get(number)
        if not other:continue
        position=row.get('official_position',row.get('position'))
        if row.get('classified',True) and position!=other.get('position'):
            errors.append(f'Car {number}: qualifying position conflict')
        duration=other.get('duration')
        if not isinstance(duration,list) or len(duration)!=3:
            errors.append(f'Car {number}: qualifying phase durations unavailable');continue
        for i,phase in enumerate(('q1','q2','q3')):
            expected=row.get(phase+'_seconds')
            actual=duration[i]
            if expected is None:
                if actual is not None and (type(actual) not in (int,float) or actual!=0):
                    errors.append(f'Car {number}: unexpected {phase.upper()} time')
            elif (any(type(value) not in (int,float) or not math.isfinite(value) or value<=0
                      for value in (expected,actual)) or abs(expected-actual)>.0011):
                errors.append(f'Car {number}: {phase.upper()} time conflict ({expected}/{actual})')
    return errors

def verified_data(manifest):
    cfg=config()
    if manifest.get('event_id')!=cfg['id']:
        raise ValueError('Data manifest event mismatch')
    records={}
    for receipt in manifest.get('receipts',[]):
        path=safe_relative(receipt['path'])
        if not path.is_file() or digest(path)!=receipt['sha256']:
            raise ValueError('Raw data integrity mismatch: '+str(path))
        rows=read_json(path)
        if not isinstance(rows,list) or any(not isinstance(r,dict) or r.get('session_key')!=cfg['session_key'] for r in rows):
            raise ValueError('Raw data session mismatch: '+path.name)
        if path.name in records:raise ValueError('Duplicate data receipt: '+path.name)
        records[path.name]=rows
    for name in ('drivers','laps','session_result','race_control','weather'):
        if name+'.json' not in records:raise ValueError('Required validated data unavailable: '+name)
    return records

def within_review(asset,start,end):
    if not all(type(t) in (int,float) and math.isfinite(t) for t in (start,end)):
        return False
    return 0<=start<end<=asset['duration']+.025 and any(
        r['in']<=start+.001 and end<=r['out']+.001 for r in asset.get('reviewed_ranges',[]))

def analyze_qualifying():
    cfg=config()
    bundle=read_json(ROOT/'research/event/event_bundle.json')
    catalog=read_json(ROOT/'data/processed/catalog.json')
    if not bundle or not catalog:raise ValueError('Event research and media catalog required')
    if bundle['event'].get('id')!=cfg['id'] or bundle['event'].get('session_key')!=cfg['session_key'] or catalog.get('event_id')!=cfg['id']:
        raise ValueError('Qualifying input event identity mismatch')
    data=verified_data(read_json(ROOT/'data/processed/data_manifest.json',{}))
    conflicts=reconcile_qualifying(bundle['results'],data['session_result.json'])
    if conflicts:raise ValueError('Qualifying classification gate failed: '+'; '.join(conflicts))
    evidence=unique(bundle['sources'],'id','Research sources')
    for source in evidence.values():
        if source.get('local_path'):
            path=safe_relative(source['local_path'])
            if not source.get('sha256') or digest(path)!=source['sha256']:
                raise ValueError('Research source integrity mismatch: '+source['id'])
    timeline=unique(bundle['timeline'],'id','Timeline')
    assets=unique(catalog['assets'],'id','Catalog assets')
    sources=unique(catalog['sources'],'id','Media sources')
    mapping=read_json(ROOT/'research/event/media_matches.json',{'event_id':cfg['id'],'matches':{}})
    if mapping.get('event_id')!=cfg['id']:raise ValueError('Media mapping event mismatch')
    if set(mapping.get('matches',{}))-timeline.keys():raise ValueError('Media map references unknown event')
    data_assets=[dict(a) for a in bundle['assets'] if a['kind']=='data']
    for a in data_assets:
        paths=a.get('local_paths',[])+([a['local_path']] if a.get('local_path') else [])
        for path in paths:
            if not safe_relative(path).is_file():raise ValueError('Missing data asset: '+path)
    review_path=ROOT/'research/media/clip_review.json'
    for event in timeline.values():
        if not event.get('source_ids') or set(event['source_ids'])-evidence.keys():
            raise ValueError('Unlinked event claim: '+event['id'])
        matches=[]
        for match in mapping.get('matches',{}).get(event['id'],[]):
            source=sources.get(match['source_id'],{})
            asset=assets.get(source.get('asset_id'))
            if not asset or match.get('source_sha256')!=asset['sha256']:
                raise ValueError('Media association has stale or missing source hash: '+event['id'])
            review_sha=digest(review_path)
            if asset.get('review_receipt_sha256')!=review_sha:
                raise ValueError('Catalog visual review changed; rerun catalog: '+event['id'])
            if match.get('review_receipt_sha256',review_sha)!=review_sha:
                raise ValueError('Media association has stale review receipt: '+event['id'])
            if not within_review(asset,match['in'],match['out']):
                raise ValueError('Association exceeds reviewed footage: '+event['id'])
            matches.append({**match,'asset_id':asset['id'],'review_receipt_sha256':review_sha,
                            'alignment':'Hash-bound sampled visual review; source-relative seconds'})
        event['media_matches']=matches
        event['assembly_status']='footage_available' if matches else 'data_graphics_or_additional_footage'
        event['data_assets']=[a for a in data_assets if a['id'] in event.get('required_asset_ids',[])]
    ideas=bundle['ranked_ideas']
    unique(ideas,'id','Story ideas')
    for idea in ideas:
        if not idea.get('event_ids') or set(idea['event_ids'])-timeline.keys():raise ValueError('Story references unknown events')
        relevant=[timeline[e] for e in idea['event_ids']]
        idea['available_asset_ids']=sorted({m['asset_id'] for e in relevant for m in e['media_matches']})
        idea['footage_event_coverage']=round(sum(bool(e['media_matches']) for e in relevant)/len(relevant),3)
        idea['ranking_method']='Editorial judgment: consequence, story clarity, evidence and available media; not measured audience performance'
        idea['status']='assembly_ready' if idea['available_asset_ids'] else 'graphics_ready'
        existing=read_json(ROOT/'outputs/manifest.json',{})
        if existing and existing.get('event_id')!=cfg['id']:raise ValueError('Existing render manifest belongs to another event')
    weather=data['weather.json']
    temps=[r['track_temperature'] for r in weather if isinstance(r.get('track_temperature'),(int,float))]
    best_laps=[]
    for result in bundle['results']:
        target=result.get('best_lap_seconds')
        if not target:continue
        candidates=[r for r in data['laps.json'] if r['driver_number']==result['driver_number'] and r.get('lap_duration') and abs(r['lap_duration']-target)<=.0011]
        # Do not assume a car's overall fastest lap was its Q3 classification lap.
        last=max(candidates,key=lambda r:r.get('date_start','')) if candidates else None
        if last:best_laps.append({'driver_number':result['driver_number'],'driver':result['driver'],'lap_number':last['lap_number'],
                                 'date_start':last['date_start'],'lap_duration':last['lap_duration'],
                                 'sectors':[last.get('duration_sector_'+str(i)) for i in (1,2,3)],'method':'Lap duration matches official time in furthest reached qualifying phase; latest matching lap'})
    write_json(ROOT/'data/processed/classification_laps.json',{'event_id':cfg['id'],'records':best_laps})
    telemetry=[]
    for file,rows in data.items():
        if not file.startswith('car_data_'):continue
        speeds=[r['speed'] for r in rows if isinstance(r.get('speed'),(int,float))]
        telemetry.append({'file':'data/raw/openf1/'+file,'samples':len(rows),'max_observed_speed_kmh':max(speeds) if speeds else None,'scope':'Sampled telemetry for configured driver and lap; no causal attribution from speed alone'})
    insights={'classification_crosscheck':{'matched_drivers':len(bundle['results']),'conflicts':[],'method':'Complete driver sets, positions, and Q1/Q2/Q3 times'},
              'classification_laps':best_laps,'track_temperature_range_c':[min(temps),max(temps)] if temps else None,
              'weather_samples':len(weather),'car_data':telemetry}
    sector_path=ROOT/'research/event/sector_comparison.json'
    if sector_path.exists():
        sectors=read_json(sector_path)
        best={r['driver_number']:r for r in best_laps}
        leader=best.get(sectors['pole_driver_number'])
        if not leader or leader['sectors']!=sectors['pole_sectors_seconds']:
            raise ValueError('Pole sector comparison is not supported by retained laps')
        for row in sectors['comparisons']:
            actual=best.get(row['driver_number'])
            if not actual or actual['sectors']!=row['sectors_seconds']:
                raise ValueError('Sector comparison has mismatched driver lap')
            deltas=[round(a-b,3) for a,b in zip(actual['sectors'],leader['sectors'])]
            if deltas!=row['delta_to_verstappen_seconds'] or abs(sum(deltas)-row['total_delta_seconds'])>.0011:
                raise ValueError('Sector comparison arithmetic does not reconcile')
        insights['sector_comparison']=sectors
    result={'event':bundle['event'],'sources':bundle['sources'],'timeline':list(timeline.values()),'results':bundle['results'],
            'ideas':ideas,'derived_facts':bundle.get('derived_facts',[]),'conflicts':bundle.get('conflicts',[]),
            'unknowns':bundle.get('unknowns',[]),'insights':insights,'data_assets':data_assets}
    write_json(ROOT/'data/processed/editorial.json',result)
    write_json(ROOT/'data/processed/decisions.json',{'at':now(),'event_id':cfg['id'],'actual_jev_inference':False,
      'jev_status':'credential_present_not_invoked' if os.getenv('TYPESAFE_API_KEY') else 'credential_missing',
      'classification_method':'Independent research and visual review; deterministic integrity, timing and source checks',
      'ranking_method':'Editorial judgment','ideas':ideas})
    log('analyze','complete',timeline_segments=len(timeline),ideas=len(ideas),matched_results=len(bundle['results']))
    return result
