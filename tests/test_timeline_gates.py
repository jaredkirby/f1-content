"""Timeline review gates, isolated from live sites and source footage."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from f1_pipeline import core, timeline, validate
from test_release_gates import fixture_workspace, finalized_fixture, put


@contextmanager
def fixture():
    with fixture_workspace() as root, patch.object(timeline,'ROOT',root):
        cfg=core.read_json(root/'config/event.json');cfg['id']='2026-singapore-qualifying'
        put(root,'config/event.json',cfg)
        manifest,qa=finalized_fixture(root,cfg['id'])
        editorial=core.read_json(root/'data/processed/editorial.json')
        editorial.update(sources=[],data_assets=[],results=[])
        put(root,'data/processed/editorial.json',editorial)
        inputs={p:core.digest(root/p) for p in validate.required_render_inputs()}
        manifest['input_hashes']=inputs
        for video in manifest['videos']:
            video.update(status='finalized_local_review',input_hashes=dict(inputs))
        put(root,'outputs/manifest.json',manifest)
        qa['input_hashes']={**inputs,**{p:core.digest(root/p) for p in validate.QA_BASE_INPUTS}}
        put(root,'outputs/qa.json',qa)
        yield root,manifest,qa


class TimelineGates(unittest.TestCase):
    def test_valid_finalized_manifest_reaches_derivative_stage(self):
        with fixture(), patch.object(timeline,'viewing_copy',side_effect=RuntimeError('derivative reached')):
            with self.assertRaisesRegex(RuntimeError,'derivative reached'):timeline.build()

    def test_changed_render_input_and_missing_qa_block_before_derivatives(self):
        for change in ('script','qa'):
            with self.subTest(change=change), fixture() as (root,_,qa), patch.object(timeline,'viewing_copy') as render:
                if change=='script':put(root,'research/event/video_plan.json',{'revision':'not rendered'})
                else:
                    qa.pop('input_hashes');put(root,'outputs/qa.json',qa)
                with self.assertRaises(ValueError):timeline.build()
                render.assert_not_called()

    def test_missing_requested_edit_blocks_before_derivatives(self):
        with fixture() as (root,manifest,qa), patch.object(timeline,'viewing_copy') as render:
            manifest['videos'].pop();put(root,'outputs/manifest.json',manifest)
            qa['input_hashes']['outputs/manifest.json']=core.digest(root/'outputs/manifest.json')
            put(root,'outputs/qa.json',qa)
            with self.assertRaises(ValueError):timeline.build()
            render.assert_not_called()

    def test_actual_versioned_edl_must_match_recorded_hash(self):
        with fixture() as (root,manifest,_), patch.object(timeline,'viewing_copy',side_effect=RuntimeError('unsafe derivative reached')):
            put(root,manifest['edit_plan'],{'event_id':manifest['event_id'],'edits':{'changed':'after QA'}})
            with self.assertRaises(ValueError):timeline.build()

    def test_downloaded_caption_hash_and_clipped_relative_times(self):
        with fixture() as (root,_,_):
            path=root/'captions.vtt'
            path.write_text('WEBVTT\n\n00:00:05.000 --> 00:00:12.000\nPublisher words.\n\n00:00:15.000 --> 00:00:20.000\nOutside the clip.\n')
            source={'caption_tracks':[{'status':'failed','local_path':'missing.vtt'},
                {'status':'downloaded','local_path':'captions.vtt','sha256':core.digest(path)}]}
            target=root/'trimmed.vtt'
            self.assertTrue(timeline.trim_captions(source,7,10,target))
            self.assertIn('00:00:00.000 --> 00:00:03.000',target.read_text())
            self.assertNotIn('Outside the clip',target.read_text())
            path.write_text('changed captions')
            with self.assertRaises(ValueError):timeline.trim_captions(source,7,10,target)

    def test_corrupt_cached_poster_is_regenerated(self):
        with fixture() as (root,manifest,_):
            put(root,'outputs/manifest.json',{})
            original=root/'original.mp4';original.write_bytes(b'original source')
            sha=core.digest(original);review_sha=core.digest(root/'research/media/clip_review.json')
            put(root,'data/processed/catalog.json',{'event_id':manifest['event_id'],
                'sources':[{'id':'s1','asset_id':'a1','url':'https://example.invalid/source'}],
                'assets':[{'id':'a1','sha256':sha,'original':'original.mp4','duration':10,
                           'review_receipt_sha256':review_sha,'reviewed_ranges':[{'in':0,'out':10}]}]})
            put(root,'data/processed/editorial.json',{'event':{'id':manifest['event_id']},'sources':[],
                'timeline':[{'id':'Q01','media_matches':[{'source_id':'s1','asset_id':'a1','source_sha256':sha,
                             'review_receipt_sha256':review_sha,'in':0,'out':10}]}]})
            key=('s1',0,10);cid='clip-'+hashlib.sha256(repr(key).encode()).hexdigest()[:12]
            poster=root/'sites/timeline/dist/posters'/f'{cid}.jpg';poster.parent.mkdir(parents=True)
            poster.write_bytes(b'valid previous poster')
            put(root,str(poster.with_suffix('.receipt.json').relative_to(root)),
                {'clip_sha256':'unchanged-clip','sha256':core.digest(poster)})
            poster.write_bytes(b'corrupt interrupted write')
            with patch.object(timeline,'viewing_copy',return_value={'sha256':'unchanged-clip'}), \
                 patch.object(timeline,'run',side_effect=RuntimeError('poster regeneration')) as ffmpeg:
                with self.assertRaisesRegex(RuntimeError,'poster regeneration'):timeline.build()
                self.assertEqual(Path(ffmpeg.call_args.args[0][-1]),poster)


if __name__=='__main__':unittest.main()
