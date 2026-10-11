"""Credential CLI and native-process boundary; never inspect the user's key."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class CredentialsTests(unittest.TestCase):
    def test_elevenlabs_credentials_never_read_openrouter_item(self):
        from unittest.mock import patch
        from f1_pipeline.credentials import resolve_api_key, native
        result = subprocess.CompletedProcess([], 0, stdout=b'synthetic-eleven-key', stderr=b'')
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'wrong-provider'}, clear=True), patch('sys.platform', 'darwin'), patch('subprocess.run', return_value=result) as run:
            self.assertEqual(resolve_api_key('elevenlabs'), 'synthetic-eleven-key')
            self.assertEqual(run.call_args.args[0][-2:], ['--provider', 'elevenlabs'])
            self.assertNotIn('wrong-provider', run.call_args.args[0])
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'synthetic-env-key'}, clear=True), patch('subprocess.run') as run:
            self.assertEqual(resolve_api_key('elevenlabs'), 'synthetic-env-key'); run.assert_not_called()

    def test_cli_stores_over_stdin_and_reports_only_metadata(self):
        script = '''
import json, subprocess, sys
from unittest.mock import patch
class Result:
    returncode=0
    stdout=b'{"status":"stored"}'
    stderr=b''
def native(command, **kwargs):
    assert command[-1]=='store'
    assert kwargs['input']==b'synthetic-key'
    assert all('synthetic-key' not in value for value in command)
    return Result()
with patch('subprocess.run', side_effect=native):
    from f1_pipeline.credentials import main
    raise SystemExit(main(['store']))
'''
        result=subprocess.run([sys.executable,'-c',script],input='synthetic-key',text=True,capture_output=True,cwd=PROJECT)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'stored')
        self.assertNotIn('synthetic-key',result.stdout+result.stderr)

    def test_saved_key_is_used_by_both_routes_only_during_execution(self):
        from unittest.mock import patch
        from f1_pipeline import hosted_inference, jev_inference
        import test_hosted_inference as text_fixture
        import test_openrouter_jev as jev_fixture
        key=b'synthetic-keychain-value'
        result=subprocess.CompletedProcess([],0,stdout=key,stderr=b'')
        with patch.dict(os.environ,{},clear=True), patch('sys.platform','darwin'), patch('subprocess.run',return_value=result) as native:
            hosted_inference.preflight(text_fixture.request_payload())
            jev_inference.preflight(jev_fixture.REQUEST)
            native.assert_not_called()
            text_http=text_fixture.SyntheticOpener(text_fixture.SyntheticResponse(json.dumps(text_fixture.provider_response()).encode()))
            jev_http=jev_fixture.Provider(jev_fixture.RESPONSE)
            a=hosted_inference.evaluate(text_fixture.request_payload(),execute=True,budget_usd=1,opener=text_http)
            b=jev_inference.evaluate(jev_fixture.REQUEST,execute=True,budget_usd=1,opener=jev_http)
            self.assertTrue(a['accepted_model_result'])
            self.assertTrue(b['accepted_model_result'])
            self.assertEqual(text_http.requests[0][0].headers['Authorization'],'Bearer '+key.decode())
            self.assertEqual(jev_http.requests[0].headers['Authorization'],'Bearer '+key.decode())
            self.assertNotIn(key.decode(),json.dumps([a,b]))

    def test_locked_keychain_fails_without_provider_call_or_secret_diagnostics(self):
        from unittest.mock import patch
        from f1_pipeline import hosted_inference
        import test_hosted_inference as fixture
        result=subprocess.CompletedProcess([],2,stdout=b'',stderr=b'synthetic-secret-must-not-leak')
        with patch.dict(os.environ,{},clear=True), patch('sys.platform','darwin'), patch('subprocess.run',return_value=result):
            receipt=hosted_inference.evaluate(fixture.request_payload(),execute=True,budget_usd=1,opener=fixture.OfflineOpener())
            self.assertFalse(receipt['inference_attempted'])
            self.assertNotIn('synthetic-secret',json.dumps(receipt))

    @unittest.skipUnless(os.environ.get('F1_KEYCHAIN_INTEGRATION')=='1' and sys.platform=='darwin',
                         'Opt-in native Keychain test; ordinary tests never touch a real Keychain')
    def test_native_unique_synthetic_item_roundtrip_update_and_delete(self):
        import uuid
        helper=Path(sys.prefix)/'bin/f1-keychain'
        identity=str(uuid.uuid4())
        def run(action,secret=None):
            result=subprocess.run([str(helper),action,'--test-id',identity],input=secret,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            return result.stdout
        try:
            self.assertEqual(json.loads(run('status'))['status'],'missing')
            self.assertEqual(json.loads(run('store',b'synthetic-first'))['status'],'stored')
            self.assertEqual(run('read'),b'synthetic-first')
            self.assertEqual(json.loads(run('store',b'synthetic-second'))['status'],'stored')
            self.assertEqual(run('read'),b'synthetic-second')
            self.assertEqual(json.loads(run('delete'))['status'],'deleted')
            self.assertEqual(json.loads(run('status'))['status'],'missing')
        finally:
            subprocess.run([str(helper),'delete','--test-id',identity],capture_output=True,timeout=15)
