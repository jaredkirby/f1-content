"""Offline model-work workflows with synthetic event files and literal outcomes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


def write(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value) if not isinstance(value, str) else value)
    return {"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def event_workspace(root):
    identity = {"id": "synthetic-session", "year": 2026, "country_name": "Singapore",
                "session_name": "Qualifying", "event_date": "2026-10-10",
                "session_key": 12345, "meeting_key": 1234}
    write(root, "config/event.json", {**identity, "reserve_bytes": 1})
    return identity


def work_record(root, identity):
    evidence = write(root, "research/event/evidence.txt", "Synthetic evidence only.")
    prompt = write(root, "research/event/prompt.txt", "Grounded vertical story.")
    output = write(root, "outputs/versions/reference/script.txt", "A grounded synthetic story.")
    usage = {"input_tokens": None, "output_tokens": None, "reasoning_tokens": None,
             "token_scope": "unknown", "cost_usd": None, "estimated_cost_usd": None,
             "cost_source": "unknown", "machine_seconds": None, "human_revision_seconds": None}
    model = {"provider": "OpenAI", "model": None, "access": "chatgpt_subscription",
             "identity_source": "unknown", "settings": None, "session_reference": None,
             "revision": None, "quantization": None}
    attempt = {"attempt_id": "attempt-1", "status": "completed", "model": model,
               "outputs": [output], "usage": usage,
               "eligibility": {"status": "not_reviewed", "failures": [], "review_files": []},
               "error": None, "provenance": []}
    return {"schema_version": "f1.model_work.v1", "work_id": "reference-1",
            "comparison_id": "story-pilot", "task": "story_script", "format": "vertical",
            "event_id": identity["id"], "event_identity": identity,
            "prompt_version": "script-v1", "rubric_version": "human-brief-v1",
            "preference_version": None, "preference_binding": None,
            "inputs": [prompt], "evidence": [evidence], "attempts": [attempt]}


def finished_output(root, identity):
    video = write(root, "outputs/versions/reference/vertical.mp4", "Synthetic video bytes, not real footage.")
    companions = {key: write(root, "outputs/versions/reference/" + filename, key)
                  for key, filename in (("captions", "vertical.vtt"), ("script", "finished-script.txt"),
                                        ("thumbnail", "vertical.jpg"))}
    edl = write(root, "outputs/versions/reference/edit-plan.json", {"event_id": identity["id"]})
    manifest = {"event_id": identity["id"], "run_id": "reference", "edit_plan": edl["path"],
                "edit_plan_sha256": edl["sha256"], "videos": [{"format": "vertical", **video,
                    **{key: item["path"] for key, item in companions.items()},
                    "companion_sha256": {key: item["sha256"] for key, item in companions.items()}}]}
    return write(root, "outputs/manifest.json", manifest)


def human_feedback(identity, manifest, comments, *, outcome="approved", model_runs=None, correction_of=None):
    return {"event_id": identity["id"], "manifest_sha256": manifest["sha256"],
            "source": {"kind": "human", "reviewer": "user", "reference": "synthetic explicit feedback"},
            "outcome": outcome, "comments": comments,
            "scope": {"kind": "output", "target": manifest["sha256"]},
            "model_runs": [] if model_runs is None else model_runs, "correction_of": correction_of}


class ModelWorkflows(unittest.TestCase):
    def test_comparison_scope_cannot_hide_changed_inputs_of_latest_linked_model_work(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            record.update(comparison_id="other-pilot", work_id="other-reference")
            record["inputs"] = [write(root, "research/event/other-prompt.txt", "Independent second prompt.")]
            other = import_model_work(write(root, "runs/other-work.json", record)["path"], root=root)
            manifest = finished_output(root, identity)
            record_feedback(human_feedback(identity, manifest, "Initial approval.", model_runs=[
                {"path": saved["receipt_path"], "sha256": saved["sha256"]}]), root=root)
            record_feedback(human_feedback(identity, manifest, "Latest reviewed version approved.", model_runs=[
                {"path": other["receipt_path"], "sha256": other["sha256"]}]), root=root)
            write(root, "research/event/other-prompt.txt", "Changed after latest human review.")
            for comparison in (None, "story-pilot", "other-pilot"):
                report = evaluation_report(comparison, root=root)
                self.assertEqual(report["quality"]["human_approved_outputs"], 0)
                self.assertEqual(len(report["quality"]["stale_feedback"]), 1)
                self.assertEqual(report["quality"]["comments"][-1]["comments"], "Latest reviewed version approved.")

    def test_comparison_scope_cannot_hide_a_corrupt_latest_human_decision_binding(self):
        from f1_pipeline.feedback import feedback_status, record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            record.update(comparison_id="other-pilot", work_id="other-reference")
            other = import_model_work(write(root, "runs/other-work.json", record)["path"], root=root)
            manifest = finished_output(root, identity)
            record_feedback(human_feedback(identity, manifest, "Initial approval.", model_runs=[
                {"path": saved["receipt_path"], "sha256": saved["sha256"]}]), root=root)
            record_feedback(human_feedback(identity, manifest, "Confirmed after another viewing.", model_runs=[
                {"path": other["receipt_path"], "sha256": other["sha256"]}]), root=root)
            changed = other["record"]
            changed["imported_at"] = "changed after latest human review"
            write(root, other["receipt_path"], changed)
            self.assertEqual(feedback_status(root=root)["status"], "not_reviewed")
            for comparison in (None, "story-pilot"):
                report = evaluation_report(comparison, root=root)
                self.assertEqual(report["quality"]["human_approved_outputs"], 0)
                self.assertEqual(len(report["quality"]["stale_feedback"]), 1)
                self.assertEqual(report["quality"]["comments"][-1]["comments"], "Confirmed after another viewing.")

    def test_orphan_provider_usage_and_import_payload_remain_visible_after_input_integrity_failure(self):
        from f1_pipeline.model_evaluation import evaluation_report
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            assets = "runs/model-evaluations/story-pilot/pending-work.assets/"
            write(root, assets + "intent.json", {"event_identity": identity, "task": "story_script",
                "format": "vertical", "inputs": record["inputs"], "evidence": record["evidence"],
                "preflight": {}, "status": "execution_requested"})
            write(root, assets + "provider-receipt.json", {"schema_version": "f1.hosted-inference.v1",
                "provider": "deepinfra", "status": "succeeded", "observed_model": "observed-model",
                "inference_attempted": True, "actual_model_inference": True, "attempts": 1,
                "usage": {"input_tokens": 120, "output_tokens": 30, "reasoning_tokens": 10},
                "cost": {"provider_estimated_cost_usd": 0.002, "actual_billing_usd": None},
                "elapsed_seconds": 2.5})
            write(root, assets + "model-work-import.json", record)
            write(root, "research/event/evidence.txt", "Evidence changed after raw provider receipt.")
            report = evaluation_report("story-pilot", root=root)
            incomplete = report["incomplete_execution_evidence"][0]
            self.assertEqual(incomplete["provider_receipt_observation"]["usage"]["input_tokens"], 120)
            self.assertEqual(incomplete["provider_receipt_observation"]["cost"]["provider_estimated_cost_usd"], 0.002)
            self.assertTrue(any("hash mismatch" in error for error in incomplete["errors"]))
            self.assertTrue(any(item["path"].endswith("model-work-import.json") for item in incomplete["artifacts"]))
            self.assertEqual(report["attempt_count"], 0)
            self.assertIsNone(report["measurements"]["actual_total_cost_usd"])

    def test_orphan_execution_intent_makes_cost_unknown_without_fabricating_an_attempt(self):
        from f1_pipeline.model_evaluation import evaluation_report
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            write(root, "runs/model-evaluations/story-pilot/pending-work.assets/intent.json", {
                "event_identity": identity, "task": "story_script", "format": "vertical",
                "inputs": record["inputs"], "evidence": record["evidence"], "preflight": {},
                "status": "execution_requested"})
            report = evaluation_report("story-pilot", root=root)
            self.assertEqual(report["attempt_count"], 0)
            self.assertEqual(report["incomplete_execution_evidence_count"], 1)
            self.assertEqual(report["incomplete_execution_evidence"][0]["work_id"], "pending-work")
            self.assertIsNone(report["measurements"]["actual_total_cost_usd"])
            self.assertIsNone(report["measurements"]["total_input_tokens"])

    def test_a_later_rejection_linking_another_comparison_updates_the_original_comparison(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            record.update(comparison_id="other-pilot", work_id="other-reference")
            other = import_model_work(write(root, "runs/other-work.json", record)["path"], root=root)
            manifest = finished_output(root, identity)
            record_feedback(human_feedback(identity, manifest, "Initial approval.", model_runs=[
                {"path": saved["receipt_path"], "sha256": saved["sha256"]}]), root=root)
            record_feedback(human_feedback(identity, manifest, "Reject after another viewing.", outcome="rejected",
                model_runs=[{"path": other["receipt_path"], "sha256": other["sha256"]}]), root=root)
            for comparison in ("story-pilot", "other-pilot"):
                report = evaluation_report(comparison, root=root)
                self.assertEqual(report["quality"]["human_approved_outputs"], 0)
                self.assertEqual(report["quality"]["human_rejected_outputs"], 1)
                self.assertEqual(report["quality"]["comments"][-1]["comments"], "Reject after another viewing.")
            self.assertTrue(evaluation_report("story-pilot", root=root)["quality"]["output_decisions"][0][
                "historical_operator_attribution_carried"])

    def test_latest_unlinked_human_rejection_overrides_previously_attributed_approval(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        for correction in (False, True):
            with self.subTest(correction=correction), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                identity = event_workspace(root)
                saved = import_model_work(write(root, "runs/work-input.json", work_record(root, identity))["path"], root=root)
                manifest = finished_output(root, identity)
                approval = record_feedback(human_feedback(identity, manifest, "Initial approval.", model_runs=[
                    {"path": saved["receipt_path"], "sha256": saved["sha256"]}]), root=root)
                record_feedback(human_feedback(identity, manifest, "Reject: the opening is too slow.",
                    outcome="rejected", correction_of=approval["id"] if correction else None), root=root)
                report = evaluation_report("story-pilot", root=root)
                self.assertEqual(report["quality"]["human_approved_outputs"], 0)
                self.assertEqual(report["quality"]["human_rejected_outputs"], 1)
                self.assertEqual(report["quality"]["comments"][-1]["comments"], "Reject: the opening is too slow.")
                self.assertIsNone(report["measurements"]["cost_per_accepted_output_usd"])

    def test_corrupt_linked_receipt_cannot_hide_feedback_or_make_cost_look_complete(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            saved = import_model_work(write(root, "runs/work-input.json", work_record(root, identity))["path"], root=root)
            manifest = finished_output(root, identity)
            record_feedback({"event_id": identity["id"], "manifest_sha256": manifest["sha256"],
                "source": {"kind": "human", "reviewer": "user", "reference": "synthetic explicit feedback"},
                "outcome": "approved", "comments": "Preserve this feedback.",
                "scope": {"kind": "output", "target": manifest["sha256"]},
                "model_runs": [{"path": saved["receipt_path"], "sha256": saved["sha256"]}]}, root=root)
            write(root, saved["receipt_path"], "{ damaged JSON")
            report = evaluation_report(root=root)
            self.assertEqual(report["quality"]["human_approved_outputs"], 0)
            self.assertEqual(len(report["quality"]["stale_feedback"]), 1)
            self.assertEqual(report["quality"]["comments"][0]["comments"], "Preserve this feedback.")
            self.assertIsNone(report["measurements"]["actual_total_cost_usd"])

    def test_legacy_companion_versions_with_one_manifest_hash_keep_separate_review_bindings(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            identity.update(id="2026-singapore-sprint", session_name="Sprint")
            write(root, "config/event.json", {**identity, "reserve_bytes": 1})
            record = work_record(root, identity)
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            video = write(root, "outputs/singapore-sprint-2026-vertical.mp4", "Synthetic legacy fixture.")
            companions = {key: write(root, "outputs/legacy-" + key + ".txt", key)
                          for key in ("captions", "script", "thumbnail")}
            write(root, "outputs/edit-plan.json", {"synthetic": True})
            manifest = write(root, "outputs/manifest.json", {"event_id": identity["id"], "videos": [{
                "format": "vertical", **video, **{key: value["path"] for key, value in companions.items()}}]})
            payload = {"event_id": identity["id"], "manifest_sha256": manifest["sha256"],
                "source": {"kind": "human", "reviewer": "user", "reference": "synthetic explicit feedback"},
                "outcome": "approved", "comments": "First companion version approved.",
                "scope": {"kind": "output", "target": manifest["sha256"]},
                "model_runs": [{"path": saved["receipt_path"], "sha256": saved["sha256"]}]}
            record_feedback(payload, root=root)
            write(root, companions["thumbnail"]["path"], "Changed legacy thumbnail.")
            payload.update(outcome="rejected", comments="Second companion version rejected.")
            record_feedback(payload, root=root)
            report = evaluation_report(root=root)
            self.assertEqual(report["quality"]["human_approved_outputs"], 0)
            self.assertEqual(report["quality"]["human_rejected_outputs"], 1)
            self.assertEqual(len(report["quality"]["stale_feedback"]), 1)

    def test_import_refuses_relative_binding_aliases_that_cross_parent_segments(self):
        from f1_pipeline.model_evaluation import import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            record["evidence"][0]["path"] = "research/event/../event/evidence.txt"
            with self.assertRaisesRegex(ValueError, "canonical"):
                import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)

    def test_changed_model_receipt_keeps_the_human_comment_visible_as_stale(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            manifest = finished_output(root, identity)
            record_feedback({"event_id": identity["id"], "manifest_sha256": manifest["sha256"],
                "source": {"kind": "human", "reviewer": "user", "reference": "synthetic explicit feedback"},
                "outcome": "approved", "comments": "Keep this explanation.",
                "scope": {"kind": "output", "target": manifest["sha256"]},
                "model_runs": [{"path": saved["receipt_path"], "sha256": saved["sha256"]}]}, root=root)
            changed = saved["record"]
            changed["imported_at"] = "altered receipt metadata"
            write(root, saved["receipt_path"], changed)
            report = evaluation_report(root=root)
            self.assertEqual(report["quality"]["human_approved_outputs"], 0)
            self.assertEqual(len(report["quality"]["stale_feedback"]), 1)
            self.assertEqual(report["quality"]["comments"][0]["comments"], "Keep this explanation.")

    def test_saved_preference_binding_remains_valid_after_a_later_human_change(self):
        from f1_pipeline.feedback import preference_status, record_preference
        from f1_pipeline.model_evaluation import import_model_work, validate_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            preference = {"event_id": identity["id"], "key": "storytelling",
                "instruction": "Grounded explanation for vertical phone viewing.",
                "scope": {"kind": "project", "target": "f1-content"},
                "source": {"kind": "human", "reviewer": "user", "reference": "synthetic explicit instruction"}}
            record_preference(preference, root=root)
            view = preference_status(root=root)
            record = work_record(root, identity)
            record.update(preference_version=view["version"], preference_binding={"version": view["version"],
                "record_hashes": {item["id"]: item["record_sha256"] for item in view["confirmed"]}})
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            preference["instruction"] = "Preserve grounding and explain the causal chain more clearly."
            record_preference(preference, root=root)
            self.assertNotEqual(preference_status(root=root)["version"], view["version"])
            self.assertEqual(validate_model_work(saved["record"], root=root)["preference_version"], view["version"])

    def test_model_work_receipts_cannot_be_overwritten_or_rebound_to_changed_inputs(self):
        from f1_pipeline.model_evaluation import import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            source = write(root, "runs/work-input.json", record)
            import_model_work(source["path"], root=root)
            with self.assertRaises(FileExistsError):
                import_model_work(source["path"], root=root)
            write(root, "research/event/evidence.txt", "Changed evidence.")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                import_model_work(source["path"], root=root)

    def test_historical_approval_survives_manifest_change_but_not_reviewed_byte_change(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            manifest = finished_output(root, identity)
            record_feedback({"event_id": identity["id"], "manifest_sha256": manifest["sha256"],
                "source": {"kind": "human", "reviewer": "user", "reference": "synthetic explicit feedback"},
                "outcome": "approved", "comments": "Readable on my phone.",
                "scope": {"kind": "output", "target": manifest["sha256"]},
                "model_runs": [{"path": saved["receipt_path"], "sha256": saved["sha256"]}]}, root=root)
            current = json.loads((root / "outputs/manifest.json").read_text())
            current["status"] = "changed-current-manifest"
            write(root, "outputs/manifest.json", current)
            self.assertEqual(evaluation_report(root=root)["quality"]["human_approved_outputs"], 1)
            write(root, "outputs/versions/reference/vertical.mp4", "Changed reviewed bytes.")
            stale = evaluation_report(root=root)
            self.assertEqual(stale["quality"]["human_approved_outputs"], 0)
            self.assertEqual(len(stale["quality"]["stale_feedback"]), 1)
            self.assertIsNone(stale["measurements"]["cost_per_accepted_output_usd"])

    def test_import_requires_explicit_prompt_version_without_an_invented_default(self):
        from f1_pipeline.model_evaluation import import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            del record["prompt_version"]
            with self.assertRaisesRegex(ValueError, "prompt_version"):
                import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)

    def test_limited_subscription_route_preserves_work_for_human_choice(self):
        from f1_pipeline.model_evaluation import route_advice
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_workspace(root)
            result = route_advice("story_script", subscription_status="limited", root=root)
            self.assertEqual(result["route"], "human_decision")
            self.assertFalse(result["provider_calls"])

    def test_report_groups_efficiency_by_task_format_and_observed_settings(self):
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            model = record["attempts"][0]["model"]
            model.update(model="observed-model", identity_source="observed", settings={"reasoning": "high"})
            record["attempts"][0]["usage"].update(input_tokens=100, token_scope="account_shared")
            import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            record["work_id"] = "reference-2"
            model["settings"] = {"reasoning": "low"}
            import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            report = evaluation_report(root=root)
            self.assertEqual(len(report["groups"]), 2)
            self.assertEqual({group["model"]["settings"]["reasoning"] for group in report["groups"]}, {"high", "low"})
            self.assertEqual(report["measurements"]["known_input_tokens"], 0)
            self.assertEqual(report["measurements"]["account_shared_usage_attempts"], 2)

    def test_efficiency_counts_all_work_once_per_human_approved_finished_version(self):
        from f1_pipeline.feedback import record_feedback
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = event_workspace(root)
            record = work_record(root, identity)
            first = record["attempts"][0]
            first["usage"].update(cost_usd=2, cost_source="operator_reported")
            failed = json.loads(json.dumps(first))
            failed.update(attempt_id="failed-first", status="failed", outputs=[], error="schema failed")
            failed["usage"]["cost_usd"] = 1
            record["attempts"].insert(0, failed)
            saved = import_model_work(write(root, "runs/work-input.json", record)["path"], root=root)
            record["work_id"], record["task"] = "reviewer-1", "claim_review"
            record["attempts"] = [first]
            record["attempts"][0]["usage"]["cost_usd"] = 4
            other = import_model_work(write(root, "runs/other-work.json", record)["path"], root=root)
            manifest = finished_output(root, identity)
            record_feedback({"event_id": identity["id"], "manifest_sha256": manifest["sha256"],
                "source": {"kind": "human", "reviewer": "user", "reference": "synthetic explicit feedback"},
                "outcome": "approved", "comments": "Clear story; keep the grounded explanation.",
                "scope": {"kind": "output", "target": manifest["sha256"]},
                "model_runs": [{"path": saved["receipt_path"], "sha256": saved["sha256"]},
                               {"path": other["receipt_path"], "sha256": other["sha256"]}]}, root=root)
            report = evaluation_report(root=root)
            self.assertEqual(report["quality"]["human_approved_outputs"], 1)
            self.assertEqual(report["measurements"]["actual_total_cost_usd"], 7)
            self.assertEqual(report["measurements"]["cost_per_accepted_output_usd"], 7)
            self.assertEqual(report["failed_attempts"], 1)
            self.assertEqual(report["quality"]["comments"][0]["comments"],
                             "Clear story; keep the grounded explanation.")

    def test_import_cannot_claim_passed_eligibility_with_a_known_failure(self):
        from f1_pipeline.model_evaluation import import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            record["attempts"][0]["eligibility"].update(status="passed", failures=["unsupported claim"])
            source = write(root, "runs/work-input.json", record)
            with self.assertRaisesRegex(ValueError, "eligibility"):
                import_model_work(source["path"], root=root)

    def test_route_advice_uses_deterministic_then_subscription_and_requires_a_decision_at_limits(self):
        from f1_pipeline.model_evaluation import route_advice
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_workspace(root)
            self.assertEqual(route_advice("hash_check", root=root)["route"], "deterministic")
            self.assertEqual(route_advice("story_script", root=root)["route"], "codex_chatgpt_subscription")
            limited = route_advice("story_script", subscription_status="unavailable", root=root)
            self.assertEqual(limited["route"], "human_decision")
            self.assertTrue(limited["requires_human_decision"])
            self.assertFalse(limited["provider_calls"])

    def test_report_keeps_estimates_separate_and_cost_undefined_without_acceptance(self):
        from f1_pipeline.model_evaluation import evaluation_report, import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            attempt = record["attempts"][0]
            attempt["usage"]["estimated_cost_usd"] = 0.25
            source = write(root, "runs/work-input.json", record)
            import_model_work(source["path"], root=root)
            report = evaluation_report(root=root)
            self.assertEqual(report["attempt_count"], 1)
            self.assertEqual(report["measurements"]["known_estimated_cost_usd"], 0.25)
            self.assertEqual(report["measurements"]["unknown_cost_attempts"], 1)
            self.assertIsNone(report["measurements"]["actual_total_cost_usd"])
            self.assertIsNone(report["measurements"]["cost_per_accepted_output_usd"])
            self.assertEqual(report["quality"]["human_approved_outputs"], 0)

    def test_import_refuses_an_unconfirmed_preference_version(self):
        from f1_pipeline.model_evaluation import import_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            record.update(preference_version="invented-brief",
                          preference_binding={"version": "invented-brief", "record_hashes": {}})
            source = write(root, "runs/work-input.json", record)
            with self.assertRaisesRegex(ValueError, "confirmed preference"):
                import_model_work(source["path"], root=root)

    def test_import_retains_unknown_model_and_actual_failed_attempt(self):
        from f1_pipeline.model_evaluation import import_model_work, validate_model_work
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = work_record(root, event_workspace(root))
            failed = json.loads(json.dumps(record["attempts"][0]))
            failed.update(attempt_id="failed-first", status="failed", outputs=[], error="schema failed")
            failed["eligibility"] = {"status": "failed", "failures": ["schema"], "review_files": []}
            failed["usage"].update(cost_usd=0.5, cost_source="operator_reported")
            record["attempts"].insert(0, failed)
            source = write(root, "runs/work-input.json", record)
            saved = import_model_work(source["path"], root=root)
            retained = validate_model_work(saved["record"], root=root)
            self.assertEqual(retained["attempts"][0]["usage"]["cost_usd"], 0.5)
            self.assertIsNone(retained["attempts"][1]["model"]["model"])
            self.assertIsNone(retained["attempts"][1]["usage"]["cost_usd"])
            self.assertEqual(saved["receipt_path"], "runs/model-evaluations/story-pilot/reference-1.json")


if __name__ == "__main__":
    unittest.main()
