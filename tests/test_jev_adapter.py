"""Offline contract/transport tests. Synthetic outputs are never inference evidence."""
import copy
import io
import json
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
from f1_pipeline import jev_adapter as adapter


REQUEST = {"model": adapter.MODEL, "state": "Synthetic test only", "questions": {
    "kind": {"type": "choice", "instructions": "Choose type", "criteria": {"a": "A", "b": "B"}},
    "impact": {"type": "score", "instructions": "Rate impact", "criteria": ["Low", "High"]},
    "support": {"type": "noul", "instructions": "Evidence supports this?"}}}
RESPONSE = {"model": adapter.MODEL, "usage": {"input_tokens": 20, "output_tokens": 8}, "answers": {
    "kind": {"type": "choice", "choice": "a", "probabilities": {"a": 0.9, "b": 0.1}, "confidence": 0.6},
    "impact": {"type": "score", "score": 0.8, "legend": {"0": "Low", "1": "High"},
               "probabilities": {"0": 0.2, "1": 0.8}, "confidence": 0.3},
    "support": {"type": "noul", "noul": 0.85}}}


class AdapterTests(unittest.TestCase):
    def test_request_and_response_contract(self):
        self.assertTrue(adapter.validate_request(REQUEST))
        self.assertIs(adapter.validate_response(RESPONSE, REQUEST), RESPONSE)

    def test_missing_key_never_opens_network(self):
        with patch.dict("os.environ", {}, clear=True), patch("urllib.request.build_opener") as opener:
            with self.assertRaisesRegex(adapter.JevError, "missing"):
                adapter.evaluate(REQUEST)
            opener.assert_not_called()

    def test_invalid_options_and_nans_rejected(self):
        for mutate in (
            lambda r: r["answers"]["kind"].update(choice="invented"),
            lambda r: r["answers"]["kind"]["probabilities"].update(a=0.8),
            lambda r: r["answers"]["kind"].update(choice="b"),
            lambda r: r["answers"]["impact"].update(score=0.1),
            lambda r: r["answers"]["support"].update(noul=float("nan")),
            lambda r: r["answers"]["support"].update(noul=True),
            lambda r: r["answers"].pop("kind"),
            lambda r: r.update(model="other-model"),
            lambda r: r["usage"].update(input_tokens=-1),
            lambda r: r["answers"]["impact"].update(legend={"0": "Low"}),
        ):
            with self.subTest(mutation=mutate):
                r = copy.deepcopy(RESPONSE)
                mutate(r)
                with self.assertRaises(adapter.JevError):
                    adapter.validate_response(r, REQUEST)

    def test_invalid_request_rejected(self):
        for mutate in (
            lambda r: r.update(model="jev-latest"),
            lambda r: r.update(state=float("nan")),
            lambda r: r["questions"]["kind"].update(criteria={"only": "One"}),
            lambda r: r["questions"]["impact"].update(criteria=["one"]),
            lambda r: r["questions"]["support"].update(criteria={"perhaps": "Invalid"}),
            lambda r: r.update(state="x" * adapter.MAX_REQUEST_BYTES),
        ):
            r = copy.deepcopy(REQUEST)
            mutate(r)
            with self.assertRaises(adapter.JevError):
                adapter.validate_request(r)

    def test_redirect_rejected(self):
        with self.assertRaisesRegex(adapter.JevError, "Redirect refused"):
            adapter.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")

    def test_mock_transport_receipt(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(RESPONSE).encode()
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-only"}), patch("urllib.request.build_opener", return_value=opener):
            receipt = adapter.evaluate(REQUEST)
        self.assertEqual(receipt["response"], RESPONSE)
        self.assertEqual(receipt["requested_model"], adapter.MODEL)
        request = opener.open.call_args[0][0]
        self.assertEqual(request.full_url, adapter.ENDPOINT)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-only")
        self.assertNotIn("test-only", json.dumps(receipt))

    def test_unauthorized_not_retried_or_logged(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(adapter.ENDPOINT, 401, "SECRET", {}, io.BytesIO(b"SECRET"))
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-only"}), patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(adapter.JevError, "HTTP error 401") as ctx:
                adapter.evaluate(REQUEST)
        self.assertEqual(opener.open.call_count, 1)
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_explicit_overload_retries_bounded(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(adapter.ENDPOINT, 529, "", {"Retry-After": "0"}, None)
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-only"}), patch("urllib.request.build_opener", return_value=opener), patch("time.sleep") as sleeper:
            with self.assertRaisesRegex(adapter.JevError, "529"):
                adapter.evaluate(REQUEST)
        self.assertEqual(opener.open.call_count, 3)
        self.assertEqual(sleeper.call_count, 2)

    def test_long_retry_after_defers_without_sleep(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(adapter.ENDPOINT, 429, "", {"Retry-After": "120"}, None)
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-only"}), patch("urllib.request.build_opener", return_value=opener), patch("time.sleep") as sleeper:
            with self.assertRaisesRegex(adapter.JevError, "deferred retry"):
                adapter.evaluate(REQUEST)
        sleeper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
