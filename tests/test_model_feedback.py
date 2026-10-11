"""Human feedback workflows use synthetic files, never real event deliveries."""
import json
import tempfile
import unittest
from pathlib import Path

from f1_pipeline.core import digest, read_json, write_json
from f1_pipeline.feedback import (feedback_status, preference_status, read_feedback,
                                  record_feedback, record_preference)


class ModelFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="f1-human-feedback-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {
            "id": "feedback-fixture", "year": 2026, "country_name": "Singapore",
            "session_name": "Qualifying", "event_date": "2026-10-10",
            "session_key": 11384, "meeting_key": 1296, "reserve_bytes": 1,
            "formats": ["vertical"],
        }
        write_json(self.root / "config/event.json", self.config)
        directory = self.root / "outputs/versions/reference"
        directory.mkdir(parents=True)
        files = {"path": "vertical.mp4", "captions": "vertical.srt",
                 "script": "vertical.txt", "thumbnail": "vertical.jpg"}
        for key, name in files.items():
            (directory / name).write_bytes(("Synthetic " + key).encode())
        paths = {key: str((directory / name).relative_to(self.root)) for key, name in files.items()}
        plan = "outputs/versions/reference/edit-plan.json"
        write_json(self.root / plan, {"event_id": self.config["id"], "edits": {}})
        self.manifest = {
            "event_id": self.config["id"], "run_id": "reference", "edit_plan": plan,
            "edit_plan_sha256": digest(self.root / plan), "videos": [{
                "format": "vertical", **paths, "sha256": digest(self.root / paths["path"]),
                "companion_sha256": {key: digest(self.root / paths[key])
                                     for key in ("captions", "script", "thumbnail")},
            }],
        }
        write_json(self.root / "outputs/manifest.json", self.manifest)
        self.source = {"kind": "human", "reviewer": "user", "reference": "explicit chat feedback"}

    def payload(self, **changes):
        sha = digest(self.root / "outputs/manifest.json")
        return {
            "event_id": self.config["id"], "manifest_sha256": sha,
            "source": dict(self.source), "outcome": "approved",
            "comments": "The grounding is clear on my phone.",
            "scope": {"kind": "output", "target": sha}, **changes,
        }

    def test_exact_current_output_requires_explicit_human_approval(self):
        self.assertEqual(feedback_status(self.root)["status"], "not_reviewed")
        record = record_feedback(self.payload(), self.root)
        status = feedback_status(self.root)
        self.assertEqual(status["status"], "approved")
        self.assertEqual(status["feedback_id"], record["id"])
        self.assertEqual(read_feedback(self.root)[0]["comments"], "The grounding is clear on my phone.")
        self.assertNotIn("outputs/manifest.json", record["output_hashes"])
        self.assertEqual(record["manifest_snapshot"], (self.root / "outputs/manifest.json").read_text())

    def test_stale_observed_manifest_cannot_be_approved(self):
        payload = self.payload()
        self.manifest["rendered_at"] = "newer output-set commit"
        write_json(self.root / "outputs/manifest.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "manifest"):
            record_feedback(payload, self.root)
        self.assertEqual(read_feedback(self.root), [])

    def test_changed_or_missing_output_bytes_invalidate_approval(self):
        record_feedback(self.payload(), self.root)
        video = self.root / self.manifest["videos"][0]["path"]
        video.write_bytes(b"replaced after review")
        status = feedback_status(self.root)
        self.assertEqual(status["status"], "not_reviewed")
        self.assertFalse(status["binding_valid"])
        with self.assertRaises(ValueError):
            record_feedback(self.payload(), self.root)
        video.unlink()
        self.assertEqual(feedback_status(self.root)["status"], "not_reviewed")

    def test_feedback_requires_valid_explicit_human_fields(self):
        cases = [
            {"source": {**self.source, "kind": "model"}},
            {"source": {**self.source, "reference": ""}},
            {"source": {**self.source, "reviewer": ""}},
            {"event_id": "other-event"}, {"outcome": "accepted_by_model"},
            {"comments": {"interpretation": "good"}},
            {"scope": {"kind": "project", "target": "f1-content"}},
            {"self_score": 10}, {"usage": {"revision_minutes": float("nan")}},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                record_feedback(self.payload(**changes), self.root)
        self.assertEqual(read_feedback(self.root), [])

    def test_new_manifests_reject_cross_event_traversal_and_incomplete_bindings(self):
        original = json.loads(json.dumps(self.manifest))
        cases = ["event", "traversal", "absolute", "companions", "plan", "empty", "duplicate"]
        for case in cases:
            self.manifest = json.loads(json.dumps(original))
            if case == "event":
                self.manifest["event_id"] = "other-event"
            elif case == "traversal":
                self.manifest["videos"][0]["path"] = "outputs/../config/event.json"
            elif case == "absolute":
                self.manifest["edit_plan"] = str(self.root / original["edit_plan"])
            elif case == "companions":
                self.manifest["videos"][0].pop("companion_sha256")
            elif case == "plan":
                self.manifest.pop("edit_plan_sha256")
            elif case == "empty":
                self.manifest["videos"] = []
            elif case == "duplicate":
                self.manifest["videos"].append(self.manifest["videos"][0])
            write_json(self.root / "outputs/manifest.json", self.manifest)
            with self.subTest(case=case), self.assertRaises(ValueError):
                record_feedback(self.payload(), self.root)
        self.assertEqual(read_feedback(self.root), [])

    def test_edited_or_truncated_ledger_never_supplies_acceptance(self):
        record_feedback(self.payload(), self.root)
        ledger = self.root / "runs/feedback.jsonl"
        original = ledger.read_bytes()
        row = json.loads(original)
        row["comments"] = "An altered comment"
        ledger.write_text(json.dumps(row) + "\n")
        with self.assertRaises(ValueError):
            read_feedback(self.root)
        status = feedback_status(self.root)
        self.assertEqual(status["status"], "not_reviewed")
        self.assertFalse(status["ledger_valid"])
        ledger.write_bytes(original[:-5])
        with self.assertRaises(ValueError):
            record_feedback(self.payload(), self.root)

    def test_correction_preserves_original_and_latest_explicit_decision_wins(self):
        original = record_feedback(self.payload(), self.root)
        correction = record_feedback(self.payload(outcome="rejected", comments="The captions are too small.",
                                                 correction_of=original["id"]), self.root)
        history = read_feedback(self.root)
        self.assertEqual([row["outcome"] for row in history], ["approved", "rejected"])
        self.assertEqual(history[1]["correction_of"], original["id"])
        self.assertEqual(feedback_status(self.root)["feedback_id"], correction["id"])
        with self.assertRaises(ValueError):
            record_feedback(self.payload(correction_of="missing-review"), self.root)
        self.manifest["rendered_at"] = "new output-set commit"
        write_json(self.root / "outputs/manifest.json", self.manifest)
        self.assertEqual(feedback_status(self.root)["status"], "not_reviewed")
        with self.assertRaises(ValueError):
            record_feedback(self.payload(correction_of=correction["id"]), self.root)
        record_feedback(self.payload(outcome="not_reviewed", comments="I have not watched this version."), self.root)
        self.assertEqual([row["outcome"] for row in read_feedback(self.root)],
                         ["approved", "rejected", "not_reviewed"])

    def test_model_attribution_requires_exact_receipt_and_event(self):
        path = "runs/model-evaluations/pilot/reference.json"
        write_json(self.root / path, {"event_id": self.config["id"], "id": "reference"})
        link = {"path": path, "sha256": digest(self.root / path)}
        record = record_feedback(self.payload(model_runs=[link]), self.root)
        self.assertEqual(record["model_runs"], [link])
        write_json(self.root / path, {"event_id": "other-event", "id": "reference"})
        status = feedback_status(self.root)
        self.assertEqual(status["status"], "not_reviewed")
        self.assertTrue(status["errors"])
        for links in ([link], [{"path": path, "sha256": digest(self.root / path)}],
                      [{"path": "config/event.json", "sha256": digest(self.root / "config/event.json")}],
                      [{"path": path, "sha256": "unknown"}], "inferred-model"):
            with self.subTest(links=links), self.assertRaises(ValueError):
                record_feedback(self.payload(model_runs=links), self.root)

    def test_explicit_scoped_preferences_preserve_versions_and_original_text(self):
        self.assertIsNone(preference_status(self.root)["version"])
        payload = {"event_id": self.config["id"], "source": self.source,
                   "key": "primary-experience", "instruction": "Grounded analysis with clear storytelling.",
                   "scope": {"kind": "project", "target": "f1-content"}, "source_feedback_ids": []}
        first = record_preference(payload, self.root)
        feedback = record_feedback(self.payload(), self.root)
        self.assertEqual(feedback["preference_version"], first["id"])
        payload["instruction"] = "Keep the grounding and make the captions larger on a phone."
        second = record_preference(payload, self.root)
        view = preference_status(self.root)
        self.assertEqual(view["version"], second["id"])
        self.assertEqual([row["id"] for row in view["confirmed"]], [second["id"]])
        self.assertEqual([row["instruction"] for row in view["history"]], [
            "Grounded analysis with clear storytelling.",
            "Keep the grounding and make the captions larger on a phone."])
        self.assertEqual(feedback_status(self.root)["status"], "approved")
        self.assertEqual(feedback_status(self.root)["preference_version"], first["id"])
        with self.assertRaises(ValueError):
            record_feedback(self.payload(preference_version=first["id"]), self.root)
        self.assertEqual(read_json(self.root / "research/event/preferences.json")["version"], second["id"])

    def test_preference_scope_and_feedback_sources_cannot_be_inferred(self):
        reviewed = record_feedback(self.payload(outcome="rejected", comments="Please enlarge captions."), self.root)
        payload = {"event_id": self.config["id"], "source": self.source,
                   "key": "captions", "instruction": "Please enlarge captions.",
                   "scope": {"kind": "format", "target": "vertical"},
                   "source_feedback_ids": [reviewed["id"]]}
        preference = record_preference(payload, self.root)
        self.assertEqual(preference_status(self.root)["confirmed"][0]["source_feedback_ids"], [reviewed["id"]])
        cases = [{"scope": {"kind": "inferred", "target": "phone"}},
                 {"scope": {"kind": "event", "target": "other-event"}},
                 {"source": {**self.source, "kind": "engagement"}},
                 {"source_feedback_ids": [preference["id"]]},
                 {"instruction": ""}, {"scope": {"kind": "output", "target": "0" * 64}},
                 {"inferred_rating": 5}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                record_preference({**payload, **changes}, self.root)
        self.assertEqual(len(preference_status(self.root)["history"]), 1)

    def test_retained_sprint_legacy_review_binds_observed_bytes_without_release_claim(self):
        self.config.update(id="2026-singapore-sprint", session_name="Sprint", session_key=11383)
        write_json(self.root / "config/event.json", self.config)
        paths = {"path": "outputs/singapore-sprint-2026-vertical.mp4",
                 "captions": "outputs/legacy.srt", "script": "outputs/legacy.txt",
                 "thumbnail": "outputs/legacy.jpg"}
        for key, relative in paths.items():
            (self.root / relative).write_bytes(("legacy " + key).encode())
        write_json(self.root / "outputs/edit-plan.json", {"event_id": self.config["id"]})
        self.manifest = {"event_id": self.config["id"], "videos": [{
            "format": "vertical", **paths, "sha256": digest(self.root / paths["path"])}]}
        write_json(self.root / "outputs/manifest.json", self.manifest)
        record = record_feedback(self.payload(), self.root)
        self.assertTrue(record["legacy_observed_bindings"])
        self.assertEqual(feedback_status(self.root)["status"], "approved")
        self.assertIn("outputs/edit-plan.json", record["output_hashes"])
        self.assertNotIn("technical_status", record)
        (self.root / paths["captions"]).write_bytes(b"changed caption bytes")
        self.assertEqual(feedback_status(self.root)["status"], "not_reviewed")

    def test_copied_event_history_and_symlink_escape_cannot_create_acceptance(self):
        record_feedback(self.payload(), self.root)
        self.config["session_key"] = 11383
        write_json(self.root / "config/event.json", self.config)
        with self.assertRaisesRegex(ValueError, "identity"):
            read_feedback(self.root)
        self.assertEqual(feedback_status(self.root)["status"], "not_reviewed")
        self.config["session_key"] = 11384
        write_json(self.root / "config/event.json", self.config)
        with tempfile.TemporaryDirectory(prefix="f1-outside-workspace-") as temp:
            external = Path(temp) / "outside.mp4"
            external.write_bytes(b"outside event workspace")
            video = self.root / self.manifest["videos"][0]["path"]
            video.unlink()
            video.symlink_to(external)
            self.manifest["videos"][0]["sha256"] = digest(external)
            write_json(self.root / "outputs/manifest.json", self.manifest)
            with self.assertRaisesRegex(ValueError, "escapes"):
                record_feedback(self.payload(), self.root)

    def test_raw_manifest_serialization_is_preserved_in_historical_feedback(self):
        manifest = self.root / "outputs/manifest.json"
        raw = manifest.read_bytes().replace(b"\n", b"\r\n")
        manifest.write_bytes(raw)
        record = record_feedback(self.payload(), self.root)
        self.assertEqual(record["manifest_snapshot"].encode(), raw)
        self.manifest["rendered_at"] = "next commit"
        write_json(manifest, self.manifest)
        self.assertEqual(read_feedback(self.root)[0]["manifest_snapshot"].encode(), raw)
        self.assertEqual(feedback_status(self.root)["status"], "not_reviewed")

    def test_malformed_record_identity_is_rejected_as_invalid_feedback(self):
        record = record_feedback(self.payload(), self.root)
        record["id"] = ["malformed id"]
        (self.root / "runs/feedback.jsonl").write_text(json.dumps(record) + "\n")
        with self.assertRaises(ValueError):
            read_feedback(self.root)

    def test_status_reports_both_ledger_and_output_failures_without_trusting_view(self):
        record_feedback(self.payload(), self.root)
        (self.root / "runs/feedback.jsonl").write_text("{broken ledger\n")
        (self.root / self.manifest["videos"][0]["path"]).unlink()
        status = feedback_status(self.root, write_view=True)
        self.assertEqual(status["status"], "not_reviewed")
        self.assertFalse(status["binding_valid"])
        self.assertFalse(status["ledger_valid"])
        self.assertEqual(read_json(self.root / "outputs/human-feedback.json")["status"], "not_reviewed")


if __name__ == "__main__":
    unittest.main()
