#!/usr/bin/env python3
"""Run the explicitly selected feed with a loopback-only live report."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import signal
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from f1_pipeline.live import run_live


class ReportHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?')[0] not in ('/', '/index.html', '/feed.json'):
            self.send_error(404)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-model', action='store_true')
    args = parser.parse_args()
    root = args.workspace.resolve()
    if not root.is_dir():
        parser.error('Workspace must exist')
    report = root / 'outputs/live'
    report.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(ReportHandler, directory=str(report)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    signal.signal(signal.SIGTERM, lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    print(f'Live report: http://127.0.0.1:{args.port}', flush=True)
    try:
        run_live(root, no_model=args.no_model)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
