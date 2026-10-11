"""Repository portability and publication-boundary regressions; no real archives."""
import importlib.util
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from f1_pipeline import jev_adapter

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('repo_guard', PROJECT/'scripts/repo_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class RepositoryTests(unittest.TestCase):
    def test_packaged_rubrics_and_timeline_resources(self):
        res = files('f1_pipeline').joinpath('resources')
        payload = {'model': jev_adapter.MODEL, 'state': 'Synthetic input',
                   'questions': json.loads(res.joinpath('jev_questions.json').read_text())}
        jev_adapter.validate_request(payload)
        for name in ('timeline.css', 'timeline.js'):
            self.assertGreater(len(res.joinpath(name).read_text()), 100)

    def invoke(self, *args, cwd=PROJECT):
        env = {k: v for k, v in os.environ.items() if k != 'F1_WORKSPACE'}
        env['PYTHONPATH'] = str(PROJECT)
        return subprocess.run([sys.executable, '-B', '-m', 'f1_pipeline', *args],
                              cwd=cwd, env=env, text=True, capture_output=True)

    def test_cli_selects_workspace_before_import_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.invoke('--workspace', str(PROJECT/'examples/synthetic'), 'doctor', cwd=tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['config']['id'], 'synthetic-session')

    def test_cli_missing_config_explains_recovery_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.invoke('doctor', cwd=tmp)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--workspace', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_source_guard_rejects_runtime_binary_and_submodule(self):
        for path, mode, value in [('events/example.json', '100644', b'{}'),
                                  ('docs/clip.mp4', '100644', b'video'),
                                  ('docs/site', '160000', b''),
                                  ('docs/link', '120000', b'../../secret'),
                                  ('docs/.env', '100644', b''),
                                  ('docs/binary', '100644', b'\0')]:
            with self.subTest(path=path):
                self.assertTrue(guard.inspect_blob(path, mode, value))

    def test_source_guard_reports_locations_without_secret_values(self):
        secret = 'ghp_' + 'a' * 40
        signed = 'https://example.invalid/video?' + 'Signature=' + 'b' * 40
        for value in (secret, signed):
            issues = guard.inspect_blob('docs/example.md', '100644', value.encode())
            self.assertTrue(issues)
            self.assertNotIn(value, str(issues))

    def test_source_guard_checks_index_even_if_working_file_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init', '-q')
            path = Path(tmp)/'README.md'
            path.write_text('ghp_' + 'a'*40)
            git('add', 'README.md')
            path.write_text('Clean working copy cannot hide staged credentials.\n')
            result = subprocess.run([sys.executable, str(PROJECT/'scripts/repo_guard.py')],
                                    cwd=tmp, text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('provider token', result.stderr)
            self.assertNotIn('a'*40, result.stderr)

    def test_source_guard_allows_only_approved_documentation_homepages(self):
        for path, addresses in guard.APPROVED_SITE_LINKS.items():
            for address in addresses:
                with self.subTest(path=path, address=address):
                    for suffix in ('', '/'):
                        blob = f'<a href="{address}{suffix}">Guide</a>'.encode()
                        self.assertEqual(guard.inspect_blob(path, '100644', blob), [])
                        self.assertTrue(guard.inspect_blob('docs/other.md', '100644', blob))
                    for suffix in ('/private-record', '?token=' + 'b'*40,
                                   '.attacker.invalid', ':443/private', '#private'):
                        blob = f'<a href="{address}{suffix}">Guide</a>'.encode()
                        issues = guard.inspect_blob(path, '100644', blob)
                        self.assertTrue(issues)
                        self.assertNotIn(address, str(issues))
                    blob = f'<a href="{address}">Guide</a> ghp_'.encode() + b'a'*40
                    self.assertTrue(guard.inspect_blob(path, '100644', blob))


if __name__ == '__main__':
    unittest.main()
