"""Independent offline protocol regressions; synthetic data is never approval."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from f1_pipeline.quality_protocol import check_protocol, freeze_protocol, preview_protocol, run


def write(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding='utf-8')
    return {'path': path, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def fixture(root):
    identity = {'id': 'synthetic-session', 'year': 2026, 'country_name': 'Example',
                'session_name': 'Qualifying', 'event_date': '2026-10-10',
                'session_key': 999999, 'meeting_key': 999999}
    write(root, 'config/event.json', {**identity, 'reserve_bytes': 1})
    rubric = write(root, 'research/rubric.txt', 'Synthetic explicit rubric, no approval thresholds.')
    protocol = {'schema_version': 'f1.quality_protocol.v1', 'protocol_id': 'sample-1',
                'event_identity': identity, 'rubric': {**rubric, 'version': 'fixture-v1'},
                'split_assignment': {'kind': 'operator_declared', 'reference': 'Fictional fixture assignment'},
                'cases': [
                    {'case_id': 'case-development', 'split': 'development',
                     'source_group_ids': ['source-one'],
                     'evidence': [write(root, 'research/development.txt', 'Fictional development input')]},
                    {'case_id': 'case-held-out', 'split': 'held_out',
                     'source_group_ids': ['source-two'],
                     'evidence': [write(root, 'research/held-out.txt', 'Fictional held-out input')]},
                ]}
    write(root, 'protocol.json', protocol)
    return protocol


class QualityProtocol(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.protocol = fixture(self.root)

    def rewrite(self, document):
        write(self.root, 'protocol.json', document)

    def test_preview_is_offline_read_only_and_supplies_no_human_approval(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network')), \
             patch('socket.create_connection', side_effect=AssertionError('No network')), \
             patch('f1_pipeline.credentials.resolve_api_key', side_effect=AssertionError('No credentials')):
            result = preview_protocol('protocol.json', root=self.root)
        self.assertEqual(result['sample']['cases'], {'development': 1, 'held_out': 1})
        self.assertFalse(result['provider_calls'])
        self.assertFalse(result['writes_performed'])
        self.assertEqual(result['human_acceptance'], 'not_inferred')
        self.assertEqual(result['human_evidence_status'], 'not_assessed')
        self.assertFalse(result['model_promotion'])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                 for p in self.root.rglob('*') if p.is_file()})

    def test_same_source_and_multi_source_bridges_cannot_cross_splits(self):
        self.protocol['cases'][0]['source_group_ids'].append('source-two')
        self.rewrite(self.protocol)
        with self.assertRaisesRegex(ValueError, 'Source-group split leakage'):
            freeze_protocol('protocol.json', root=self.root)
        self.assertFalse((self.root / 'runs').exists())

    def test_reposted_identical_content_cannot_hide_under_different_groups(self):
        copied = write(self.root, 'research/repost.txt', 'Fictional development input')
        self.protocol['cases'][1]['evidence'] = [copied]
        self.rewrite(self.protocol)
        with self.assertRaisesRegex(ValueError, 'content split leakage'):
            preview_protocol('protocol.json', root=self.root)

    def test_evidence_path_reuse_cannot_cross_splits(self):
        self.protocol['cases'][1]['evidence'] = deepcopy(self.protocol['cases'][0]['evidence'])
        self.rewrite(self.protocol)
        with self.assertRaisesRegex(ValueError, 'split leakage'):
            preview_protocol('protocol.json', root=self.root)

    def test_freeze_is_exclusive_and_check_verifies_frozen_current_bytes(self):
        saved = freeze_protocol('protocol.json', root=self.root)
        original = (self.root / saved['receipt_path']).read_bytes()
        result = check_protocol(saved['receipt_path'], root=self.root)
        self.assertEqual(result['status'], 'current_frozen_protocol')
        self.assertEqual(result['sha256'], saved['sha256'])
        with self.assertRaisesRegex(ValueError, 'already frozen'):
            freeze_protocol('protocol.json', root=self.root)
        self.assertEqual(original, (self.root / saved['receipt_path']).read_bytes())
        self.assertEqual(len(list((self.root / 'runs/quality-protocols').iterdir())), 1)

    def test_related_cases_can_share_groups_and_evidence_within_one_split(self):
        another = deepcopy(self.protocol['cases'][0])
        another['case_id'] = 'neighboring-excerpt'
        another['source_group_ids'].append('neighbor-source')
        self.protocol['cases'].append(another)
        self.rewrite(self.protocol)
        result = preview_protocol('protocol.json', root=self.root)
        self.assertEqual(result['sample']['cases'], {'development': 2, 'held_out': 1})
        self.assertEqual(result['sample']['source_groups'], 3)

    def test_input_change_before_publish_leaves_no_frozen_receipt_or_tempfile(self):
        def change_input(_):
            write(self.root, 'research/held-out.txt', 'Changed during freezing')
        with patch('f1_pipeline.quality_protocol.os.fsync', side_effect=change_input):
            with self.assertRaisesRegex(ValueError, 'Stale or missing'):
                freeze_protocol('protocol.json', root=self.root)
        self.assertEqual(list((self.root / 'runs/quality-protocols').iterdir()), [])

    def test_symlink_receipt_directory_is_refused_before_writing(self):
        (self.root / 'alternate').mkdir()
        (self.root / 'runs').mkdir()
        (self.root / 'runs/quality-protocols').symlink_to(self.root / 'alternate', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'canonical paths'):
            freeze_protocol('protocol.json', root=self.root)
        self.assertEqual(list((self.root / 'alternate').iterdir()), [])

    def test_changed_protocol_config_rubric_or_case_evidence_is_stale(self):
        for changed in ('protocol.json', 'config/event.json', 'research/rubric.txt', 'research/held-out.txt'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                fixture(root)
                saved = freeze_protocol('protocol.json', root=root)
                with (root / changed).open('a') as handle:
                    handle.write('\n')
                with self.assertRaisesRegex(ValueError, 'Stale or missing'):
                    check_protocol(saved['receipt_path'], root=root)

    def test_corrupt_receipt_and_copied_receipt_refused(self):
        saved = freeze_protocol('protocol.json', root=self.root)
        receipt = json.loads((self.root / saved['receipt_path']).read_text())
        write(self.root, 'receipt-copy.json', receipt)
        with self.assertRaisesRegex(ValueError, 'canonical frozen receipt path'):
            check_protocol('receipt-copy.json', root=self.root)
        receipt['protocol']['rubric']['version'] = 'changed'
        write(self.root, saved['receipt_path'], receipt)
        with self.assertRaisesRegex(ValueError, 'Corrupt frozen receipt'):
            check_protocol(saved['receipt_path'], root=self.root)

    def test_labels_acceptances_or_reviewer_provenance_are_not_silently_imported(self):
        for field, value in (('label', 'approved'), ('human_acceptance', True),
                             ('source', {'kind': 'human', 'reviewer': 'invented'})):
            with self.subTest(field=field):
                protocol = deepcopy(self.protocol)
                protocol['cases'][0][field] = value
                self.rewrite(protocol)
                with self.assertRaisesRegex(ValueError, 'unsupported fields'):
                    preview_protocol('protocol.json', root=self.root)

    def test_malformed_identity_split_rubric_duplicates_and_paths(self):
        variants = []
        wrong_identity = deepcopy(self.protocol)
        wrong_identity['event_identity']['year'] = 2025
        variants.append(wrong_identity)
        missing_held_out = deepcopy(self.protocol)
        missing_held_out['cases'][1]['split'] = 'development'
        variants.append(missing_held_out)
        invalid_split = deepcopy(self.protocol)
        invalid_split['cases'][1]['split'] = 'random'
        variants.append(invalid_split)
        no_rubric = deepcopy(self.protocol)
        no_rubric['rubric']['version'] = ''
        variants.append(no_rubric)
        duplicated = deepcopy(self.protocol)
        duplicated['cases'][1]['case_id'] = duplicated['cases'][0]['case_id']
        variants.append(duplicated)
        escape = deepcopy(self.protocol)
        escape['rubric']['path'] = '../rubric.txt'
        variants.append(escape)
        for index, protocol in enumerate(variants):
            with self.subTest(index=index):
                self.rewrite(protocol)
                with self.assertRaises(ValueError):
                    preview_protocol('protocol.json', root=self.root)

    def test_duplicate_json_fields_and_nonfinite_values_refused(self):
        for text in ('{"schema_version":"x","schema_version":"y"}', '{"value":NaN}'):
            write(self.root, 'protocol.json', text)
            with self.assertRaises(ValueError):
                preview_protocol('protocol.json', root=self.root)

    def test_symlink_evidence_alias_and_outside_request_refused(self):
        (self.root / 'alias.txt').symlink_to(self.root / 'research/development.txt')
        self.protocol['cases'][0]['evidence'][0]['path'] = 'alias.txt'
        self.rewrite(self.protocol)
        with self.assertRaisesRegex(ValueError, 'symlink aliases'):
            preview_protocol('protocol.json', root=self.root)
        with self.assertRaisesRegex(ValueError, 'escapes event workspace'):
            preview_protocol(self.root.parent / 'outside.json', root=self.root)

    def test_no_inference_execute_flag_supported(self):
        with self.assertRaisesRegex(ValueError, 'cannot execute inference'):
            run(SimpleNamespace(command='quality-freeze', request=Path('protocol.json'), execute=True))


if __name__ == '__main__':
    unittest.main()
