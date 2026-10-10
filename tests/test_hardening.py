"""Bounded workspace, exact-session collection, derivative and review regressions."""
from contextlib import ExitStack, contextmanager, redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

from f1_pipeline import core, collect, catalog


BASE_CONFIG = {
    "id": "2026-singapore-qualifying", "year": 2026, "country_name": "Singapore",
    "session_name": "Qualifying", "event_date": "2026-10-10", "session_key": 11384,
    "meeting_key": 1296, "timezone": "Asia/Singapore",
}
SESSION = {**{k: BASE_CONFIG[k] for k in ("year", "country_name", "session_name", "session_key", "meeting_key")},
           "date_start": "2026-10-10T13:00:00+00:00", "is_cancelled": False}


@contextmanager
def workspace(configuration=None):
    with tempfile.TemporaryDirectory(prefix="f1-hardening-") as tmp, ExitStack() as stack:
        root = Path(tmp).resolve()
        for module in (core, collect, catalog):
            stack.enter_context(patch.object(module, "ROOT", root))
        if configuration is not None:
            core.write_json(root / "config/event.json", configuration)
        yield root


def receipt(path, url):
    return {"url": url, "path": str(path.relative_to(core.ROOT)), "sha256": core.digest(path),
            "bytes": path.stat().st_size, "http_status": 200}


class WorkspaceTests(unittest.TestCase):
    def test_environment_root_is_absolute_and_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp).resolve()
            with patch.dict(os.environ, {"F1_WORKSPACE": str(expected)}):
                self.assertEqual(core.resolve_workspace(), expected)
            for value in ("", "events/relative", "../elsewhere"):
                with self.assertRaises(ValueError):
                    core.resolve_workspace(value)

    def test_import_honors_event_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, F1_WORKSPACE=str(Path(tmp).resolve()))
            out = subprocess.check_output([sys.executable, "-c", "from f1_pipeline.core import ROOT; print(ROOT)"], env=env, cwd=core.CODE_ROOT, text=True)
            self.assertEqual(out.strip(), str(Path(tmp).resolve()))

    def test_traversal_and_symlink_destinations_rejected(self):
        with workspace(BASE_CONFIG) as root, tempfile.TemporaryDirectory() as outside:
            (root / "escape").symlink_to(outside, target_is_directory=True)
            for path in ("../outside.json", Path(outside) / "external.json", "escape/elsewhere.json"):
                with self.subTest(path=str(path)), self.assertRaises(ValueError):
                    core.write_workspace_json(path, {})
            with patch.object(core, "public_url") as network:
                with self.assertRaises(ValueError):
                    core.fetch("https://example.invalid/data", root / "escape/file.json")
                network.assert_not_called()

    def test_config_requires_exact_identity_and_bounded_paths(self):
        with workspace() as root:
            for key in ("id", "year", "country_name", "session_name", "event_date", "session_key", "meeting_key"):
                value = dict(BASE_CONFIG)
                value.pop(key)
                with self.subTest(missing=key), self.assertRaises(ValueError):
                    core.validate_config(value)
            for changes in ({"year": True}, {"session_key": "latest"}, {"session_name": "Main Qualifying"},
                            {"session_name": []}, {"event_date": "2025-10-10"}, {"event_date": "2026-99-99"},
                            {"paths": {"output": "../elsewhere"}}, {"output_path": "../../escape"},
                            {"telemetry_samples": [{"driver": "../", "lap": 2}]}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    core.validate_config({**BASE_CONFIG, **changes})
            self.assertEqual(core.validate_config(BASE_CONFIG)["telemetry_samples"], [])


class CollectionTests(unittest.TestCase):
    def test_session_rejects_wrong_or_missing_identity(self):
        c = core.validate_config(BASE_CONFIG)
        self.assertEqual(collect.validate_session([SESSION], c), SESSION)
        for key in ("session_key", "meeting_key", "year", "country_name", "session_name"):
            bad = dict(SESSION)
            bad.pop(key)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                collect.validate_session([bad], c)
        for change in ({"session_name": "Sprint Qualifying"}, {"country_name": "Japan"}, {"year": 2025},
                       {"date_start": "2026-10-11T13:00:00Z"}, {"is_cancelled": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                collect.validate_session([{**SESSION, **change}], c)

    def test_every_record_needs_explicit_session(self):
        for rows in ([{}], [{"session_key": None}], [{"session_key": 1}], [{"session_key": "11384"}], [None]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                collect.validate_records(rows, 11384)
        self.assertEqual(collect.validate_records([{ "session_key": 11384}], 11384), [{"session_key": 11384}])

    def test_invalid_config_causes_no_request(self):
        with workspace({"id": "not-ready"}), patch.object(collect, "fetch") as fetch:
            with self.assertRaises(ValueError):
                collect.collect_data()
            fetch.assert_not_called()

    def test_qualifying_has_no_grid_or_implicit_telemetry(self):
        requested = []
        with workspace(BASE_CONFIG) as root:
            def fake_fetch(url, path, **kwargs):
                name = urlparse(url).path.rsplit("/", 1)[-1]
                requested.append(name)
                rows = [SESSION] if name == "sessions" else [{"session_key": 11384}]
                core.write_json(path, rows)
                return receipt(path, url)
            with patch.object(collect, "fetch", side_effect=fake_fetch), patch.object(collect.time, "sleep"), patch.object(collect, "log"), redirect_stdout(io.StringIO()):
                result = collect.collect_data()
            self.assertNotIn("starting_grid", requested)
            self.assertNotIn("car_data", requested)
            self.assertEqual(result["telemetry_samples"], [])
            self.assertEqual(result["status"], "complete")

    def test_failed_driver_fetch_never_uses_stale_disk_file_for_telemetry(self):
        c = {**BASE_CONFIG, "telemetry_samples": [{"driver": "VER", "lap": 2}]}
        requested = []
        with workspace(c) as root:
            core.write_json(root / "data/raw/openf1/drivers.json", [{"session_key": 999, "name_acronym": "VER", "driver_number": 3}])
            def fake_fetch(url, path, **kwargs):
                name = urlparse(url).path.rsplit("/", 1)[-1]
                requested.append(name)
                if name == "drivers":
                    raise RuntimeError("Synthetic unavailable endpoint")
                core.write_json(path, [SESSION] if name == "sessions" else [{"session_key": 11384}])
                return receipt(path, url)
            with patch.object(collect, "fetch", side_effect=fake_fetch), patch.object(collect.time, "sleep"), patch.object(collect, "log"), redirect_stdout(io.StringIO()):
                result = collect.collect_data()
            self.assertNotIn("car_data", requested)
            self.assertEqual(result["status"], "partial")
            self.assertTrue(any("successfully validated drivers" in failure["error"] for failure in result["failures"]))

    def test_explicit_telemetry_uses_configured_lap_and_driver(self):
        c = {**BASE_CONFIG, "telemetry_samples": [{"driver": "VER", "lap": 2, "max_seconds": 30}]}
        requests = []
        with workspace(c):
            def fake_fetch(url, path, **kwargs):
                name = urlparse(url).path.rsplit("/", 1)[-1]
                requests.append(url)
                rows = [{"session_key": 11384}]
                if name == "sessions": rows = [SESSION]
                if name == "drivers": rows = [{"session_key": 11384, "name_acronym": "VER", "driver_number": 3}]
                if name == "laps": rows = [{"session_key": 11384, "driver_number": 3, "lap_number": 2, "date_start": "2026-10-10T13:01:00Z", "lap_duration": 90.0}]
                if name == "car_data": rows = [{"session_key": 11384, "driver_number": 3, "date": "2026-10-10T13:01:10Z", "speed": 200}]
                core.write_json(path, rows)
                return receipt(path, url)
            with patch.object(collect, "fetch", side_effect=fake_fetch), patch.object(collect.time, "sleep"), patch.object(collect, "log"), redirect_stdout(io.StringIO()):
                result = collect.collect_data()
            self.assertEqual(result["telemetry_samples"][0]["lap"], 2)
            self.assertEqual(result["telemetry_samples"][0]["end"], "2026-10-10T13:01:30+00:00")
            self.assertEqual(sum("/car_data?" in url for url in requests), 1)


class CatalogTests(unittest.TestCase):
    def seed_cache(self, path, original_sha, recipe):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture derivative")
        core.write_json(path.with_suffix(".receipt.json"), {
            "original_sha256": original_sha, "recipe_sha256": catalog.recipe_digest(recipe),
            "sha256": core.digest(path), "bytes": path.stat().st_size,
            "validation": "probe_and_full_decode"})

    def test_corruption_and_recipe_changes_invalidate_both_caches(self):
        with workspace() as root:
            for name, recipe in (("proxy.mp4", catalog.PROXY_RECIPE), ("sheet.jpg", catalog.CONTACT_RECIPE)):
                path = root / name
                self.seed_cache(path, "abc", recipe)
                self.assertTrue(catalog.cached_derivative(path, "abc", recipe))
                self.assertFalse(catalog.cached_derivative(path, "abc", {**recipe, "version": 99}))
                path.write_bytes(b"CORRUPTION")
                self.assertFalse(catalog.cached_derivative(path, "abc", recipe))

    def test_failed_derivative_never_replaces_previous_output(self):
        with workspace() as root:
            output = root / "proxy.mp4"
            output.write_bytes(b"previous good bytes")
            original = root / "original.mp4"
            original.write_bytes(b"fixture original")
            def fail(args, **kwargs):
                Path(args[-1]).write_bytes(b"partial broken video")
                raise RuntimeError("Synthetic failed encode")
            with patch.object(catalog, "run", side_effect=fail), self.assertRaises(RuntimeError):
                catalog.build_derivative(original, output, "abc", 10, False, catalog.PROXY_RECIPE)
            self.assertEqual(output.read_bytes(), b"previous good bytes")
            self.assertEqual(list(root.glob(".proxy-*")), [])

    def test_stale_review_and_out_of_bounds_ranges_rejected(self):
        with workspace() as root:
            path = root / "original.mp4"
            good = {"sha256": "abc", "local_path": "original.mp4", "segments": [
                {"in_seconds": 1, "out_seconds": 10, "observation": "Observed", "event_ids": ["E01"]}]}
            self.assertEqual(catalog.review_ranges(good, "abc", 10, path)[0],
                             {"in": 1, "out": 10, "observation": "Observed", "event_ids": ["E01"]})
            for change in ({"sha256": "stale"}, {"original_sha256": "stale"},
                           {"segments": [{"in_seconds": 0, "out_seconds": 10.01}]},
                           {"segments": [{"in_seconds": -1, "out_seconds": 1}]},
                           {"local_path": "../escape.mp4"}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    catalog.review_ranges({**good, **change}, "abc", 10, path)

    def test_valid_cache_hits_preserve_review_and_skip_ffmpeg(self):
        with workspace(BASE_CONFIG) as root:
            original = root / "research/media/downloads/original.mp4"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"original fixture")
            sha = core.digest(original)
            asset_id = "asset-" + sha[:16]
            self.seed_cache(root / "media/proxies" / (asset_id + ".mp4"), sha, catalog.PROXY_RECIPE)
            self.seed_cache(root / "media/contact_sheets" / (asset_id + ".jpg"), sha, catalog.CONTACT_RECIPE)
            core.write_json(root / "research/media/sources.json", [{"id": "source-1", "title": "Qualifying",
                "url": "https://example.invalid/clip", "local_path": str(original.relative_to(root)), "sha256": sha}])
            core.write_json(root / "research/media/clip_review.json", {"event_id": BASE_CONFIG["id"], "reviews": [
                {"source_id": "source-1", "sha256": sha, "review_method": "Fixture", "segments": [
                    {"in_seconds": 2, "out_seconds": 5, "label": "qualifying_run"}]}]})
            info = {"format": {"duration": "10"}, "streams": [{"codec_type": "video", "width": 640, "height": 360, "codec_name": "h264"}]}
            with patch.object(catalog, "probe", return_value=info), patch.object(catalog, "run") as run, patch.object(catalog, "log"), redirect_stdout(io.StringIO()):
                result = catalog.catalog()
            run.assert_not_called()
            asset = result["assets"][0]
            self.assertEqual(asset["reviewed_ranges"], [{"in": 2, "out": 5, "label": "qualifying_run"}])
            self.assertEqual(asset["original_sha256"], sha)
            self.assertEqual(asset["review_receipt_sha256"], core.digest(root / "research/media/clip_review.json"))


if __name__ == "__main__":
    unittest.main()
