import unittest
from f1_pipeline.analyze_session import reconcile_qualifying, within_review
from f1_pipeline.analyze import reconcile_results
from f1_pipeline.render import checked_scene

class SessionPipelineTests(unittest.TestCase):
    def test_qualifying_uses_each_phase_and_furthest_stage(self):
        official=[{'driver_number':30,'position':9,'q1_seconds':93.0,'q2_seconds':91.7,'q3_seconds':92.1}]
        api=[{'driver_number':30,'position':9,'duration':[93.0,91.7,92.1]}]
        self.assertEqual(reconcile_qualifying(official,api),[])
        api[0]['duration'][2]=91.7
        self.assertIn('Q3 time conflict',' '.join(reconcile_qualifying(official,api)))

    def test_qualifying_rejects_extra_and_duplicate_drivers(self):
        rows=[{'driver_number':3,'position':1,'duration':[91.0,90.0,89.0]}]
        official=[{'driver_number':3,'position':1,'q1_seconds':91.0,'q2_seconds':90.0,'q3_seconds':89.0}]
        self.assertTrue(reconcile_qualifying(official,rows+[{'driver_number':44,'position':2,'duration':[92.0,91.0,90.0]}]))
        with self.assertRaises(ValueError):reconcile_qualifying(official,rows+rows)

    def test_no_time_is_not_invented_as_slowest_lap(self):
        official=[{'driver_number':6,'position':22,'official_position':None,'classified':False,'q1_seconds':None,'q2_seconds':None,'q3_seconds':None}]
        self.assertEqual(reconcile_qualifying(official,[{'driver_number':6,'position':'RT','duration':[None,None,None]}]),[])

    def test_race_result_rejects_duplicate_record_overwrite(self):
        row={'driver_number':3}
        self.assertTrue(reconcile_results([row],[row,row]))

    def test_reviewed_interval_rejects_escape_and_nan(self):
        asset={'duration':90,'reviewed_ranges':[{'in':10,'out':20}]}
        self.assertTrue(within_review(asset,12,18))
        self.assertFalse(within_review(asset,12,21))
        self.assertFalse(within_review(asset,float('nan'),18))

    def test_render_cannot_extend_past_reviewed_scene(self):
        editorial={'timeline':[{'id':'Q01','media_matches':[{'source_id':'s1','in':10,'out':20}]}]}
        asset={'duration':90,'reviewed_ranges':[{'in':10,'out':20}]}
        scene={'id':'s','event_ids':['Q01'],'source_id':'s1','source_in':12,'source_out_limit':19,'narration':'Verified narration.'}
        self.assertEqual(checked_scene(scene,editorial,asset),19)
        scene['source_out_limit']=25
        with self.assertRaises(ValueError):checked_scene(scene,editorial,asset)

    def test_render_rejects_orphan_claims_even_for_graphics(self):
        with self.assertRaises(ValueError):checked_scene({'id':'bad','event_ids':['Q99'],'narration':'No evidence'}, {'timeline':[]},None)

if __name__=='__main__':unittest.main()
