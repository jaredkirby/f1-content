#!/usr/bin/env python3
"""Reject missing packaged resources and unexpected wheel payloads."""
from pathlib import Path
import sys
from zipfile import ZipFile


def main(path):
    with ZipFile(path) as wheel:
        names = set(wheel.namelist())
        required = {'f1_pipeline/cli.py', 'f1_pipeline/jev_adapter.py',
                    'f1_pipeline/resources/jev_questions.json',
                    'f1_pipeline/resources/timeline.css', 'f1_pipeline/resources/timeline.js'}
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


if __name__ == '__main__':
    main(sys.argv[1])
