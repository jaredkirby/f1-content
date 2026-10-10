"""Regression gates from the independent review; no network or real media used.

The tests require integrity gates identified in review. Temporary fixtures
never touch run data.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import f1_pipeline.catalog as catalog_module
import f1_pipeline.analyze as analyze_module


def put(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class ReviewGates(unittest.TestCase):
    def catalog_fixture(self, root, source_hash):
        original = root / "research/media/downloads/clip.mp4"
        original.parent.mkdir(parents=True)
        original.write_bytes(b"synthetic original fixture")
        actual_hash = hashlib.sha256(original.read_bytes()).hexdigest()
        for relative in (f"media/proxies/asset-{actual_hash[:16]}.mp4",
                         f"media/contact_sheets/asset-{actual_hash[:16]}.jpg"):
            p = root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"synthetic cached derivative")
        put(root, "research/media/sources.json", [{
            "id": "source-1", "title": "Fixture", "url": "https://example.invalid/clip",
            "local_path": str(original.relative_to(root)),
            "sha256": source_hash or actual_hash,
            "download_status": "downloaded", "categories": []}])
        return original

    def test_catalog_rejects_source_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.catalog_fixture(root, "0" * 64)
            info = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 640, "height": 360}],
                    "format": {"duration": "10.0"}}
            with patch.object(catalog_module, "ROOT", root), \
                 patch.object(catalog_module, "safe_relative", side_effect=lambda p: root / p), \
                 patch.object(catalog_module, "config", return_value={"id": "fixture", "media_budget_bytes": 1000000}), \
                 patch.object(catalog_module, "probe", return_value=info), \
                 patch.object(catalog_module, "ensure_space"), \
                 patch.object(catalog_module, "run"), patch.object(catalog_module, "log"):
                with self.assertRaises((ValueError, RuntimeError)):
                    catalog_module.catalog()

    def test_catalog_does_not_accept_invalid_cached_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = self.catalog_fixture(root, None)
            info = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 640, "height": 360}],
                    "format": {"duration": "10.0"}}

            def fake_probe(path):
                if Path(path) == original:
                    return info
                raise RuntimeError("Synthetic corrupt derivative")

            with patch.object(catalog_module, "ROOT", root), \
                 patch.object(catalog_module, "safe_relative", side_effect=lambda p: root / p), \
                 patch.object(catalog_module, "config", return_value={"id": "fixture", "media_budget_bytes": 1000000}), \
                 patch.object(catalog_module, "probe", side_effect=fake_probe), \
                 patch.object(catalog_module, "ensure_space"), \
                 patch.object(catalog_module, "run") as run, patch.object(catalog_module, "log"):
                try:
                    catalog_module.catalog()
                except (ValueError, RuntimeError):
                    return  # Explicit rejection is acceptable.
                self.assertTrue(run.called, "Corrupt existing proxy was silently accepted without validation/regeneration")

    def test_analysis_rejects_cross_session_raw_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            official = {"driver_number": 3, "position": 1, "classified": True,
                        "laps_completed": 20, "points": 8, "status": "Finished", "gap_seconds": 0}
            bundle = {"event": {"id": "fixture", "session_key": 11383}, "results": [official],
                      "timeline": [], "assets": [], "ranked_ideas": [], "sources": [],
                      "derived_facts": [], "conflicts": [], "unknowns": []}
            put(root, "research/event/event_bundle.json", bundle)
            put(root, "data/processed/catalog.json", {"event_id": "fixture", "sources": [], "assets": []})
            put(root, "data/processed/data_manifest.json", {
                "event_id": "fixture", "session": {"session_key": 11383}, "receipts": [],
                "failures": [{"endpoint": "session_result", "error": "Cross-session record"}]})
            put(root, "data/raw/openf1/session_result.json", [{
                "driver_number": 3, "session_key": 99999, "position": 1,
                "number_of_laps": 20, "points": 8, "dnf": False, "gap_to_leader": 0}])
            for name in ("drivers", "laps", "weather", "pit"):
                put(root, f"data/raw/openf1/{name}.json", [])
            with patch.object(analyze_module, "ROOT", root), \
                 patch.object(analyze_module, "config", return_value={"id": "fixture", "session_key": 11383, "event_date": "2026-10-10"}), \
                 patch.object(analyze_module, "log"):
                with self.assertRaises((ValueError, RuntimeError)):
                    analyze_module.analyze()

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Use bundled Python with Pillow for render gate")
    def test_render_rejects_stale_editorial_before_rendering(self):
        from f1_pipeline import render as render_module
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            put(root, "data/processed/editorial.json", {"event": {"id": "wrong-event"}})
            put(root, "data/processed/catalog.json", {"event_id": "2026-singapore-sprint", "sources": [], "assets": []})
            with patch.object(render_module, "ROOT", root), \
                 patch.object(render_module, "config", return_value={"id": "2026-singapore-sprint"}), \
                 patch.object(render_module, "render_one", return_value=({"format": "vertical"}, [])) as render_one, \
                 patch.object(render_module, "log"):
                with self.assertRaises((ValueError, RuntimeError)):
                    render_module.render("vertical")
                render_one.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Use bundled Python with Pillow for render gate")
    def test_render_rejects_manifest_from_another_event(self):
        from f1_pipeline import render as render_module
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            put(root, "data/processed/editorial.json", {"event": {"id": "2026-singapore-sprint"}})
            put(root, "data/processed/catalog.json", {"event_id": "2026-singapore-sprint", "sources": [], "assets": []})
            put(root, "outputs/manifest.json", {"event_id": "wrong-event", "videos": []})
            with patch.object(render_module, "ROOT", root), \
                 patch.object(render_module, "config", return_value={"id": "2026-singapore-sprint"}), \
                 patch.object(render_module, "render_one", return_value=({"format": "vertical"}, [])) as render_one, \
                 patch.object(render_module, "log"):
                with self.assertRaises((ValueError, RuntimeError)):
                    render_module.render("vertical")
                render_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
