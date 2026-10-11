import argparse
import json
import shutil
import os
from pathlib import Path

def main(argv=None):
    from .model_cli import COMMANDS, options
    from .quality_protocol import COMMANDS as QUALITY_COMMANDS
    from .narration_cli import COMMANDS as SPEECH_COMMANDS, options as speech_options
    parser = argparse.ArgumentParser(description="Evidence-first F1 session production pipeline (select workspace with F1_WORKSPACE or scripts/f1 --workspace)")
    parser.add_argument("--workspace", type=Path, help="Event directory (defaults to the working directory)")
    parser.add_argument("command", choices=["live", "doctor", "collect", "catalog", "analyze", "prepare-jev", "prepare-review-site", "review-site-status", "render", "validate", "finalize", "report", "timeline", "run", *COMMANDS, *QUALITY_COMMANDS, *SPEECH_COMMANDS])
    parser.add_argument("--refresh", action="store_true", help="Explicitly refresh source downloads")
    parser.add_argument("--format", choices=["vertical", "landscape", "both"], default="both")
    parser.add_argument("--site-directory", type=Path, help="Existing independent Site checkout for the mobile review destination")
    parser.add_argument("--once", action="store_true", help="One live collection cycle")
    parser.add_argument("--no-model", action="store_true", help="Collect live evidence without model calls")
    options(parser)
    speech_options(parser)
    args = parser.parse_args(argv)
    # Select before loading modules: each process owns exactly one workspace.
    selected = args.workspace or Path(os.environ.get("F1_WORKSPACE", Path.cwd()))
    if not selected.is_absolute() and args.workspace is None and "F1_WORKSPACE" in os.environ:
        parser.error("F1_WORKSPACE must be an absolute event-workspace path")
    selected = selected.expanduser().resolve()
    if not selected.is_dir():
        parser.error("Workspace directory does not exist: " + str(selected))
    os.environ["F1_WORKSPACE"] = str(selected)
    if args.command == "live":
        from .live import run_live
        try:
            run_live(selected, once=args.once, no_model=args.no_model)
            return 0
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
    from .core import ROOT, config, now
    from .harness import stage
    if ROOT != selected:
        parser.error("This process already loaded another workspace; start a fresh CLI process")
    try:
        event_config = config()
    except (ValueError, OSError) as exc:
        parser.error(str(exc) + "; provide --workspace with a reviewed config/event.json")
    if args.command == "review-site-status":
        from .review_destination import review_site_status
        result = review_site_status()
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['ready_for_human_review'] else 2
    if args.command == "prepare-review-site":
        from .review_destination import prepare_review_site
        if args.site_directory is None:
            parser.error("prepare-review-site requires --site-directory")
        try:
            print(json.dumps(prepare_review_site(args.site_directory), indent=2, allow_nan=False))
            return 0
        except (ValueError, OSError, KeyError, TypeError) as exc:
            parser.error(str(exc))
    if args.command in SPEECH_COMMANDS:
        from .narration_cli import run
        try:
            print(json.dumps(run(args), indent=2, allow_nan=False))
            return 0
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
            parser.error(str(exc))
    if args.command in QUALITY_COMMANDS:
        from .quality_protocol import run
        try:
            print(json.dumps(run(args), indent=2, allow_nan=False))
            return 0
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
    if args.command in COMMANDS:
        from .model_cli import run
        try:
            result = run(args)
            print(json.dumps(result, indent=2, allow_nan=False))
            provider = result.get('provider_result', result)
            return 2 if provider.get('status') == 'failed' else 0
        except (ValueError, OSError, RuntimeError) as exc:
            parser.error(str(exc))
    if args.command == "doctor":
        from .narration import selections
        narration = selections(ROOT)
        print(json.dumps({"at": now(), "root": str(ROOT), "free_bytes": shutil.disk_usage(ROOT).free,
                          "config": event_config, "narration": {name: {'provider': item['provider'], 'effect': item['effect']} for name, item in narration.items()} if narration else {'provider': 'macos-say', 'voice': 'Samantha'},
                          "tools": {t: shutil.which(t) for t in ("ffmpeg", "ffprobe", "say", "node")}}, indent=2))
    if args.command in ("collect", "run"):
        from .collect import collect_data
        stage('collect', lambda: collect_data(args.refresh))
    if args.command in ("catalog", "run"):
        from .catalog import catalog
        stage('catalog', lambda: catalog())
    if args.command in ("analyze", "run"):
        from .analyze import analyze
        stage('analyze', lambda: analyze())
    if args.command == "prepare-jev":
        from .jev import prepare
        print(json.dumps(stage('prepare-jev', prepare), indent=2))
    if args.command in ("render", "run"):
        from .render import render
        stage('render', lambda: render(args.format))
    if args.command in ("validate", "run"):
        from .validate import validate
        result = stage('validate', validate)
        print(json.dumps(result, indent=2))
        if result["errors"]:
            raise SystemExit(1)
    if args.command == "timeline":
        from .timeline import build
        stage("timeline", build)
    if args.command in ("report", "run"):
        from .report import report
        stage('report', lambda: report())
    if args.command == "finalize":
        from .finalize import finalize
        print(json.dumps(stage('finalize', finalize), indent=2))

if __name__ == "__main__":
    raise SystemExit(main())
