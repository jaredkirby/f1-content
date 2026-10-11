"""Public evaluation workflow from outside the checkout and actual wheel."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_quality_results import fixture

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class QualityResultsCLITests(unittest.TestCase):
    def test_bound_result_lifecycle_counts_and_stale_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / 'event'
            workspace.mkdir()
            fixture(workspace)
            environment = {**os.environ, 'PYTHONPATH': str(PACKAGE_ROOT),
                           'F1_DISABLE_KEYCHAIN': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
            environment.pop('OPENROUTER_API_KEY', None)

            def invoke(command, request, *extra):
                return subprocess.run(
                    [sys.executable, '-B', '-m', 'f1_pipeline', '--workspace',
                     str(workspace), command, '--request', request, *extra],
                    cwd=root, env=environment, capture_output=True, text=True)

            before = {p.relative_to(workspace): p.read_bytes()
                      for p in workspace.rglob('*') if p.is_file()}
            preview = invoke('quality-results-preview', 'evaluation.json')
            self.assertEqual(preview.returncode, 0, preview.stderr)
            value = json.loads(preview.stdout)
            by_split = {row['split']: row for row in value['groups']}
            self.assertEqual(by_split['development']['accuracy'], 1)
            self.assertEqual(by_split['held_out']['accuracy'], 0)
            self.assertEqual(by_split['held_out']['coverage'], 'partial')
            self.assertEqual(value['human_acceptance'], 'not_inferred')
            self.assertFalse(value['provider_calls'])
            self.assertEqual(before, {p.relative_to(workspace): p.read_bytes()
                                     for p in workspace.rglob('*') if p.is_file()})
            forbidden = invoke('quality-results-preview', 'evaluation.json', '--execute')
            self.assertNotEqual(forbidden.returncode, 0)
            self.assertIn('cannot execute inference', forbidden.stderr)
            saved = invoke('quality-results-save', 'evaluation.json')
            self.assertEqual(saved.returncode, 0, saved.stderr)
            receipt = json.loads(saved.stdout)['receipt_path']
            original = (workspace / receipt).read_bytes()
            report = invoke('quality-results-report', receipt)
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertEqual(json.loads(report.stdout)['status'], 'current_evaluation')
            duplicate = invoke('quality-results-save', 'evaluation.json')
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn('already saved', duplicate.stderr)
            (workspace / 'research/held.txt').write_text('Changed fictional evidence')
            stale = invoke('quality-results-report', receipt)
            self.assertNotEqual(stale.returncode, 0)
            self.assertNotIn('Traceback', stale.stderr)
            self.assertEqual((workspace / receipt).read_bytes(), original)
