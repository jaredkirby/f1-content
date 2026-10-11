"""Public CLI protocol lifecycle from outside the source checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_quality_protocol import fixture

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class QualityProtocolCLITests(unittest.TestCase):
    def test_frozen_protocol_lifecycle_and_stale_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / 'event'
            workspace.mkdir()
            fixture(workspace)
            environment = {**os.environ, 'PYTHONPATH': str(PACKAGE_ROOT),
                           'F1_DISABLE_KEYCHAIN': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
            environment.pop('OPENROUTER_API_KEY', None)

            def invoke(command, request):
                return subprocess.run(
                    [sys.executable, '-B', '-m', 'f1_pipeline', '--workspace',
                     str(workspace), command, '--request', request],
                    cwd=root, env=environment, capture_output=True, text=True)

            preview = invoke('quality-preview', 'protocol.json')
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertFalse(json.loads(preview.stdout)['writes_performed'])
            self.assertFalse((workspace / 'runs').exists())
            frozen = invoke('quality-freeze', 'protocol.json')
            self.assertEqual(frozen.returncode, 0, frozen.stderr)
            receipt = json.loads(frozen.stdout)['receipt_path']
            original_bytes = (workspace / receipt).read_bytes()
            checked = invoke('quality-check', receipt)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout)['human_acceptance'], 'not_inferred')
            duplicate = invoke('quality-freeze', 'protocol.json')
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn('already frozen', duplicate.stderr)
            (workspace / 'research/held-out.txt').write_text('Changed fictional evidence')
            stale = invoke('quality-check', receipt)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn('Stale or missing evidence', stale.stderr)
            self.assertEqual((workspace / receipt).read_bytes(), original_bytes)
