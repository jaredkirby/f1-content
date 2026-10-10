"""Independent release gate regressions. Fixtures never touch event deliveries."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from f1_pipeline import core, analyze_session, render, finalize, validate


@contextmanager
def fixture_workspace():
    with tempfile.TemporaryDirectory(prefix="f1-release-gate-") as tmp, ExitStack() as stack:
        root = Path(tmp).resolve()
        for module in (core, analyze_session, render, finalize, validate):
            stack.enter_context(patch.object(module, "ROOT", root))
            if hasattr(module, "log"):
                stack.enter_context(patch.object(module, "log"))
        core.write_json(root / "config/event.json", {
            "id": "release-fixture", "year": 2026, "country_name": "Singapore",
            "session_name": "Qualifying", "event_date": "2026-10-10", "session_key": 11384,
            "meeting_key": 1296, "formats": ["vertical", "landscape"], "reserve_bytes": 1,
        })
        yield root


def put(root, path, value):
    core.write_json(root / path, value)


def finalized_fixture(root, event_id="release-fixture"):
    """Create valid content-addressed technical/visual/audio receipts without codecs."""
    put(root, "research/event/video_plan.json", {"revision": "original"})
    put(root, "research/event/event_bundle.json", {"event": {"id": event_id}})
    put(root, "research/media/clip_review.json", {"event_id": event_id, "reviews": []})
    put(root, "data/processed/catalog.json", {"event_id": event_id, "sources": [], "assets": []})
    put(root, "data/processed/editorial.json", {"event": {"id": event_id}, "timeline": [], "ideas": []})
    put(root, "outputs/versions/fixture/edit-plan.json", {"event_id": event_id, "edits": {}})
    inputs = {p: core.digest(root / p) for p in validate.required_render_inputs()}
    videos = []
    for name in ("vertical", "landscape"):
        paths = {"path": f"outputs/versions/fixture/{name}.mp4",
                 "captions": f"outputs/versions/fixture/{name}.srt",
                 "script": f"outputs/versions/fixture/{name}.txt",
                 "thumbnail": f"outputs/versions/fixture/{name}.jpg"}
        for key, relative in paths.items():
            (root / relative).write_bytes((name + ":" + key).encode())
        videos.append({"format": name, **paths, "sha256": core.digest(root / paths["path"]),
                       "companion_sha256": {key: core.digest(root / paths[key]) for key in ("captions", "script", "thumbnail")},
                       "input_hashes": inputs})
    manifest = {"event_id": event_id, "run_id": "fixture", "videos": videos, "input_hashes": inputs,
                "edit_plan": "outputs/versions/fixture/edit-plan.json",
                "edit_plan_sha256": core.digest(root / "outputs/versions/fixture/edit-plan.json")}
    put(root, "outputs/manifest.json", manifest)
    qa = {"event_id": event_id, "status": "passed", "errors": [],
          "edit_plan_sha256": manifest["edit_plan_sha256"],
          "videos": [{"format": v["format"], "sha256": v["sha256"]} for v in videos],
          "input_hashes": {**inputs, **{p: core.digest(root / p) for p in validate.QA_BASE_INPUTS}}}
    put(root, "outputs/qa.json", qa)
    put(root, "outputs/visual-review.json", {"status": "passed", "videos": [
        {"video_sha256": v["sha256"], "status": "passed"} for v in videos]})
    put(root, "outputs/audio-quality.json", [{"video_sha256": v["sha256"], "status": "passed"} for v in videos])
    put(root, "research/event/editorial_review.json", {"overall_status": "pass", "input_hashes": inputs})
    return manifest, qa


class ReleaseGates(unittest.TestCase):
    def test_valid_bound_release_can_finalize_and_finalize_again(self):
        with fixture_workspace() as root:
            finalized_fixture(root)
            self.assertEqual(finalize.finalize()["status"], "complete_local_delivery")
            self.assertEqual(finalize.finalize()["status"], "complete_local_delivery")

    def test_finalization_rejects_config_or_review_change_after_qa(self):
        for path in ("config/event.json", "research/media/clip_review.json"):
            with self.subTest(path=path), fixture_workspace() as root:
                finalized_fixture(root)
                value = core.read_json(root / path)
                value["revision"] = "changed after QA"
                put(root, path, value)
                with self.assertRaises(ValueError):
                    finalize.finalize()

    def test_finalization_rechecks_additional_captured_input(self):
        with fixture_workspace() as root:
            manifest, qa = finalized_fixture(root)
            path = "research/event/extra.json"
            put(root, path, {"value": "reviewed"})
            sha = core.digest(root / path)
            manifest["input_hashes"][path] = sha
            for video in manifest["videos"]:
                video["input_hashes"][path] = sha
            put(root, "outputs/manifest.json", manifest)
            qa["input_hashes"].update({path: sha, "outputs/manifest.json": core.digest(root / "outputs/manifest.json")})
            put(root, "outputs/qa.json", qa)
            put(root, path, {"value": "changed"})
            with self.assertRaises(ValueError):
                finalize.finalize()

    def test_finalization_rechecks_render_inputs_after_technical_qa(self):
        with fixture_workspace() as root:
            finalized_fixture(root)
            put(root, "research/event/video_plan.json", {"revision": "new narration never rendered"})
            review = core.read_json(root / "research/event/editorial_review.json")
            review["input_hashes"]["research/event/video_plan.json"] = core.digest(root / "research/event/video_plan.json")
            put(root, "research/event/editorial_review.json", review)
            with self.assertRaises(ValueError):
                finalize.finalize()
            self.assertFalse((root / "outputs/delivery.json").exists())

    def test_finalization_rejects_qa_without_current_input_bindings(self):
        with fixture_workspace() as root:
            _, qa = finalized_fixture(root)
            qa.pop("input_hashes")
            put(root, "outputs/qa.json", qa)
            with self.assertRaises(ValueError):
                finalize.finalize()

    def test_finalization_rejects_missing_requested_format(self):
        with fixture_workspace() as root:
            manifest, qa = finalized_fixture(root)
            manifest["videos"].pop()
            put(root, "outputs/manifest.json", manifest)
            qa["input_hashes"]["outputs/manifest.json"] = core.digest(root / "outputs/manifest.json")
            put(root, "outputs/qa.json", qa)
            with self.assertRaises(ValueError):
                finalize.finalize()

    def test_failed_second_format_preserves_authoritative_previous_release(self):
        with fixture_workspace() as root:
            finalized_fixture(root)
            previous_manifest = (root / "outputs/manifest.json").read_bytes()
            previous_edl = (root / "outputs/versions/fixture/edit-plan.json").read_bytes()
            def fake_render(name, plan, editorial, catalog, output_dir):
                if name == "landscape":
                    raise RuntimeError("Synthetic second-format failure")
                (output_dir / "new-first-format.mp4").write_bytes(b"candidate")
                return {"format": name, "path": str((output_dir / "new-first-format.mp4").relative_to(root))}, []
            with patch.object(render, "plans", return_value={"vertical": {}, "landscape": {}}), \
                 patch.object(render, "render_one", side_effect=fake_render):
                with self.assertRaisesRegex(RuntimeError, "second-format"):
                    render.render("both")
            self.assertEqual((root / "outputs/manifest.json").read_bytes(), previous_manifest)
            self.assertEqual((root / "outputs/versions/fixture/edit-plan.json").read_bytes(), previous_edl)

    def test_scene_rejects_event_match_for_an_older_source_hash(self):
        scene = {"id": "clip", "source_id": "s1", "event_ids": ["Q01"],
                 "source_in": 1, "source_out_limit": 5, "narration": "Verified story."}
        editorial = {"timeline": [{"id": "Q01", "media_matches": [
            {"source_id": "s1", "source_sha256": "old-content", "in": 0, "out": 10}]}]}
        asset = {"sha256": "new-content", "duration": 10, "reviewed_ranges": [{"in": 0, "out": 10}]}
        with self.assertRaises(ValueError):
            render.checked_scene(scene, editorial, asset)

    def test_analysis_rejects_review_changed_since_catalog(self):
        with fixture_workspace() as root:
            put(root, "research/media/clip_review.json", {"review": "new: only 0-2 seconds approved"})
            official = {"driver_number": 3, "position": 1, "q1_seconds": 93, "q2_seconds": 92, "q3_seconds": 91}
            put(root, "research/event/event_bundle.json", {
                "event": {"id": "release-fixture", "session_key": 11384}, "results": [official],
                "sources": [{"id": "evidence"}], "timeline": [{"id": "Q01", "source_ids": ["evidence"]}],
                "assets": [], "ranked_ideas": []})
            put(root, "data/processed/catalog.json", {
                "event_id": "release-fixture", "sources": [{"id": "s1", "asset_id": "a1"}],
                "assets": [{"id": "a1", "sha256": "original-sha", "duration": 10,
                            "reviewed_ranges": [{"in": 0, "out": 10}],
                            "review_receipt_sha256": "old-review-hash"}]})
            put(root, "research/event/media_matches.json", {"event_id": "release-fixture", "matches": {
                "Q01": [{"source_id": "s1", "source_sha256": "original-sha", "in": 5, "out": 9}]}})
            data = {"session_result.json": [{"driver_number": 3, "position": 1, "duration": [93, 92, 91]}],
                    "weather.json": [], "laps.json": []}
            with patch.object(analyze_session, "verified_data", return_value=data):
                with self.assertRaises(ValueError):
                    analyze_session.analyze_qualifying()

    def test_phase_reconciliation_rejects_nonfinite_api_time(self):
        official = [{"driver_number": 3, "position": 1, "q1_seconds": 93, "q2_seconds": 92, "q3_seconds": 91}]
        for value in (float("nan"), float("inf"), True, -91):
            with self.subTest(value=value):
                api = [{"driver_number": 3, "position": 1, "duration": [93, 92, value]}]
                self.assertTrue(analyze_session.reconcile_qualifying(official, api))

    def test_technical_qa_requires_render_and_companion_hash_bindings(self):
        with fixture_workspace() as root:
            manifest, _ = finalized_fixture(root)
            put(root, "data/processed/editorial.json", {
                "event": {"id": "release-fixture"}, "sources": [{"id": "evidence"}],
                "timeline": [{"id": "Q01", "source_ids": ["evidence"]}], "ideas": []})
            scene = {"event_ids": ["Q01"], "claim_source_ids": ["evidence"], "duration": 2}
            put(root, manifest["edit_plan"], {"event_id": "release-fixture", "edits": {
                "vertical": [scene], "landscape": [scene]}})
            manifest["edit_plan_sha256"] = core.digest(root / manifest["edit_plan"])
            for video in manifest["videos"]:
                video.update(width=720, height=1280)
                (root / video["captions"]).write_text("1\n00:00:00,000 --> 00:00:02,000\nA caption.\n")
                video['companion_sha256']={key:core.digest(root/video[key]) for key in validate.COMPANIONS}
            manifest['input_hashes']={p:core.digest(root/p) for p in validate.required_render_inputs()}
            for video in manifest['videos']:
                video['input_hashes']=dict(manifest['input_hashes'])
            put(root, "outputs/manifest.json", manifest)
            info = {"format": {"duration": "2"}, "streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 720, "height": 1280, "duration": "2"},
                {"codec_type": "audio", "codec_name": "aac", "duration": "2"}]}
            with patch.object(validate, "probe", return_value=info), patch.object(validate, "run"):
                result = validate.validate()
            self.assertEqual(result["status"], "passed", result['errors'])
            self.assertTrue(set(manifest['input_hashes']).issubset(result['input_hashes']))
            for missing in ('input_hashes','companion_sha256'):
                with self.subTest(missing=missing):
                    incomplete=deepcopy(manifest)
                    for video in incomplete['videos']:video.pop(missing)
                    put(root,'outputs/manifest.json',incomplete)
                    with patch.object(validate, "probe", return_value=info), patch.object(validate, "run"):
                        result=validate.validate()
                    self.assertEqual(result['status'],'failed')

    def test_legacy_compatibility_is_specific_to_preversioned_sprint(self):
        with fixture_workspace() as root:
            cfg=core.read_json(root/'config/event.json')
            cfg['id']='2026-singapore-sprint'
            cfg['session_name']='Sprint'
            put(root,'config/event.json',cfg)
            legacy={'event_id':cfg['id'],'videos':[
                {'format':name,'path':f'outputs/singapore-sprint-2026-{name}.mp4'}
                for name in ('vertical','landscape')]}
            self.assertTrue(validate.legacy_release(legacy))
            self.assertFalse(validate.legacy_release({**legacy,'run_id':'new'}))
            self.assertFalse(validate.legacy_release({**legacy,'event_id':'2026-singapore-qualifying'}))


if __name__ == "__main__":
    unittest.main()
