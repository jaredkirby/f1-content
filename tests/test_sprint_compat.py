"""Sprint association migration uses reviewed bytes, never untouched run outputs."""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from f1_pipeline import core, analyze
from f1_pipeline.render import checked_scene


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='f1-sprint-match-') as tmp, ExitStack() as stack:
        root=Path(tmp).resolve()
        for module in (core,analyze):stack.enter_context(patch.object(module,'ROOT',root))
        stack.enter_context(patch.object(analyze,'MATCHES',{'E03':[('source-1',0,20)]}))
        original=root/'original.mp4';original.write_bytes(b'original acquisition fixture')
        sha=core.digest(original)
        review=root/'review.json';review.write_text('{"review":"current"}')
        review_sha=core.digest(review)
        source={'id':'source-1','asset_id':'a1','sha256':sha}
        asset={'id':'a1','original':'original.mp4','sha256':sha,'duration':30,
               'review_receipt_sha256':review_sha,'reviewed_ranges':[{'in':0,'out':10},{'in':10,'out':20}]}
        yield root, {'source-1':source}, {'a1':asset}, review_sha


class SprintCompatibilityTests(unittest.TestCase):
    def test_bound_intersections_can_be_used_by_strict_renderer(self):
        with fixture() as (_,sources,assets,sha):
            matches=analyze.sprint_media_matches('E03',sources,assets,sha)
            self.assertEqual([(m['in'],m['out']) for m in matches],[(0,10),(10,20)])
            self.assertTrue(all(m['source_sha256']==assets['a1']['sha256'] and m['review_receipt_sha256']==sha for m in matches))
            editorial={'timeline':[{'id':'E03','media_matches':matches}]}
            scene={'id':'start','source_id':'source-1','source_in':0,'source_out_limit':10,
                   'event_ids':['E03'],'narration':'The verified start.'}
            self.assertEqual(checked_scene(scene,editorial,assets['a1'],True,sha),10)

    def test_unreviewed_gaps_and_lead_in_are_excluded(self):
        with fixture() as (_,sources,assets,sha):
            assets['a1']['reviewed_ranges']=[{'in':.36,'out':7.76},{'in':7.84,'out':19.38}]
            matches=analyze.sprint_media_matches('E03',sources,assets,sha)
            self.assertEqual([(m['in'],m['out']) for m in matches],[(.36,7.76),(7.84,19.38)])
            self.assertTrue(all(m['requested_in']==0 and m['requested_out']==20 for m in matches))

    def test_stale_review_or_original_is_rejected(self):
        with fixture() as (root,sources,assets,sha):
            with self.assertRaises(ValueError):analyze.sprint_media_matches('E03',sources,assets,'new-review')
            (root/'original.mp4').write_bytes(b'replaced source content')
            with self.assertRaises(ValueError):analyze.sprint_media_matches('E03',sources,assets,sha)

    def test_missing_acquisition_hash_and_unreviewed_selection_rejected(self):
        with fixture() as (_,sources,assets,sha):
            sources['source-1'].pop('sha256')
            with self.assertRaises(ValueError):analyze.sprint_media_matches('E03',sources,assets,sha)
            sources['source-1']['sha256']=assets['a1']['sha256']
            assets['a1']['reviewed_ranges']=[{'in':21,'out':25}]
            with self.assertRaises(ValueError):analyze.sprint_media_matches('E03',sources,assets,sha)

    def test_undownloaded_reference_is_a_gap_and_repeated_asset_hashing_is_cached(self):
        with fixture() as (_,sources,assets,sha):
            self.assertEqual(analyze.sprint_media_matches('E03',{},assets,sha),[])
            verified=set()
            with patch.object(analyze,'digest',wraps=core.digest) as hashing:
                analyze.sprint_media_matches('E03',sources,assets,sha,verified)
                analyze.sprint_media_matches('E03',sources,assets,sha,verified)
                self.assertEqual(hashing.call_count,1)


if __name__=='__main__':unittest.main()
