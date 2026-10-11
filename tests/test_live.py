import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from f1_pipeline.live import (bind, connect, current_records, evidence, ingest,
                              load_config, parse_history, plain, run_live, validate_brief)


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.c = {'event_id': 'synthetic-race', 'name': 'Synthetic Race', 'event_date': '2026-10-11',
                  'session_name': 'Race', 'source_page': 'https://www.formula1.com/en/latest/article/synthetic',
                  'source_event_id': 'ca06b2a8-6d7f-4f6e-a8fb-7d7c6d00e607',
                  'history_url': 'https://cdn.monterosa.cloud/events/ca/ca06b2a8-6d7f-4f6e-a8fb-7d7c6d00e607/history.json',
                  'stop_at': '2099-01-01T00:00:00Z', 'reserve_bytes': 1}
        (self.root / 'config').mkdir()
        (self.root / 'config/live.json').write_text(json.dumps(self.c))
        self.c = load_config(self.root)
        self.db = connect(self.root)
        self.addCleanup(lambda: self.db.close())
        bind(self.db, self.c)

    def row(self, id='one', text='<p>Lap 1</p>', **fields):
        return {'id': id, 'content_type': 'article-element',
                'published_at_iso': '2026-10-11T12:01:00Z',
                'custom_fields': {'all': {'title': 'Race start', 'text': text,
                                          'accessLevel': 'public', **fields}}}

    def data(self, *rows):
        return json.dumps({'timeline': list(rows)}).encode()

    def test_backfill_restart_corrections_and_retractions(self):
        data = self.data(self.row(), self.row('late'))
        first = ingest(self.db, self.root, self.c, data)
        self.assertEqual(first['new_revisions'], 2)
        self.assertEqual(ingest(self.db, self.root, self.c, data)['new_revisions'], 0)
        self.db.close()
        self.db = connect(self.root)
        bind(self.db, self.c)
        changed = ingest(self.db, self.root, self.c, self.data(self.row(text='Corrected lap'), self.row('missed')))
        self.assertEqual(changed['new_revisions'], 2)
        self.assertEqual({r['id'] for r in current_records(self.db)}, {'one', 'missed'})
        self.assertEqual(self.db.execute('SELECT count(*) FROM revisions').fetchone()[0], 4)
        self.assertEqual(len(list((self.root / 'runs/live/snapshots').glob('*.json'))), 2)

    def test_malformed_snapshot_never_erases_previous_feed(self):
        ingest(self.db, self.root, self.c, self.data(self.row()))
        for bad in (b'{}', b'{', self.data(), self.data(self.row(), self.row())):
            with self.assertRaises(ValueError):
                ingest(self.db, self.root, self.c, bad)
            self.assertEqual(len(current_records(self.db)), 1)

    def test_restricted_records_and_active_html_excluded(self):
        rows = parse_history(self.data(self.row(text='<script>steal()</script><p>Hello &amp; welcome</p>'),
                                       self.row('restricted', accessLevel='subscriber')), self.c)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['text'], 'Hello & welcome')
        self.assertEqual(plain('<img src=x onerror=steal()>Fine'), 'Fine')

    def test_identity_mismatch_refused(self):
        with self.assertRaises(ValueError):
            bind(self.db, {**self.c, 'event_id': 'another'})
        row = self.row()
        row['published_at_iso'] = '2025-10-11T12:01:00Z'
        with self.assertRaises(ValueError):
            parse_history(self.data(row), self.c)

    def test_fetch_failure_retains_data_and_visible_staleness(self):
        ingest(self.db, self.root, self.c, self.data(self.row()))
        with patch('f1_pipeline.live.download', side_effect=TimeoutError):
            run_live(self.root, once=True, no_model=True)
        feed = json.loads((self.root / 'outputs/live/feed.json').read_text())
        self.assertEqual(len(feed['records']), 1)
        self.assertEqual(feed['error'], 'TimeoutError')
        self.assertIsNone(feed['model'])

    def test_model_citations_fail_closed(self):
        ingest(self.db, self.root, self.c, self.data(self.row()))
        bundle = evidence(self.db, self.c)
        brief = {'headline': 'Race starts', 'summary': 'Race starts.', 'race_status': 'Reported underway',
                 'moments': [{'title': 'Start', 'explanation': 'Lap 1', 'source_ids': ['one']}], 'uncertainties': []}
        validate_brief(brief, bundle)
        brief['moments'][0]['source_ids'] = ['invented']
        with self.assertRaises(ValueError):
            validate_brief(brief, bundle)

    def test_duplicate_writer_refused(self):
        import fcntl
        lock_path = self.root / 'runs/live/writer.lock'
        with lock_path.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, 'already owns'):
                run_live(self.root, once=True, no_model=True)

    def test_api_auth_refused_without_inference(self):
        from f1_pipeline.live import model_brief
        import subprocess
        result = subprocess.CompletedProcess([], 0, 'Logged in using an API key', '')
        with patch('f1_pipeline.live.shutil.which', return_value='/bin/codex'), patch('f1_pipeline.live.subprocess.run', return_value=result) as runner:
            with self.assertRaisesRegex(RuntimeError, 'subscription login required'):
                model_brief(self.root, evidence(self.db, self.c))
            self.assertEqual(runner.call_count, 1)

    def test_collection_continues_while_model_is_pending(self):
        from threading import Event
        started, release = Event(), Event()
        calls = []

        def slow_model(root, bundle):
            started.set()
            if not release.wait(2):
                raise RuntimeError('test release missing')
            raise RuntimeError('synthetic model unavailable')

        def pause(seconds):
            calls.append(seconds)
            self.assertTrue(started.wait(1))
            feed = json.loads((self.root / 'outputs/live/feed.json').read_text())
            if len(calls) == 1:
                self.assertEqual(feed['model_status'], 'generating')
            else:
                self.assertEqual({r['id'] for r in feed['records']}, {'one', 'late'})
                release.set()
                raise KeyboardInterrupt

        with patch('f1_pipeline.live.download', side_effect=[self.data(self.row()), self.data(self.row(), self.row('late'))]), \
             patch('f1_pipeline.live.model_brief', side_effect=slow_model), \
             patch('f1_pipeline.live.time.sleep', side_effect=pause):
            result = run_live(self.root)
        self.assertEqual(result['collector_status'], 'stopped')
        self.assertEqual(len(calls), 2)

    def test_subscription_execution_strips_keys_and_retains_usage(self):
        from f1_pipeline.live import model_brief
        import os
        import subprocess
        brief = {'headline': 'Race starts', 'summary': 'Race starts.', 'race_status': 'Reported underway',
                 'moments': [{'title': 'Start', 'explanation': 'Lap 1', 'source_ids': ['one']}], 'uncertainties': []}
        ingest(self.db, self.root, self.c, self.data(self.row()))

        def execute(command, **kwargs):
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertNotIn('CODEX_API_KEY', kwargs['env'])
            if command[1] == 'login':
                return subprocess.CompletedProcess(command, 0, 'Logged in using ChatGPT', '')
            self.assertIn('forced_login_method="chatgpt"', command)
            self.assertIn('shell_tool', command)
            Path(command[command.index('-o') + 1]).write_text(json.dumps(brief))
            return subprocess.CompletedProcess(command, 0, json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 123}}), '')

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic', 'CODEX_API_KEY': 'synthetic'}), \
             patch('f1_pipeline.live.shutil.which', return_value='/bin/codex'), \
             patch('f1_pipeline.live.subprocess.run', side_effect=execute):
            result = model_brief(self.root, evidence(self.db, self.c))
        receipt = json.loads((self.root / result['receipt_path']).read_text())
        self.assertEqual(receipt['status'], 'complete')
        self.assertEqual(receipt['usage']['input_tokens'], 123)
        self.assertIsNone(receipt['actual_cost'])


if __name__ == '__main__':
    unittest.main()
