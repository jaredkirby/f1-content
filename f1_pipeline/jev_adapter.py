#!/usr/bin/env python3
"""Credential-required adapter for TypeSafe Jev; no inferred or mock fallback.

Contract checked 2026-10-10 against https://docs.typesafe.ai/api.
Only the official HTTPS endpoint is used; redirects are refused.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
MAX_REQUEST_BYTES = 131072  # Local resource cap, not a model token estimate.
MAX_RESPONSE_BYTES = 2_000_000


class JevError(Exception):
    """A failed operation. No model results should be reported from it."""


def encode(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise JevError("Input must be finite JSON data") from exc


def number(value, low, high):
    return (type(value) in (int, float) and math.isfinite(value)
            and low <= value <= high)


def validate_request(payload, *, model=MODEL):
    if not isinstance(payload, dict) or set(payload) != {"model", "state", "questions"}:
        raise JevError("Request must contain exactly model, state, questions")
    if payload["model"] != model:
        raise JevError("This evaluated adapter pins model " + model)
    if not isinstance(payload["state"], (str, dict, list)) or not payload["state"]:
        raise JevError("state must be a nonempty text, object, or array")
    questions = payload["questions"]
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 64:
        raise JevError("Local request limit is 1 to 64 questions")
    for name, question in questions.items():
        if not isinstance(name, str) or not name or not isinstance(question, dict):
            raise JevError("Each question needs a string id and an object")
        if set(question) - {"type", "instructions", "criteria"}:
            raise JevError("Unsupported question field: " + name)
        if not isinstance(question.get("instructions"), (str, dict, list)) or not question["instructions"]:
            raise JevError("Missing question instructions: " + name)
        kind = question.get("type")
        criteria = question.get("criteria")
        if kind == "choice":
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 255:
                raise JevError("Choice needs 2 to 255 options: " + name)
            if any(not isinstance(k, str) or not k for k in criteria):
                raise JevError("Choice option keys must be nonempty strings")
            if any(v is not None and not isinstance(v, (str, dict, list)) for v in criteria.values()):
                raise JevError("Choice rubric descriptions must be text or structured data")
        elif kind == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise JevError("Score needs 2 to 10 levels: " + name)
            if any(not isinstance(v, (str, dict, list)) for v in criteria):
                raise JevError("Score rubric descriptions must be text or structured data")
        elif kind == "noul":
            if criteria is not None and (not isinstance(criteria, dict)
                    or set(criteria) - {"true", "false"}
                    or any(not isinstance(v, (str, dict, list)) for v in criteria.values())):
                raise JevError("Noul criteria can only describe true and false")
        else:
            raise JevError("Unsupported question type: " + name)
    body = encode(payload)
    if len(body) > MAX_REQUEST_BYTES:
        raise JevError("Request exceeds local byte limit; split evidence into smaller records")
    return body


def validate_response(response, payload, *, allowed_models=None):
    if (not isinstance(response, dict) or not isinstance(response.get('model'), str)
            or response['model'] not in (allowed_models or {payload['model']})):
        raise JevError("Missing or unexpected provider model identity")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(payload["questions"]):
        raise JevError("Response question ids do not match the request")
    usage = response.get("usage")
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                        for k in ("input_tokens", "output_tokens")):
        raise JevError("Missing or invalid provider token usage")
    for name, question in payload["questions"].items():
        answer = answers[name]
        kind = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise JevError("Answer type mismatch: " + name)
        if kind == "noul":
            if not number(answer.get("noul"), 0, 1):
                raise JevError("Invalid noul probability: " + name)
            continue
        labels = (set(question["criteria"]) if kind == "choice"
                  else {str(i) for i in range(len(question["criteria"]))})
        probabilities = answer.get("probabilities")
        if (not isinstance(probabilities, dict) or set(probabilities) != labels
                or not all(number(p, 0, 1) for p in probabilities.values())
                or not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-5)):
            raise JevError("Invalid probability distribution: " + name)
        if not number(answer.get("confidence"), 0, 1):
            raise JevError("Invalid confidence: " + name)
        if kind == "choice":
            choice = answer.get("choice")
            if not isinstance(choice, str) or choice not in labels:
                raise JevError("Returned choice outside declared options: " + name)
            if probabilities[choice] + 1e-5 < max(probabilities.values()):
                raise JevError("Chosen option is not a maximum: " + name)
        else:
            legend = answer.get("legend")
            if not isinstance(legend, dict) or set(legend) != labels:
                raise JevError("Score legend does not match declared levels: " + name)
            expected = sum(int(k) * v for k, v in probabilities.items())
            if (not number(answer.get("score"), 0, len(labels) - 1)
                    or not math.isclose(answer["score"], expected, abs_tol=1e-5)):
                raise JevError("Score does not match its probability-weighted levels: " + name)
    return response


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise JevError("Redirect refused; credential is restricted to the official endpoint")


def evaluate(payload, *, timeout=20):
    body = validate_request(payload)
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise JevError("TYPESAFE_API_KEY is missing; actual Jev inference was not run")
    if "\n" in key or "\r" in key:
        raise JevError("Invalid credential format")
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "f1-content-jev/1.0",
    })
    start = time.monotonic()
    # No retry after ambiguous network failure: avoid duplicate charge assumptions.
    # Retry only explicit throttling/overload; at most three attempts, bounded delay.
    for attempt in range(3):
        try:
            with opener.open(request, timeout=timeout) as result:
                raw = result.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise JevError("Provider response exceeds the local limit")
            try:
                response = json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise JevError("Provider returned invalid JSON") from exc
            validate_response(response, payload)
            return {"schema_version": "f1.jev.evaluation.v1", "backend": "typesafe_jev",
                    "actual_model_inference": True, "endpoint": ENDPOINT,
                    "requested_model": payload["model"], "response": response,
                    "request_sha256": hashlib.sha256(body).hexdigest(),
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "elapsed_seconds": round(time.monotonic() - start, 4),
                    "attempts": attempt + 1}
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 529) and attempt < 2:
                delay = 2 ** attempt
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        raise JevError("Provider requested deferred retry; rerun later") from None
                if not math.isfinite(delay) or not 0 <= delay <= 8:
                    raise JevError("Provider requested deferred retry; rerun later") from None
                time.sleep(delay)
                continue
            # Never echo provider bodies or exceptions that might contain input.
            raise JevError("Provider HTTP error " + str(exc.code) + "; no accepted result") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise JevError("Provider connection failed; no accepted result (" + type(exc).__name__ + ")") from None
    raise JevError("Provider retry limit reached")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="Check credential presence, never its value")
    parser.add_argument("--request", type=Path, help="JSON request containing model/state/questions")
    parser.add_argument("--output", type=Path, help="Write result receipt (must not exist)")
    parser.add_argument("--validate-only", action="store_true", help="Validate request locally without inference")
    args = parser.parse_args(argv)
    try:
        if args.status:
            out = {"backend": "typesafe_jev", "endpoint": ENDPOINT, "model": MODEL,
                   "credential_present": bool(os.environ.get("TYPESAFE_API_KEY", "").strip()),
                   "inference_attempted": False}
        else:
            if not args.request:
                parser.error("--request or --status is required")
            if args.output and args.output.exists():
                raise JevError("Output already exists; choose a new receipt path")
            if args.request.stat().st_size > MAX_REQUEST_BYTES:
                raise JevError("Request file exceeds the local byte limit")
            payload = json.loads(args.request.read_text())
            body = validate_request(payload)
            if args.validate_only:
                out = {"valid": True, "inference_attempted": False,
                       "request_sha256": hashlib.sha256(body).hexdigest()}
            else:
                out = evaluate(payload)
        rendered = json.dumps(out, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x") as output:
                output.write(rendered)
        else:
            print(rendered, end="")
        return 0
    except (JevError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "accepted_model_result": False,
                          "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
