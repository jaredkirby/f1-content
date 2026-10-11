#!/usr/bin/env python3
"""Reject missing packaged resources and unexpected wheel payloads."""
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def main(path):
    with ZipFile(path) as wheel:
        names = set(wheel.namelist())
        required = {'f1_pipeline/cli.py', 'f1_pipeline/jev_adapter.py',
                    'f1_pipeline/narration.py', 'f1_pipeline/narration_cli.py', 'f1_pipeline/speech_provider.py',
                    'f1_pipeline/resources/robot_vocoder.cjs',
                    'f1_pipeline/quality_protocol.py', 'f1_pipeline/story_contract.py',
                    'f1_pipeline/quality_results.py',
                    'f1_pipeline/live.py', 'f1_pipeline/resources/live.html',
                    'f1_pipeline/resources/jev_questions.json',
                    'f1_pipeline/resources/timeline.css', 'f1_pipeline/resources/timeline.js',
                    'f1_pipeline/resources/mobile-review-site/app/review.tsx',
                    'f1_pipeline/resources/mobile-review-site/app/api/feedback/route.ts',
                    'f1_pipeline/resources/mobile-review-site/app/api/credential/route.ts',
                    'f1_pipeline/resources/mobile-review-site/app/api/operator/credential/route.ts'}
        missing = required - names
        if missing:
            raise ValueError('Wheel missing: ' + ', '.join(sorted(missing)))
        for name in names:
            p = Path(name)
            if not (name.startswith('f1_pipeline/') or '.dist-info' in p.parts[0]):
                raise ValueError('Unexpected wheel payload: ' + name)
            if '..' in p.parts or p.is_absolute() or p.suffix.lower() in {'.mp4', '.pdf', '.pem', '.key'}:
                raise ValueError('Unsafe wheel payload: ' + name)
        entrypoint = next(name for name in names if name.endswith('.dist-info/entry_points.txt'))
        text = wheel.read(entrypoint).decode()
        assert 'f1-content = f1_pipeline.cli:main' in text
        assert 'f1-jev = f1_pipeline.jev_adapter:main' in text
        print(f'Wheel checked: {len(names)} package/metadata files, all required resources present.')
        # Exercise the actual wheel payload outside the checkout. Tests may read
        # public synthetic fixture definitions, but CLI imports come only from it.
        with tempfile.TemporaryDirectory(prefix='f1-wheel-review-') as tmp:
            wheel.extractall(tmp)
            smoke = '''import sys, unittest
from pathlib import Path
sys.path[:0] = [sys.argv[1], sys.argv[2]]
import f1_pipeline
import test_review_destination as review
import test_live as live
import test_quality_cli as quality
import test_quality_results_cli as results
import test_narration as narration
assert Path(sys.argv[1]).resolve() in Path(f1_pipeline.__file__).resolve().parents
review.PACKAGE_ROOT = Path(sys.argv[1])
quality.PACKAGE_ROOT = Path(sys.argv[1])
results.PACKAGE_ROOT = Path(sys.argv[1])
suite = unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromTestCase(review.ReviewDestinationTests),
    unittest.defaultTestLoader.loadTestsFromTestCase(live.LiveTests),
    unittest.defaultTestLoader.loadTestsFromTestCase(quality.QualityProtocolCLITests),
    unittest.defaultTestLoader.loadTestsFromTestCase(results.QualityResultsCLITests),
    unittest.defaultTestLoader.loadTestsFromTestCase(narration.NarrationTests),
])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
'''
            tests = Path(__file__).resolve().parents[1]/'tests'
            subprocess.run([sys.executable, '-I', '-B', '-c', smoke, tmp, str(tests)],
                           cwd=tmp, check=True)


if __name__ == '__main__':
    main(sys.argv[1])
