"""Explicit ElevenLabs/system-speech jobs; no credentials or calls during render."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from . import narration as n
from .core import digest, now, safe_relative, write_json


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_settings(provider):
    for key, limit in [('voice', 100), ('model', 80)]:
        if not isinstance(provider[key], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,'+str(limit)+'}', provider[key]):
            raise ValueError('Invalid ElevenLabs ' + key)
    settings = provider['settings']
    required = {'output_format', 'voice_settings', 'seed', 'apply_text_normalization', 'pronunciation_dictionary_locators'}
    if not isinstance(settings, dict) or set(settings) != required:
        raise ValueError('Complete effective ElevenLabs settings required')
    if settings['output_format'] not in {'mp3_44100_128', 'mp3_44100_192', 'mp3_22050_32'}:
        raise ValueError('Unsupported ElevenLabs audio format')
    if settings['apply_text_normalization'] not in {'auto', 'on', 'off'}:
        raise ValueError('Invalid speech normalization')
    seed = settings['seed']
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 4294967295):
        raise ValueError('Invalid speech seed')
    voice = settings['voice_settings']
    expected = {'stability'} if provider['model'] == 'eleven_v3' else {'speed', 'stability', 'similarity_boost', 'style', 'use_speaker_boost'}
    if not isinstance(voice, dict) or set(voice) != expected:
        raise ValueError('Unsupported effective voice settings for this model')
    for key, value in voice.items():
        if key == 'use_speaker_boost':
            if type(value) is not bool: raise ValueError('Invalid speaker boost')
        elif not n.number(value, .7 if key == 'speed' else 0, 1.2 if key == 'speed' else 1):
            raise ValueError('Invalid effective voice setting')
    if provider['model'] == 'eleven_v3' and voice['stability'] not in [0, .5, 1]:
        raise ValueError('Eleven v3 stability must be 0, 0.5 or 1')
    dictionaries = settings['pronunciation_dictionary_locators']
    if not isinstance(dictionaries, list) or len(dictionaries) > 3:
        raise ValueError('At most three pronunciation dictionaries are supported')
    for row in dictionaries:
        if not isinstance(row, dict) or set(row) != {'pronunciation_dictionary_id', 'version_id'}:
            raise ValueError('Pronunciation dictionaries require pinned versions')
        for value in row.values():
            if not isinstance(value, str) or not re.fullmatch('[a-zA-Z0-9_-]{1,100}', value):
                raise ValueError('Invalid pronunciation dictionary/version')


def alignment_captions(alignment, text, duration):
    if not isinstance(alignment, dict):
        raise ValueError('Provider character alignment missing')
    chars = alignment.get('characters')
    starts = alignment.get('character_start_times_seconds')
    ends = alignment.get('character_end_times_seconds')
    if (not isinstance(chars, list) or not all(isinstance(c, str) and len(c) == 1 for c in chars)
            or ''.join(chars) != text or not isinstance(starts, list) or not isinstance(ends, list)
            or len(chars) != len(starts) or len(chars) != len(ends)):
        raise ValueError('Provider alignment does not map to the reviewed text')
    previous_start = previous_end = 0
    for start, end in zip(starts, ends):
        if not n.number(start, previous_start, duration) or not n.number(end, max(start, previous_end), duration):
            raise ValueError('Invalid provider character timing')
        previous_start, previous_end = start, end
    words = list(re.finditer(r'\S+', text))
    rows = []
    for offset in range(0, len(words), 12):
        group = words[offset:offset+12]
        first, last = group[0].start(), group[-1].end()
        rows.append({'start': starts[first], 'end': ends[last-1], 'text': text[first:last]})
    return n.captions(rows, text, duration)


def cache_key(value, scene):
    return n.sha({'provider': value['provider'], 'text': scene['text'], 'recipe': 'scene-alignment-v1'})


def cached_scene(value, scene, root):
    path = safe_relative('runs/narration/cache/'+cache_key(value, scene)+'.json', root=root)
    if not path.exists(): return None
    cached = n.load(path, root)
    if cached.get('key') != cache_key(value, scene): raise ValueError('Narration cache request changed')
    row = cached['scene']
    n.verify(row['original'], root)
    data = n.pcm(n.verify(row['clean'], root), value['limits']['max_audio_seconds'])
    if row['samples'] != len(data)//2 or row['duration'] != len(data)/2/n.RATE or row['text_sha256'] != n.sha(scene['text']):
        raise ValueError('Narration cache audio/text changed')
    n.captions(row['captions'], scene['text'], row['duration'])
    n.verify(cached['provider_receipt'], root)
    return cached


def authorization(path, value, preview, root):
    auth = n.load(path, root)
    fields = {'schema_version', 'request_sha256', 'source', 'provider', 'max_calls', 'max_characters',
              'max_credits', 'credits_per_character', 'rate_reference'}
    if (not isinstance(auth, dict) or set(auth) != fields or auth['schema_version'] != 'f1.narration_authorization.v1'
            or auth['request_sha256'] != n.sha(value) or auth['provider'] != 'elevenlabs'
            or not isinstance(auth['source'], dict) or set(auth['source']) != {'kind', 'reviewer', 'reference'}
            or auth['source']['kind'] != 'human'
            or any(not isinstance(auth['source'][k], str) or not auth['source'][k].strip() for k in ('reviewer', 'reference'))
            or type(auth['max_calls']) is not int or not preview['calls'] <= auth['max_calls'] <= value['limits']['max_calls']
            or type(auth['max_characters']) is not int or not preview['characters'] <= auth['max_characters'] <= value['limits']['max_characters']
            or not n.number(auth['credits_per_character'], .001, 100)
            or not n.number(auth['max_credits'], .001, 20000000)
            or auth['max_credits'] < preview['characters']*auth['credits_per_character']
            or not isinstance(auth['rate_reference'], str) or not auth['rate_reference'].strip()):
        raise ValueError('Current request-bound human authorization and credit ceiling required')
    return auth


def execute(path, *, authorization_path=None, execute=False, api_key=None, opener=None, root=None):
    root, cfg, value = n.request(path, root)
    preview = n.prepare(path, root)
    if not execute: return preview
    kind = value['provider']['kind']
    if kind not in {'elevenlabs', 'say'}:
        raise ValueError('Use speech-import for imported audio')
    if preview['cache_hit']:
        return n.validate_result(value, n.load(n.result_path(value), root), root)
    cache = [cached_scene(value, scene, root) for scene in value['scenes']]
    auth = None
    if kind == 'elevenlabs' and any(c is None for c in cache):
        if authorization_path is None: raise ValueError('Hosted speech requires --authorization')
        auth = authorization(authorization_path, value, preview, root)
        from .credentials import resolve_api_key, valid_key
        key = resolve_api_key('elevenlabs') if api_key is None else api_key
        if not valid_key(key): raise ValueError('ElevenLabs credential unavailable; no request sent')
    directory = n.new_job(value, root, cfg)
    intent = {'status': 'execution_requested', 'event_identity': value['event_identity'],
              'request_sha256': n.sha(value), 'provider': value['provider'], 'created_at': now(),
              'authorization': n.binding(authorization_path, root) if auth else None,
              'preflight': preview}
    write_json(directory/'intent.json', intent)
    model_intent = {**intent, 'task': 'narration_voice', 'format': 'audio',
                    'inputs': [n.binding(directory/'request.json', root)], 'evidence': [value['plan']]}
    write_json(safe_relative(f"runs/model-evaluations/narration/{value['job_id']}.assets/intent.json", root=root), model_intent)
    rows = []; provenance = [n.binding(directory/'intent.json', root)]
    start = time.monotonic(); calls = 0
    try:
        for scene, cached in zip(value['scenes'], cache):
            cached = cached or cached_scene(value, scene, root)
            if cached:
                row = dict(cached['scene']); row['id'] = scene['id']
                rows.append(row); provenance.append(cached['provider_receipt'])
                continue
            receipt = {'provider': kind, 'requested_model': value['provider']['model'],
                       'voice': value['provider']['voice'], 'settings': value['provider']['settings'],
                       'text_sha256': n.sha(scene['text']), 'submitted_characters': len(scene['text']),
                       'provider_request_id': None, 'actual_cost_usd': None, 'actual_credits': None,
                       'status': 'attempted', 'created_at': now(), 'http_status': None}
            receipt_path = directory/(scene['id']+'-provider.json')
            write_json(receipt_path, receipt)  # A possibly billed attempt is visible before transport.
            original = directory/(scene['id']+('-original.mp3' if kind == 'elevenlabs' else '-original.wav'))
            native_originals = []
            if kind == 'say':
                from .render import phrases
                assembled = bytearray(); cue_rows = []
                for index, text in enumerate(phrases(scene['text'])):
                    phrase = directory/f"{scene['id']}-phrase-{index}.aiff"
                    outcome = subprocess.run(['say', '-v', 'Samantha', '-r', str(value['provider']['settings']['words_per_minute']),
                                              '-o', str(phrase), text], capture_output=True,
                                             timeout=value['limits']['timeout_seconds'])
                    if outcome.returncode: raise ValueError('System speech generation failed')
                    phrase_wav = directory/f"{scene['id']}-phrase-{index}.wav"
                    chunk = n.convert(phrase, phrase_wav, value['limits'])
                    offset = len(assembled)/2/n.RATE
                    assembled.extend(chunk)
                    cue_rows.append({'start': offset, 'end': len(assembled)/2/n.RATE, 'text': text})
                    native_originals.append(n.binding(phrase, root))
                n.write_pcm(original, assembled)
            else:
                # Recheck the authorization and frozen request before each billable scene.
                n.assert_current(path, value, root)
                if n.binding(authorization_path, root) != intent['authorization']:
                    raise ValueError('Speech authorization changed during execution')
                authorization(authorization_path, value, preview, root)
                body = {'text': scene['text'], 'model_id': value['provider']['model'],
                        **{k: v for k, v in value['provider']['settings'].items() if k != 'output_format'}}
                if body['seed'] is None: del body['seed']
                endpoint = 'https://api.elevenlabs.io/v1/text-to-speech/'+value['provider']['voice']+'/with-timestamps?'+urllib.parse.urlencode({'output_format': value['provider']['settings']['output_format']})
                req = urllib.request.Request(endpoint, data=n.canonical(body), method='POST',
                                             headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
                transport = opener or urllib.request.build_opener(NoRedirect())
                calls += 1
                with transport.open(req, timeout=value['limits']['timeout_seconds']) as response:
                    receipt['http_status'] = response.getcode()
                    if response.geturl() != endpoint or response.getcode() != 200:
                        raise ValueError('Speech response endpoint/status rejected; redirects refused')
                    raw = response.read(value['limits']['max_response_bytes']+1)
                    if len(raw) > value['limits']['max_response_bytes']: raise ValueError('Speech response exceeds byte bound')
                    rid = response.headers.get('request-id')
                    if isinstance(rid, str) and re.fullmatch('[a-zA-Z0-9_-]{1,128}', rid): receipt['provider_request_id'] = rid
                receipt['response_sha256'] = hashlib.sha256(raw).hexdigest()
                payload = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite speech response')))
                audio = base64.b64decode(payload['audio_base64'], validate=True)
                if not audio or len(audio) > value['limits']['max_response_bytes']: raise ValueError('Invalid speech audio size')
                original.write_bytes(audio)
                receipt.update(status='response_received', response_bytes=len(raw))
                write_json(receipt_path, receipt)
            clean = directory/(scene['id']+'-clean.wav')
            data = n.convert(original, clean, value['limits'])
            duration = len(data)/2/n.RATE
            if kind != 'say': cue_rows = alignment_captions(payload.get('alignment'), scene['text'], duration)
            if kind != 'say':
                alignment_path = directory/(scene['id']+'-alignment.json')
                write_json(alignment_path, {k: payload['alignment'][k] for k in (
                    'characters', 'character_start_times_seconds', 'character_end_times_seconds')})
                provenance.append(n.binding(alignment_path, root))
            row = n.scene_result(scene, original, clean, cue_rows, value, root)
            if native_originals: row['native_originals'] = native_originals
            receipt.update(status='succeeded', original=row['original'], clean=row['clean'], duration=duration)
            write_json(receipt_path, receipt)
            rows.append(row); provenance.append(n.binding(receipt_path, root))
            cache_path = safe_relative('runs/narration/cache/'+cache_key(value, scene)+'.json', root=root)
            write_json(cache_path, {'key': cache_key(value, scene), 'scene': row, 'provider_receipt': n.binding(receipt_path, root)})
        n.assert_current(path, value, root)
        result = n.make_result(value, directory, rows, provenance, root, publish=False)
        _model_work(value, result, directory, root, kind, time.monotonic()-start, calls)
        return n.load(directory/'result.json', root)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        # Provider error bodies and exception text may contain credentials; retain only safe categories.
        status = error.code if isinstance(error, urllib.error.HTTPError) else None
        write_json(directory/'failure.json', {'status': 'failed', 'event_identity': value['event_identity'],
                   'http_status': status, 'error': 'Narration execution failed; do not automatically repeat this job',
                   'provider_calls_attempted': calls, 'actual_cost_usd': None, 'actual_credits': None})
        try:
            _model_work(value, None, directory, root, kind, time.monotonic()-start, calls)
        except (ValueError, OSError, KeyError, TypeError):
            pass  # The mirrored execution intent retains incomplete-work accounting.
        raise ValueError('Narration execution failed; inspect retained receipts before any new execution') from None


def _model_work(value, result, directory, root, kind, seconds, calls):
    from .model_evaluation import import_model_work
    failed = result is None
    provenance = ([n.binding(directory/'intent.json', root), n.binding(directory/'failure.json', root)]
                  if failed else result['provenance'])
    record = {'schema_version': 'f1.model_work.v1', 'work_id': value['job_id'], 'comparison_id': 'narration',
              'task': 'narration_voice', 'format': 'audio', 'event_id': value['event_identity']['id'],
              'event_identity': value['event_identity'], 'prompt_version': 'narration-v1', 'rubric_version': None,
              'preference_version': None, 'preference_binding': None,
              'inputs': [n.binding(directory/'request.json', root)], 'evidence': [value['plan']],
              'attempts': [{'attempt_id': 'attempt-1', 'status': 'failed' if failed else 'completed',
                  'error': 'Narration execution failed; inspect retained provider receipts' if failed else None,
                  'model': {'provider': kind, 'model': value['provider']['model'], 'revision': None,
                            'quantization': None, 'session_reference': None, 'identity_source': 'unknown',
                            'access': 'hosted_api' if kind == 'elevenlabs' else 'deterministic',
                            'settings': {'voice': value['provider']['voice'], **value['provider']['settings'], 'provider_calls': calls}},
                  'outputs': [] if failed else [s['clean'] for s in result['scenes']], 'provenance': provenance,
                  'eligibility': {'status': 'not_reviewed', 'failures': [], 'review_files': []},
                  'usage': {'input_tokens': None, 'output_tokens': None, 'reasoning_tokens': None,
                            'cost_usd': None, 'estimated_cost_usd': None, 'machine_seconds': seconds,
                            'human_revision_seconds': None, 'token_scope': 'unknown', 'cost_source': 'unknown'}}]}
    write_json(directory/'model-work.json', record)
    imported = import_model_work(directory/'model-work.json', root=root)
    if not failed:
        result['model_runs'] = [{'path': imported['receipt_path'], 'sha256': imported['sha256']}]
        write_json(directory/'result.json', result)
