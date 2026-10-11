#!/usr/bin/env python3
"""Create a reviewable narration request from an existing event video plan, offline."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from f1_pipeline import narration as n
from f1_pipeline.core import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--format', choices=('vertical', 'landscape'), required=True)
    parser.add_argument('--provider', choices=('imported', 'say', 'elevenlabs'), default='imported')
    parser.add_argument('--voice', help='Explicit ElevenLabs voice ID')
    parser.add_argument('--model', default='eleven_multilingual_v2')
    parser.add_argument('--settings', type=Path, help='Workspace-relative complete ElevenLabs settings JSON')
    parser.add_argument('--output', default='research/event/narration-request.json')
    args = parser.parse_args()
    try:
        root, _, identity = n.workspace(args.workspace)
        plan = n.load('research/event/video_plan.json', root)
        if args.provider == 'elevenlabs':
            if not args.voice or not args.settings:
                raise ValueError('ElevenLabs requires explicit --voice and --settings')
            provider = {'kind': args.provider, 'voice': args.voice, 'model': args.model,
                        'settings': n.load(args.settings, root)}
        elif args.provider == 'say':
            provider = {'kind': 'say', 'model': 'macos-say', 'voice': 'Samantha', 'settings': {'words_per_minute': 172}}
        else:
            provider = {'kind': 'imported', 'model': None, 'voice': None, 'settings': {}}
        value = {'schema_version': 'f1.narration_request.v1', 'job_id': args.job_id, 'event_identity': identity,
                 'plan': n.binding('research/event/video_plan.json', root), 'format': args.format, 'provider': provider,
                 'scenes': [{'id': s['id'], 'text': s['narration']} for s in plan['formats'][args.format]['scenes']],
                 'limits': {'max_characters': 20000, 'max_calls': 50, 'timeout_seconds': 120,
                            'max_response_bytes': 32*1024**2, 'max_audio_seconds': 180}}
        target = n.safe_relative(args.output, root=root)
        if target.exists(): raise ValueError('Request destination exists; preserve it and choose another --output')
        write_json(target, value)
        # Validate before handing off a request; retain invalid preparation for correction.
        preview = n.prepare(target, root)
        print(n.canonical(preview).decode())
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__': raise SystemExit(main())
