"""Execution receipts distinguish required artifacts, cache reuse and partial data."""
from contextlib import contextmanager
import unittest
from unittest.mock import Mock, patch

from f1_pipeline import core, harness
from test_release_gates import fixture_workspace, finalized_fixture, put


@contextmanager
def fixture():
    with fixture_workspace() as root, patch.object(harness,'ROOT',root), patch.object(harness,'log'):
        yield root


def receipt(root):
    return core.read_json(sorted((root/'runs/stages').glob('*.json'))[-1])


class HarnessGates(unittest.TestCase):
    def test_missing_required_input_blocks_operation_even_with_old_output(self):
        with fixture() as root:
            put(root,'data/processed/catalog.json',{'old':'artifact'})
            operation=Mock()
            with self.assertRaisesRegex(ValueError,'Required stage input'):
                harness.stage('catalog',operation)
            operation.assert_not_called()
            self.assertEqual(receipt(root)['status'],'failed')
            self.assertIn('data/processed/catalog.json',receipt(root)['output_hashes'])

    def test_partial_collection_remains_nonfatal_and_explicit(self):
        with fixture() as root:
            result={'status':'partial','failures':[{'endpoint':'pit','error':'optional unavailable'}]}
            def operation():
                put(root,'data/processed/data_manifest.json',result)
                return result
            self.assertEqual(harness.stage('collect',operation),result)
            record=receipt(root)
            self.assertEqual(record['status'],'partial')
            self.assertEqual(record['source_failures'],result['failures'])
            self.assertEqual(record['output_changes']['data/processed/data_manifest.json'],'created')
            harness.stage('collect',operation)
            self.assertEqual(receipt(root)['output_changes']['data/processed/data_manifest.json'],'unchanged')

    def test_missing_required_output_is_a_recorded_failure(self):
        with fixture() as root:
            with self.assertRaisesRegex(ValueError,'required output'):
                harness.stage('collect',lambda:{'status':'complete'})
            self.assertEqual(receipt(root)['status'],'failed')

    def test_sprint_mapping_and_script_fallback_are_explicit(self):
        with fixture() as root:
            cfg=core.read_json(root/'config/event.json');cfg.update(id='2026-singapore-sprint',session_name='Sprint')
            put(root,'config/event.json',cfg)
            for path in ('research/event/event_bundle.json','research/media/clip_review.json','data/processed/catalog.json','data/processed/data_manifest.json'):
                put(root,path,{'assets':[]})
            def operation():
                put(root,'data/processed/editorial.json',{'event':{'id':cfg['id']}})
                put(root,'data/processed/decisions.json',{})
                return {}
            harness.stage('analyze',operation)
            record=receipt(root)
            self.assertEqual(record['status'],'passed')
            self.assertIn('research/event/media_matches.json',record['missing_optional_inputs'])
            self.assertIn('f1_pipeline/analyze.py',record['input_hashes'])
            required,optional,_=harness.contracts('render',cfg)
            self.assertNotIn('research/event/video_plan.json',required)
            self.assertIn('research/event/video_plan.json',optional)
            self.assertIn('f1_pipeline/video_plan.py',required)
            self.assertTrue(harness.artifact_path('f1_pipeline/video_plan.py').is_file())

    def test_qualifying_mapping_is_required(self):
        with fixture() as root:
            required,optional,_=harness.contracts('analyze',core.config())
            self.assertIn('research/event/media_matches.json',required)
            self.assertNotIn('research/event/media_matches.json',optional)

    def test_validation_uses_manifest_edl_not_convenience_copy(self):
        with fixture() as root:
            path='outputs/versions/current/edit-plan.json'
            put(root,'outputs/manifest.json',{'edit_plan':path})
            put(root,'data/processed/catalog.json',{})
            put(root,'data/processed/editorial.json',{})
            put(root,path,{'edits':{}})
            def operation():
                result={'status':'passed','errors':[]}
                put(root,'outputs/qa.json',result)
                return result
            harness.stage('validate',operation)
            self.assertIn(path,receipt(root)['input_hashes'])
            self.assertNotIn('outputs/edit-plan.json',receipt(root)['input_hashes'])
            (root/path).unlink()
            put(root,'outputs/edit-plan.json',{'stale':'convenience copy'})
            blocked=Mock()
            with self.assertRaisesRegex(ValueError,'Required stage input'):
                harness.stage('validate',blocked)
            blocked.assert_not_called()

    def test_render_receipt_binds_versioned_edl_output(self):
        with fixture() as root:
            manifest,_=finalized_fixture(root)
            harness.stage('render',lambda:manifest)
            record=receipt(root)
            self.assertIn(manifest['edit_plan'],record['output_hashes'])
            self.assertNotIn('outputs/edit-plan.json',record['output_hashes'])
            self.assertEqual(record['output_changes'][manifest['edit_plan']],'unchanged')

    def test_escaped_edl_is_rejected_before_validation(self):
        with fixture() as root:
            put(root,'outputs/manifest.json',{'edit_plan':'../outside.json'})
            put(root,'data/processed/catalog.json',{})
            put(root,'data/processed/editorial.json',{})
            operation=Mock()
            with self.assertRaisesRegex(ValueError,'escapes'):
                harness.stage('validate',operation)
            operation.assert_not_called()
            self.assertEqual(receipt(root)['status'],'failed')


if __name__=='__main__':unittest.main()
