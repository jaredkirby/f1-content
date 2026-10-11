"""Explicit, hash-bound narration preparation, import and offline processing.

Provider execution lives in speech_provider; rendering only consumes saved assets.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import wave

from .core import (ROOT, digest, ensure_space, now, read_json, safe_relative,
                   validate_config, write_json)
from .model_evaluation import IDENTITY_KEYS

RATE = 48000
FRAME_SAMPLES = RATE // 24
MAX_JSON = 2_000_000
SELECTION = 'research/event/narration-selection.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def workspace(root=None):
    root = Path(ROOT if root is None else root).resolve()
    cfg = validate_config(read_json(safe_relative('config/event.json', root=root)), root=root)
    return root, cfg, {k: cfg[k] for k in IDENTITY_KEYS}


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', value):
        raise ValueError('Invalid narration identifier')
    return value


def load(path, root):
    p = safe_relative(path, root=root)
    if p.stat().st_size > MAX_JSON:
        raise ValueError('Narration JSON exceeds its byte limit')
    try:
        return json.loads(p.read_text(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('Invalid narration JSON') from None


def binding(path, root):
    root = Path(root).resolve()
    p = safe_relative(path, root=root)
    return {'path': p.relative_to(root).as_posix(), 'sha256': digest(p)}


def verify(link, root):
    if (not isinstance(link, dict) or set(link) != {'path', 'sha256'}
            or not isinstance(link['path'], str) or Path(link['path']).is_absolute()
            or '..' in Path(link['path']).parts or Path(link['path']).as_posix() != link['path']
            or not isinstance(link['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', link['sha256'])):
        raise ValueError('Invalid narration path/hash binding')
    p = safe_relative(link['path'], root=root)
    if not p.is_file() or digest(p) != link['sha256']:
        raise ValueError('Narration asset changed: ' + link['path'])
    return p


def request(path, root=None):
    root, cfg, identity = workspace(root)
    value = load(path, root)
    fields = {'schema_version', 'job_id', 'event_identity', 'plan', 'format', 'provider', 'scenes', 'limits'}
    if not isinstance(value, dict) or set(value) != fields or value['schema_version'] != 'f1.narration_request.v1':
        raise ValueError('Unsupported narration request schema/fields')
    slug(value['job_id'])
    if value['event_identity'] != identity:
        raise ValueError('Narration event identity mismatch')
    if value['format'] not in cfg.get('formats', ['vertical', 'landscape']):
        raise ValueError('Narration format not requested by this event')
    plan = load(verify(value['plan'], root), root)
    if value['plan']['path'] != 'research/event/video_plan.json' or plan.get('event_id') != identity['id']:
        raise ValueError('Narration requires the current event video plan')
    planned = plan.get('formats', {}).get(value['format'], {}).get('scenes', [])
    scenes = value['scenes']
    if not isinstance(scenes, list) or not scenes or len(scenes) > 100 or len(scenes) != len(planned):
        raise ValueError('Narration must cover every planned scene in order')
    seen = set()
    for row, scene in zip(scenes, planned):
        if (not isinstance(row, dict) or set(row) != {'id', 'text'} or row['id'] != scene.get('id')
                or row['id'] in seen or row['text'] != scene.get('narration')
                or not isinstance(row['text'], str) or not row['text'].strip() or len(row['text']) > 2000):
            raise ValueError('Narration text/scene does not match the reviewed plan')
        slug(row['id']); seen.add(row['id'])
    provider = value['provider']
    if not isinstance(provider, dict) or set(provider) != {'kind', 'model', 'voice', 'settings'}:
        raise ValueError('Explicit narration provider/model/voice/settings required')
    if provider['kind'] == 'elevenlabs':
        from .speech_provider import validate_settings
        validate_settings(provider)
    elif provider['kind'] == 'say':
        if (provider['model'] != 'macos-say' or provider['voice'] != 'Samantha'
                or set(provider['settings']) != {'words_per_minute'}
                or not number(provider['settings']['words_per_minute'], 100, 250)):
            raise ValueError('Unsupported system speech settings')
    elif provider['kind'] == 'imported':
        if provider != {'kind': 'imported', 'model': None, 'voice': None, 'settings': {}}:
            raise ValueError('Imported source identity belongs in its provenance receipt')
    else:
        raise ValueError('Unsupported speech backend')
    limits = value['limits']
    if not isinstance(limits, dict) or set(limits) != {'max_characters', 'max_calls', 'timeout_seconds', 'max_response_bytes', 'max_audio_seconds'}:
        raise ValueError('Explicit narration resource bounds required')
    for key, lower, upper in [('max_characters', 1, 200000), ('max_calls', 1, 100),
                              ('timeout_seconds', 1, 120), ('max_response_bytes', 1024, 32*1024**2),
                              ('max_audio_seconds', 1, 180)]:
        if type(limits[key]) is not int or not lower <= limits[key] <= upper:
            raise ValueError('Invalid narration limit: ' + key)
    if sum(len(s['text']) for s in scenes) > limits['max_characters'] or len(scenes) > limits['max_calls']:
        raise ValueError('Narration exceeds approved request/character bounds')
    canonical(value)
    return root, cfg, value


def result_path(value):
    return f"runs/narration/{value['job_id']}/result.json"


def assert_current(path, value, root):
    if sha(request(path, root)[2]) != sha(value):
        raise ValueError('Narration request changed during execution')


def captions(rows, text, duration):
    if not isinstance(rows, list) or not rows or len(rows) > 1000:
        raise ValueError('Narration needs explicit caption timings')
    previous = 0
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'start', 'end', 'text'}
                or not number(row['start'], previous, duration) or not number(row['end'], row['start'], duration)
                or row['end'] <= row['start'] or not isinstance(row['text'], str) or not row['text'].strip()):
            raise ValueError('Invalid or nonmonotonic narration captions')
        previous = row['end']
    if ' '.join(' '.join(r['text'] for r in rows).split()) != ' '.join(text.split()):
        raise ValueError('Caption text differs from the reviewed narration')
    return rows


def pcm(path, max_seconds=180):
    try:
        with wave.open(str(path), 'rb') as wav:
            count = wav.getnframes()
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, RATE):
                raise ValueError('Renderer narration must be mono 48 kHz PCM16')
            if not 0 < count <= RATE * max_seconds:
                raise ValueError('Narration duration outside bounds')
            data = wav.readframes(count)
            if len(data) != count*2:
                raise ValueError('Truncated narration WAV')
            return data
    except (wave.Error, EOFError):
        raise ValueError('Invalid narration WAV') from None


def write_pcm(path, data):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE)
        wav.writeframes(data)


def convert(source, target, limits):
    # Full decode, bounded output length and no overwrite; partial output is never published.
    if source.stat().st_size > limits['max_response_bytes']:
        raise ValueError('Source narration exceeds byte bound')
    cmd = ['ffmpeg', '-v', 'error', '-xerror', '-n', '-i', str(source), '-map', '0:a:0',
           '-ar', str(RATE), '-ac', '1', '-c:a', 'pcm_s16le',
           '-fs', str(int((limits['max_audio_seconds']+1)*RATE*2+4096)), str(target)]
    try:
        run = subprocess.run(cmd, capture_output=True, timeout=limits['timeout_seconds'])
        if run.returncode:
            raise ValueError('Narration audio decode failed')
    except subprocess.TimeoutExpired:
        raise ValueError('Narration audio decode timed out') from None
    data = pcm(target, limits['max_audio_seconds'])
    # Verify input duration as well: FFmpeg's file-size cap must not silently truncate long input.
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'json', str(source)], capture_output=True, timeout=20)
    try:
        duration = float(json.loads(probe.stdout)['format']['duration'])
    except (ValueError, KeyError, json.JSONDecodeError):
        raise ValueError('Narration source duration unavailable') from None
    if not number(duration, 0.001, limits['max_audio_seconds']) or abs(duration-len(data)/2/RATE) > .1:
        raise ValueError('Narration source was truncated or exceeds duration bound')
    return data


def validate_result(value, result, root):
    _, _, identity = workspace(root)
    if (not isinstance(result, dict) or result.get('schema_version') != 'f1.narration_result.v1'
            or result.get('event_identity') != identity or result.get('request_sha256') != sha(value)
            or result.get('format') != value['format'] or result.get('job_id') != value['job_id']):
        raise ValueError('Stale or mismatched narration result')
    verify(result['request'], root)
    if sha(load(result['request']['path'], root)) != sha(value):
        raise ValueError('Narration saved request changed')
    if result.get('provider') != value['provider']:
        raise ValueError('Narration provider settings changed')
    rows = result.get('scenes', [])
    if len(rows) != len(value['scenes']):
        raise ValueError('Incomplete narration result')
    for scene, row in zip(value['scenes'], rows):
        if row.get('id') != scene['id'] or row.get('text_sha256') != sha(scene['text']):
            raise ValueError('Narration scene/text changed')
        verify(row['original'], root)
        data = pcm(verify(row['clean'], root), value['limits']['max_audio_seconds'])
        duration = len(data)/2/RATE
        if row.get('samples') != len(data)//2 or row.get('sample_rate') != RATE or row.get('duration') != duration:
            raise ValueError('Narration sample count/duration changed')
        captions(row['captions'], scene['text'], duration)
        for link in row.get('native_originals', []): verify(link, root)
    for link in result.get('provenance', []):
        verify(link, root)
    for link in result.get('model_runs', []):
        verify(link, root)
    return result


def prepare(path, root=None):
    root, _, value = request(path, root)
    cached = safe_relative(result_path(value), root=root)
    hit = cached.is_file()
    if hit:
        validate_result(value, load(cached, root), root)
    misses = value['scenes']
    if not hit and value['provider']['kind'] in {'say', 'elevenlabs'}:
        from .speech_provider import cached_scene
        misses = [s for s in value['scenes'] if cached_scene(value, s, root) is None]
    return {'status': 'preflight', 'job_id': value['job_id'], 'request_sha256': sha(value),
            'provider': value['provider'], 'format': value['format'], 'cache_hit': hit,
            'calls': 0 if hit else len(misses),
            'characters': 0 if hit else sum(len(s['text']) for s in misses),
            'provider_calls': False, 'actual_cost_usd': None}


def new_job(value, root, cfg):
    ensure_space(4*value['limits']['max_response_bytes']*len(value['scenes']), root=root, reserve=cfg['reserve_bytes'])
    directory = safe_relative(f"runs/narration/{value['job_id']}", root=root)
    if directory.exists():
        raise ValueError('Narration job exists; do not repeat a possibly billed/interrupted execution')
    if safe_relative(f"runs/model-evaluations/narration/{value['job_id']}.json", root=root).exists():
        raise ValueError('Narration model-work identifier already exists')
    if safe_relative(f"runs/model-evaluations/narration/{value['job_id']}.assets", root=root).exists():
        raise ValueError('Narration execution intent already exists')
    directory.mkdir(parents=True)
    write_json(directory/'request.json', value)
    return directory


def make_result(value, directory, rows, provenance, root, publish=True):
    result = {'schema_version': 'f1.narration_result.v1', 'job_id': value['job_id'],
              'event_identity': value['event_identity'], 'event_id': value['event_identity']['id'],
              'format': value['format'], 'request_sha256': sha(value),
              'request': binding(directory/'request.json', root), 'provider': value['provider'],
              'scenes': rows, 'provenance': provenance, 'created_at': now(), 'human_acceptance': 'not_inferred'}
    validate_result(value, result, root)
    if publish:
        write_json(directory/'result.json', result)
    return result


def scene_result(scene, original, clean, cue_rows, value, root):
    data = pcm(clean, value['limits']['max_audio_seconds'])
    duration = len(data)/2/RATE
    return {'id': scene['id'], 'text_sha256': sha(scene['text']), 'original': binding(original, root),
            'clean': binding(clean, root), 'samples': len(data)//2, 'sample_rate': RATE,
            'duration': duration, 'captions': captions(cue_rows, scene['text'], duration)}


def import_audio(path, bundle_path, root=None):
    root, cfg, value = request(path, root)
    if value['provider']['kind'] != 'imported':
        raise ValueError('Use an imported request for operator-supplied audio')
    bundle = load(bundle_path, root)
    if (not isinstance(bundle, dict) or set(bundle) != {'schema_version', 'request_sha256', 'provenance', 'scenes'}
            or bundle['schema_version'] != 'f1.narration_import.v1' or bundle['request_sha256'] != sha(value)
            or not isinstance(bundle['provenance'], dict) or bundle['provenance'].get('kind') != 'operator_import'
            or not isinstance(bundle['provenance'].get('reference'), str) or not bundle['provenance']['reference'].strip()
            or len(bundle.get('scenes', [])) != len(value['scenes'])):
        raise ValueError('Invalid or stale narration import bundle/provenance')
    for scene, row in zip(value['scenes'], bundle['scenes']):
        if not isinstance(row, dict) or set(row) != {'id', 'audio', 'captions', 'reviewed_by'} or row['id'] != scene['id']:
            raise ValueError('Imported scenes must match request order')
        if not isinstance(row['reviewed_by'], str) or not row['reviewed_by'].strip():
            raise ValueError('Imported timings need an explicit reviewer')
        verify(row['audio'], root)
    directory = new_job(value, root, cfg)
    write_json(directory/'import.json', bundle)
    rows = []
    for scene, row in zip(value['scenes'], bundle['scenes']):
        original = directory/(scene['id']+'-original'+verify(row['audio'], root).suffix)
        shutil.copyfile(verify(row['audio'], root), original)
        if digest(original) != row['audio']['sha256']:
            raise ValueError('Imported source changed during copy')
        clean = directory/(scene['id']+'-clean.wav')
        convert(original, clean, value['limits'])
        rows.append(scene_result(scene, original, clean, row['captions'], value, root))
    assert_current(path, value, root)
    return make_result(value, directory, rows, [binding(directory/'import.json', root)], root)


def effect_recipe(value):
    if not isinstance(value, dict) or value.get('schema_version') != 'f1.narration_effect.v1':
        raise ValueError('Unsupported narration effect schema')
    if value.get('kind') == 'none' and set(value) == {'schema_version', 'kind'}:
        return value
    fields = {'schema_version', 'kind', 'processor_sha256', 'options'}
    if value.get('kind') != 'robot_vocoder' or set(value) != fields or not re.fullmatch('[0-9a-f]{64}', value['processor_sha256']):
        raise ValueError('Explicit vocoder processor hash/options required')
    o = value['options']
    if not isinstance(o, dict) or set(o) != {'mode', 'note', 'brightness', 'clarity', 'wet', 'tempo', 'echo', 'progression', 'progressionBeats'}:
        raise ValueError('Complete vocoder settings required')
    if o['mode'] not in {'single', 'chord', 'melody', 'progression'} or o['progression'] not in {'minor', 'pop', 'warm', 'cadence'} or type(o['progressionBeats']) is not int or o['progressionBeats'] not in {1, 2, 4}:
        raise ValueError('Invalid vocoder mode/progression')
    for key, low, high in [('note', 36, 72), ('tempo', 60, 180), ('brightness', 0, 1), ('clarity', 0, 1), ('wet', 0, 1), ('echo', 0, 1)]:
        if not number(o[key], low, high):
            raise ValueError('Invalid vocoder setting: ' + key)
    return value


def process(path, effect_path, *, processor=None, root=None):
    root, cfg, value = request(path, root)
    result_link = binding(result_path(value), root)
    result = validate_result(value, load(result_link['path'], root), root)
    effect = effect_recipe(load(effect_path, root))
    recipe_link = binding(effect_path, root)
    executable = None
    if effect['kind'] == 'robot_vocoder':
        if processor is None or not Path(processor).is_absolute():
            raise ValueError('Vocoder requires an explicit absolute --dsp-module path')
        executable = Path(processor).resolve()
        if digest(executable) != effect['processor_sha256']:
            raise ValueError('External vocoder processor hash mismatch')
    key = sha({'result': result_link, 'effect': effect, 'recipe': 'track-pcm48-v1',
               'wrapper': digest(Path(__file__).with_name('resources')/'robot_vocoder.cjs')})
    directory = safe_relative(f"runs/narration/{value['job_id']}/effects/{key}", root=root)
    if directory.exists():
        selected = load(directory/'selection.json', root)
        validate_selection(selected, root)
        select(selected, root)
        return selected
    ensure_space(RATE*2*182*4, root=root, reserve=cfg['reserve_bytes'])
    directory.mkdir(parents=True)
    segments = []; dry = bytearray()
    for row in result['scenes']:
        data = pcm(verify(row['clean'], root), value['limits']['max_audio_seconds'])
        count = len(data)//2
        padded = math.ceil(count/FRAME_SAMPLES)*FRAME_SAMPLES
        segments.append((row, len(dry)//2, padded))
        dry.extend(data); dry.extend(bytes((padded-count)*2))
    if len(dry)//2 > RATE*180:
        raise ValueError('Assembled narration exceeds the 180-second processor limit')
    write_pcm(directory/'dry.wav', dry)
    if executable:
        wrapper = Path(__file__).with_name('resources')/'robot_vocoder.cjs'
        try:
            outcome = subprocess.run(['node', str(wrapper), str(executable), str(directory/'dry.wav'),
                                      str(directory/'processed.wav'), canonical(effect['options']).decode()],
                                     capture_output=True, timeout=120,
                                     env={k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'LC_ALL', 'TMPDIR'}})
        except subprocess.TimeoutExpired:
            raise ValueError('Vocoder processing timed out') from None
        if outcome.returncode:
            raise ValueError('Vocoder processing failed; inspect the configured external module')
        if digest(executable) != effect['processor_sha256']:
            raise ValueError('Vocoder processor changed during processing')
        processed = pcm(directory/'processed.wav', 181)
        tail = .6 if effect['options']['echo'] > 0 else 0
        expected = len(dry)//2 + round(RATE*tail)
        if len(processed)//2 != expected:
            raise ValueError('Vocoder changed the narration time axis')
    else:
        processed = bytes(dry)
        tail = 0
    rows = []
    for index, (row, start, count) in enumerate(segments):
        extra = math.ceil(round(tail*RATE)/FRAME_SAMPLES)*FRAME_SAMPLES if index == len(segments)-1 else 0
        data = processed[start*2:(start+count+extra)*2]
        data += bytes((count+extra)*2-len(data))
        if executable is None and count == row['samples']:
            audio = row['clean']  # Exact container bytes as well as PCM for a frame-aligned bypass.
        else:
            target = directory/(row['id']+'.wav'); write_pcm(target, data)
            audio = binding(target, root)
        rows.append({'id': row['id'], 'text_sha256': row['text_sha256'], 'audio': audio,
                     'duration': len(data)/2/RATE, 'samples': len(data)//2,
                     'captions': row['captions'], 'tail_seconds': extra/RATE})
    receipt = {'event_identity': value['event_identity'], 'event_id': value['event_identity']['id'],
               'source_result': result_link, 'effect': effect, 'dry_track': binding(directory/'dry.wav', root),
               'effect_recipe': recipe_link, 'processor_rate': 22050 if executable else None,
               'scenes': rows, 'provider_calls': False, 'created_at': now(), 'human_acceptance': 'not_inferred'}
    write_json(directory/'receipt.json', receipt)
    selected = {'schema_version': 'f1.narration_selection.v1', 'event_identity': value['event_identity'],
                'request': result['request'], 'source_result': result_link, 'format': value['format'],
                'effect_receipt': binding(directory/'receipt.json', root), 'effect_recipe': recipe_link,
                'provider': value['provider'], 'effect': effect, 'scenes': rows,
                'model_runs': result.get('model_runs', [])}
    assert_current(path, value, root)
    validate_selection(selected, root)
    write_json(directory/'selection.json', selected)
    select(selected, root)
    return selected


def validate_selection(selected, root=None):
    root, _, identity = workspace(root)
    if selected.get('schema_version') != 'f1.narration_selection.v1' or selected.get('event_identity') != identity:
        raise ValueError('Narration selection event/schema mismatch')
    verify(selected['request'], root)
    _, _, value = request(selected['request']['path'], root)
    result = validate_result(value, load(verify(selected['source_result'], root), root), root)
    recipe = effect_recipe(load(verify(selected['effect_recipe'], root), root))
    receipt = load(verify(selected['effect_receipt'], root), root)
    if (selected.get('format') != value['format'] or selected.get('provider') != value['provider']
            or selected.get('effect') != recipe or receipt.get('effect') != recipe
            or receipt.get('source_result') != selected['source_result']
            or receipt.get('event_identity') != identity or receipt.get('scenes') != selected.get('scenes')):
        raise ValueError('Narration effect/source selection mismatch')
    verify(receipt['dry_track'], root)
    rows = selected.get('scenes', [])
    if len(rows) != len(value['scenes']):
        raise ValueError('Incomplete narration selection')
    for index, (scene, dry, row) in enumerate(zip(value['scenes'], result['scenes'], rows)):
        if row.get('id') != scene['id'] or row.get('text_sha256') != sha(scene['text']) or row.get('captions') != dry['captions']:
            raise ValueError('Narration selected text/timings changed')
        data = pcm(verify(row['audio'], root), 181)
        expected = math.ceil(dry['samples']/FRAME_SAMPLES)*FRAME_SAMPLES
        tail = math.ceil(.6*24)/24 if recipe['kind'] == 'robot_vocoder' and recipe['options']['echo'] > 0 and index == len(rows)-1 else 0
        if (row.get('samples') != len(data)//2 or row.get('samples') != expected+round(tail*RATE)
                or row.get('duration') != len(data)/2/RATE or row.get('tail_seconds') != tail):
            raise ValueError('Narration selected timing/tail changed')
        captions(row['captions'], scene['text'], row['duration'])
    return selected


def selected_narration(format_name, root=None):
    root, _, _ = workspace(root)
    return selections(root).get(format_name)


def selections(root):
    path = safe_relative(SELECTION, root=root)
    if not path.exists():
        return {}
    registry = load(path, root)
    _, cfg, identity = workspace(root)
    if registry.get('schema_version') != 'f1.narration_selections.v1' or registry.get('event_identity') != identity:
        raise ValueError('Narration selections event/schema mismatch')
    formats = registry.get('formats')
    if not isinstance(formats, dict) or not formats or set(formats)-set(cfg.get('formats', ['vertical', 'landscape'])):
        raise ValueError('Invalid narration selected formats')
    for name, selected in formats.items():
        if validate_selection(selected, root)['format'] != name:
            raise ValueError('Narration selected format mismatch')
    return formats


def select(selected, root):
    # Replacing one format may recover a stale selection for that same format;
    # other formats must still validate before the registry can be published.
    path = safe_relative(SELECTION, root=root)
    registry = load(path, root) if path.exists() else {'schema_version': 'f1.narration_selections.v1',
                'event_identity': selected['event_identity'], 'formats': {}}
    registry['formats'][selected['format']] = selected
    for item in registry['formats'].values(): validate_selection(item, root)
    if registry.get('event_identity') != selected['event_identity']:
        raise ValueError('Existing narration selections belong to another event')
    write_json(path, registry)


def selection_inputs(root=None):
    root, _, _ = workspace(root)
    if not safe_relative(SELECTION, root=root).exists():
        return set()
    selected = selections(root)
    paths = {SELECTION}
    def collect(value):
        if isinstance(value, dict):
            if set(value) == {'path', 'sha256'}:
                verify(value, root); paths.add(value['path'])
            else:
                for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(selected)
    for item in selected.values():
        for key in ('source_result', 'effect_receipt'):
            collect(load(item[key]['path'], root))
    return paths
