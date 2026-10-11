import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from f1_pipeline import narration as n, speech_provider as provider
from f1_pipeline.core import write_json

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class Response:
    def __init__(self, payload, endpoint, status=200):
        self.raw = json.dumps(payload).encode(); self.endpoint = endpoint; self.status = status
        self.headers = {'request-id': 'synthetic-request'}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit): return self.raw[:limit]
    def geturl(self): return self.endpoint
    def getcode(self): return self.status


class Transport:
    def __init__(self, audio): self.audio = audio; self.calls = []
    def open(self, req, timeout):
        self.calls.append(req)
        text = json.loads(req.data)['text']
        tick = .8/len(text)
        return Response({'audio_base64': base64.b64encode(self.audio).decode(), 'alignment': {
            'characters': list(text), 'character_start_times_seconds': [i*tick for i in range(len(text))],
            'character_end_times_seconds': [(i+1)*tick for i in range(len(text))]}}, req.full_url)


class NarrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        cfg = json.loads((PACKAGE_ROOT/'examples/synthetic/config/event.json').read_text())
        cfg['reserve_bytes'] = 1; cfg['formats'] = ['vertical', 'landscape']
        write_json(self.root/'config/event.json', cfg)
        identity = {k: cfg[k] for k in n.IDENTITY_KEYS}
        self.scenes = [{'id': 'opening', 'text': 'A verified synthetic opening.'},
                       {'id': 'ending', 'text': 'The measured gap was small.'}]
        self.plan = {'event_id': cfg['id'], 'formats': {f: {'scenes': [
            {'id': s['id'], 'narration': s['text']} for s in self.scenes]} for f in cfg['formats']}}
        write_json(self.root/'research/event/video_plan.json', self.plan)
        self.value = {'schema_version': 'f1.narration_request.v1', 'job_id': 'fixture',
                      'event_identity': identity, 'plan': n.binding('research/event/video_plan.json', self.root),
                      'format': 'vertical', 'provider': {'kind': 'imported', 'model': None, 'voice': None, 'settings': {}},
                      'scenes': deepcopy(self.scenes), 'limits': {'max_characters': 2000, 'max_calls': 2,
                      'timeout_seconds': 10, 'max_response_bytes': 1000000, 'max_audio_seconds': 10}}
        self.path = 'research/event/narration-request.json'; self.save()
        audio = self.root/'research/event/source.wav'
        n.write_pcm(audio, (b'\x00\x10\x00\xf0')*(n.RATE//2))
        self.audio = audio.read_bytes()
        self.bundle = {'schema_version': 'f1.narration_import.v1', 'request_sha256': n.sha(self.value),
                       'provenance': {'kind': 'operator_import', 'reference': 'Synthetic fixture only'},
                       'scenes': [{'id': s['id'], 'audio': n.binding(audio, self.root), 'reviewed_by': 'synthetic test',
                                   'captions': [{'start': .1, 'end': .8, 'text': s['text']}]} for s in self.scenes]}
        self.bundle_path = 'research/event/import.json'
        self.effect_path = 'research/event/effect.json'
        write_json(self.root/self.effect_path, {'schema_version': 'f1.narration_effect.v1', 'kind': 'none'})
        self.decode = patch.object(n, 'convert', side_effect=self.copy_decode); self.decode.start(); self.addCleanup(self.decode.stop)

    def copy_decode(self, source, target, limits):
        shutil.copyfile(source, target); return n.pcm(target, limits['max_audio_seconds'])

    def save(self): write_json(self.root/self.path, self.value)

    def imported(self):
        self.bundle['request_sha256'] = n.sha(self.value)
        write_json(self.root/self.bundle_path, self.bundle)
        return n.import_audio(self.path, self.bundle_path, self.root)

    def hosted(self):
        self.value['provider'] = {'kind': 'elevenlabs', 'model': 'eleven_multilingual_v2', 'voice': 'voice12345678',
            'settings': {'output_format': 'mp3_44100_128', 'seed': 0, 'apply_text_normalization': 'auto',
                         'pronunciation_dictionary_locators': [], 'voice_settings': {'speed': 1, 'stability': .5,
                         'similarity_boost': .75, 'style': 0, 'use_speaker_boost': True}}}
        self.save()
        path = 'research/event/authorization.json'
        write_json(self.root/path, {'schema_version': 'f1.narration_authorization.v1', 'request_sha256': n.sha(self.value),
            'source': {'kind': 'human', 'reviewer': 'fixture', 'reference': 'Synthetic test authorization'},
            'provider': 'elevenlabs', 'max_calls': 2, 'max_characters': 2000, 'max_credits': 2000,
            'credits_per_character': 1, 'rate_reference': 'Synthetic rate; no provider billing'})
        return path

    def test_import_bypass_preserves_source_and_invalidates_changed_audio(self):
        result = self.imported()
        source_hash = result['scenes'][0]['clean']['sha256']
        selected = n.process(self.path, self.effect_path, root=self.root)
        self.assertEqual(selected['scenes'][0]['audio']['sha256'], source_hash)
        self.assertEqual(selected['scenes'][0]['duration'], 1)
        self.assertEqual(n.selected_narration('vertical', self.root), selected)
        self.assertIsNone(n.selected_narration('landscape', self.root))
        self.assertIn(n.SELECTION, n.selection_inputs(self.root))
        (self.root/selected['scenes'][0]['audio']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'): n.selected_narration('vertical', self.root)

    def test_stale_identity_plan_and_text_fail_before_writes(self):
        for change in ('identity', 'plan', 'text'):
            value = deepcopy(self.value)
            if change == 'identity': value['event_identity']['session_key'] += 1
            if change == 'plan': value['plan']['sha256'] = '0'*64
            if change == 'text': value['scenes'][0]['text'] = 'Different narration.'
            write_json(self.root/self.path, value)
            with self.assertRaises(ValueError): n.prepare(self.path, self.root)
        self.assertFalse((self.root/'runs/narration').exists())

    def test_nonfinite_overlapping_missing_and_wrong_text_timings_rejected(self):
        for rows in ([], [{'start': float('nan'), 'end': .8, 'text': self.scenes[0]['text']}],
                     [{'start': 0, 'end': .8, 'text': 'Wrong text'}],
                     [{'start': 0, 'end': .6, 'text': 'A verified'}, {'start': .5, 'end': .8, 'text': 'synthetic opening.'}]):
            with self.assertRaises(ValueError): n.captions(rows, self.scenes[0]['text'], 1)

    def test_import_requires_hash_bound_bundle_and_review(self):
        self.bundle['scenes'][0]['reviewed_by'] = ''
        write_json(self.root/self.bundle_path, self.bundle)
        with self.assertRaisesRegex(ValueError, 'reviewer'): n.import_audio(self.path, self.bundle_path, self.root)
        self.assertFalse((self.root/'runs/narration').exists())

    def test_traversal_and_symlink_bindings_rejected(self):
        for path in ('../outside.wav', '/private/tmp/outside.wav'):
            with self.assertRaises(ValueError): n.verify({'path': path, 'sha256': 'a'*64}, self.root)
        (self.root/'research/event/escape.wav').symlink_to('/private/tmp/outside.wav')
        with self.assertRaises(ValueError): n.verify({'path': 'research/event/escape.wav', 'sha256': 'a'*64}, self.root)

    def test_truncated_wav_is_rejected(self):
        path = self.root/'research/event/source.wav'
        path.write_bytes(self.audio[:-200])
        with self.assertRaisesRegex(ValueError, 'Truncated'): n.pcm(path)

    def test_reused_selection_validates_receipts(self):
        self.imported(); first = n.process(self.path, self.effect_path, root=self.root)
        self.assertEqual(n.process(self.path, self.effect_path, root=self.root), first)
        receipt = self.root/first['effect_receipt']['path']
        receipt.write_text('{}')
        with self.assertRaises(ValueError): n.process(self.path, self.effect_path, root=self.root)

    def test_preflight_never_reads_credential_or_network(self):
        self.hosted()
        with patch('f1_pipeline.credentials.resolve_api_key', side_effect=AssertionError('secret read')):
            result = provider.execute(self.path, root=self.root)
        self.assertFalse(result['provider_calls']); self.assertEqual(result['calls'], 2)
        self.assertFalse((self.root/'runs/narration').exists())

    def test_hosted_execution_serialization_cache_and_model_attribution(self):
        auth = self.hosted(); transport = Transport(self.audio)
        result = provider.execute(self.path, authorization_path=auth, execute=True, api_key='synthetic-secret', opener=transport, root=self.root)
        self.assertEqual(len(transport.calls), 2)
        body = json.loads(transport.calls[0].data)
        self.assertEqual(body['model_id'], 'eleven_multilingual_v2'); self.assertEqual(body['seed'], 0)
        self.assertEqual(transport.calls[0].get_header('Xi-api-key'), 'synthetic-secret')
        self.assertIn('/with-timestamps?', transport.calls[0].full_url)
        self.assertEqual(len(result['model_runs']), 1)
        self.assertTrue(n.prepare(self.path, self.root)['cache_hit'])
        provider.execute(self.path, execute=True, root=self.root)
        self.assertEqual(len(transport.calls), 2)
        # A new job can reuse exact scene bytes without another credential read/call.
        self.value['job_id'] = 'reuse'; self.save()
        self.assertEqual(n.prepare(self.path, self.root)['calls'], 0)
        reused = provider.execute(self.path, execute=True, root=self.root)
        self.assertEqual(reused['scenes'][0]['clean'], result['scenes'][0]['clean'])

    def test_hosted_execution_requires_bound_authorization_before_secret_access(self):
        auth = self.hosted()
        bad = n.load(auth, self.root); bad['request_sha256'] = 'a'*64; write_json(self.root/auth, bad)
        with patch('f1_pipeline.credentials.resolve_api_key', side_effect=AssertionError('secret read')):
            with self.assertRaisesRegex(ValueError, 'authorization'):
                provider.execute(self.path, authorization_path=auth, execute=True, root=self.root)
        self.assertFalse((self.root/'runs/narration').exists())

    def test_interrupted_provider_cannot_repeat_job_and_secrets_are_redacted(self):
        auth = self.hosted()
        class Failed:
            def open(self, *args, **kwargs): raise OSError('synthetic-secret upstream body')
        with self.assertRaisesRegex(ValueError, 'retained receipts'):
            provider.execute(self.path, authorization_path=auth, execute=True, api_key='synthetic-secret', opener=Failed(), root=self.root)
        self.assertFalse((self.root/n.result_path(self.value)).exists())
        self.assertNotIn('synthetic-secret', (self.root/'runs/narration/fixture/failure.json').read_text())
        work = n.load('runs/model-evaluations/narration/fixture.json', self.root)
        self.assertEqual(work['attempts'][0]['status'], 'failed')
        self.assertIsNone(work['attempts'][0]['usage']['cost_usd'])
        with self.assertRaisesRegex(ValueError, 'exists'):
            provider.execute(self.path, authorization_path=auth, execute=True, api_key='synthetic-secret', opener=Failed(), root=self.root)

    def test_redirect_missing_alignment_and_response_bound_fail_closed(self):
        auth = self.hosted()
        class Redirect(Transport):
            def open(self, req, timeout):
                return Response({}, 'https://other.example/audio')
        with self.assertRaises(ValueError): provider.execute(self.path, authorization_path=auth, execute=True, api_key='fixture', opener=Redirect(self.audio), root=self.root)
        self.assertFalse((self.root/n.result_path(self.value)).exists())
        with self.assertRaises(ValueError): provider.alignment_captions(None, 'Hello', 1)
        with self.assertRaises(ValueError): provider.alignment_captions({'characters': ['X']}, 'Hello', 1)

    def test_v3_rejects_unsupported_speed_and_invalid_delivery(self):
        self.hosted(); p = self.value['provider']; p['model'] = 'eleven_v3'
        with self.assertRaises(ValueError): provider.validate_settings(p)
        p['settings']['voice_settings'] = {'stability': .5}; provider.validate_settings(p)
        p['settings']['voice_settings']['stability'] = .3
        with self.assertRaises(ValueError): provider.validate_settings(p)

    def test_credit_ceiling_and_request_edits_fail_before_provider_access(self):
        auth = self.hosted()
        bad = n.load(auth, self.root); bad['max_credits'] = .001; write_json(self.root/auth, bad)
        with patch('f1_pipeline.credentials.resolve_api_key', side_effect=AssertionError('secret read')):
            with self.assertRaises(ValueError): provider.execute(self.path, authorization_path=auth, execute=True, root=self.root)
        original = deepcopy(self.value)
        self.value['job_id'] = 'changed'; self.save()
        with self.assertRaisesRegex(ValueError, 'changed'): n.assert_current(self.path, original, self.root)

    def test_cache_tampering_and_duplicate_work_identity_fail_before_generation(self):
        auth = self.hosted(); transport = Transport(self.audio)
        result = provider.execute(self.path, authorization_path=auth, execute=True, api_key='fixture', opener=transport, root=self.root)
        self.value['job_id'] = 'reuse'; self.save()
        (self.root/result['scenes'][0]['clean']['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError): n.prepare(self.path, self.root)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'native audio tools unavailable')
    def test_cli_helper_import_and_selection_from_another_directory(self):
        import os
        import sys
        env = {k: v for k, v in os.environ.items() if k not in {'F1_WORKSPACE', 'ELEVENLABS_API_KEY', 'OPENROUTER_API_KEY'}}
        env.update(PYTHONPATH=str(Path(n.__file__).resolve().parents[1]), F1_DISABLE_KEYCHAIN='1')
        helper = subprocess.run([sys.executable, str(PACKAGE_ROOT/'scripts/prepare_narration_request.py'),
                    '--workspace', str(self.root), '--job-id', 'cli', '--format', 'vertical',
                    '--output', 'research/event/cli-request.json'], cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(helper.returncode, 0, helper.stderr)
        request_path = 'research/event/cli-request.json'
        self.bundle['request_sha256'] = json.loads(helper.stdout)['request_sha256']
        write_json(self.root/self.bundle_path, self.bundle)
        def invoke(command, *args):
            result = subprocess.run([sys.executable, '-m', 'f1_pipeline', '--workspace', str(self.root), command,
                         '--request', request_path, *args], cwd=self.root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertFalse(invoke('speech-prepare')['provider_calls'])
        invoke('speech-import', '--bundle', self.bundle_path)
        selected = invoke('speech-process', '--effect', self.effect_path)
        self.assertEqual(selected['provider']['kind'], 'imported')
        self.assertTrue(invoke('speech-prepare')['cache_hit'])

    def test_multiple_formats_and_effect_receipt_bindings(self):
        self.imported(); vertical = n.process(self.path, self.effect_path, root=self.root)
        self.value['job_id'] = 'landscape'; self.value['format'] = 'landscape'; self.save(); self.imported()
        n.process(self.path, self.effect_path, root=self.root)
        self.assertEqual(set(n.selections(self.root)), {'vertical', 'landscape'})
        registry = n.load(n.SELECTION, self.root)
        registry['formats']['vertical']['scenes'][0]['captions'][0]['start'] = 0
        write_json(self.root/n.SELECTION, registry)
        with self.assertRaises(ValueError): n.selected_narration('vertical', self.root)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'native audio/video tools unavailable')
    def test_native_render_consumes_saved_audio_without_speech_generation(self):
        from contextlib import ExitStack
        from PIL import Image
        from f1_pipeline import core, render
        self.imported(); selected = n.process(self.path, self.effect_path, root=self.root)
        write_json(self.root/'research/media/clip_review.json', {'reviews': []})
        scenes = [{'id': s['id'], 'title': s['id'], 'kicker': 'synthetic', 'narration': s['text'],
                   'event_ids': ['E1'], 'source_in': 0, 'metrics': []} for s in self.scenes]
        def execute(cmd, **kwargs):
            self.assertNotEqual(cmd[0], 'say')
            return core.run(cmd, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(patch.object(core, 'ROOT', self.root))
            stack.enter_context(patch.object(render, 'ROOT', self.root))
            stack.enter_context(patch.object(render, 'run', side_effect=execute))
            stack.enter_context(patch.object(render, 'overlay_image', return_value=Image.new('RGBA', (720, 1280))))
            stack.enter_context(patch('f1_pipeline.credentials.resolve_api_key', side_effect=AssertionError('secret read')))
            record, edl = render.render_one('vertical', {'scenes': scenes, 'title': 'Synthetic narration', 'idea_id': 'fixture'},
                    {'timeline': [{'id': 'E1', 'source_ids': ['synthetic-source']}]}, {'sources': [], 'assets': []},
                    self.root/'outputs/versions/native')
        self.assertAlmostEqual(record['duration'], 2, delta=.12)
        self.assertIn('Imported', record['narration'])
        self.assertEqual(edl[0]['narration_audio'], selected['scenes'][0]['audio'])
        srt = (self.root/record['captions']).read_text()
        self.assertEqual(srt.count('-->'), 2)
        self.assertIn('00:00:00,100 --> 00:00:00,800', srt)
        self.assertIn('00:00:01,100 --> 00:00:01,800', srt)
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'native audio tools unavailable')
    def test_real_audio_import_decode_roundtrip(self):
        self.decode.stop()
        result = self.imported()
        self.assertEqual(n.pcm(self.root/result['scenes'][0]['clean']['path']), n.pcm(self.root/'research/event/source.wav'))

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_vocoder_external_contract_one_final_tail_and_source_reuse(self):
        self.imported()
        # A bounded synthetic processor tests the external invocation contract, not voice quality.
        module = self.root/'fake-dsp.cjs'
        module.write_text('''module.exports={
decodeWav(b){const d=new DataView(b.buffer,b.byteOffset,b.byteLength);return {sampleRate:d.getUint32(24,true),samples:Float32Array.from({length:d.getUint32(40,true)/2},(_,i)=>d.getInt16(44+i*2,true)/32768)}},
normalize(a){return a},resample(a,f,t){return Float32Array.from({length:Math.round(a.length*t/f)},(_,i)=>a[Math.min(a.length-1,Math.floor(i*f/t))])},
vocode(a,r,o){const b=new Float32Array(a.length+(o.echo>0?Math.ceil(r*.6):0));b.set(a);return b},
encodeWav(a,r){const b=Buffer.alloc(44+a.length*2);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(r,24);b.writeUInt32LE(r*2,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(a.length*2,40);for(let i=0;i<a.length;i++)b.writeInt16LE(Math.round(a[i]*32767),44+i*2);return b}
};''')
        recipe = {'schema_version': 'f1.narration_effect.v1', 'kind': 'robot_vocoder', 'processor_sha256': n.digest(module),
                  'options': {'mode': 'single', 'note': 43, 'brightness': .6, 'clarity': .48, 'wet': .5,
                              'tempo': 100, 'echo': .1, 'progression': 'minor', 'progressionBeats': 1}}
        write_json(self.root/self.effect_path, recipe)
        with patch('f1_pipeline.credentials.resolve_api_key', side_effect=AssertionError('secret read')):
            selected = n.process(self.path, self.effect_path, processor=module, root=self.root)
        self.assertEqual([s['duration'] for s in selected['scenes']], [1, 1+15/24])
        self.assertEqual([s['tail_seconds'] for s in selected['scenes']], [0, 15/24])
        self.assertEqual(selected['scenes'][1]['captions'][-1]['end'], .8)
        self.assertEqual(n.digest(self.root/'research/event/source.wav'), self.bundle['scenes'][0]['audio']['sha256'])
        recipe['options']['echo'] = 0; write_json(self.root/self.effect_path, recipe)
        next_selection = n.process(self.path, self.effect_path, processor=module, root=self.root)
        self.assertNotEqual(next_selection['effect_receipt'], selected['effect_receipt'])
        self.assertEqual(next_selection['source_result'], selected['source_result'])
        self.assertEqual(next_selection['scenes'][1]['duration'], 1)


if __name__ == '__main__': unittest.main()
