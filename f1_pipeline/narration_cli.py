"""CLI boundary for explicit narration work."""
COMMANDS = ('speech-prepare', 'speech-execute', 'speech-import', 'speech-process')


def options(parser):
    from pathlib import Path
    group = parser.add_argument_group('explicit narration commands')
    group.add_argument('--bundle', type=Path, help='Workspace-relative imported audio/timing bundle')
    group.add_argument('--effect', type=Path, help='Workspace-relative narration effect recipe')
    group.add_argument('--dsp-module', type=Path, help='Explicit absolute external Robot Voice Lab DSP module')
    group.add_argument('--authorization', type=Path, help='Workspace-relative human-authorized speech request and credit ceiling')


def run(args):
    from . import narration
    if args.request is None: raise ValueError('Speech commands require --request')
    if args.command == 'speech-prepare': return narration.prepare(args.request)
    if args.command == 'speech-execute':
        from .speech_provider import execute
        return execute(args.request, authorization_path=args.authorization, execute=args.execute)
    if args.command == 'speech-import':
        if args.bundle is None: raise ValueError('speech-import requires --bundle')
        return narration.import_audio(args.request, args.bundle)
    if args.command == 'speech-process':
        if args.effect is None: raise ValueError('speech-process requires --effect')
        return narration.process(args.request, args.effect, processor=args.dsp_module)
