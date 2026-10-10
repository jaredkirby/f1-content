import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from collections import namedtuple
from f1_pipeline.core import ensure_space, public_url, safe_relative, write_json, read_json
from f1_pipeline.catalog import labels, sources_list

class GuardTests(unittest.TestCase):
    def test_disk_reserve_includes_expected_write(self):
        usage = namedtuple("usage", "total used free")(1000, 700, 300)
        with patch("f1_pipeline.core.shutil.disk_usage", return_value=usage):
            ensure_space(100, reserve=200)
            with self.assertRaises(RuntimeError):
                ensure_space(101, reserve=200)

    def test_disallow_local_and_credential_urls(self):
        for url in ("file:///etc/passwd", "http://example.com", "https://user:pass@example.com", "https://example.com:8080"):
            with self.assertRaises(ValueError):
                public_url(url)
        with patch("f1_pipeline.core.socket.getaddrinfo", return_value=[(None,None,None,None,("127.0.0.1",443))]):
            with self.assertRaises(ValueError):
                public_url("https://local.example")

    def test_asset_paths_do_not_escape(self):
        with self.assertRaises(ValueError):
            safe_relative("../../etc/passwd")

    def test_labels_are_multi_label(self):
        self.assertEqual(set(labels("Rain: opening lap collision")), {"weather", "race_start", "incident"})
        self.assertEqual(labels("Driver training"), ["context"])

    def test_reject_malformed_source_inventory(self):
        with self.assertRaises(ValueError):
            sources_list({"sources": "not a list"})

    def test_json_atomic_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "manifest.json"
            write_json(p, {"name": "Hülkenberg"})
            self.assertEqual(read_json(p), {"name": "Hülkenberg"})
            self.assertFalse(p.with_suffix(".json.tmp").exists())

if __name__ == "__main__":
    unittest.main()
