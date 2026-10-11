"""Explicit human review of the selected output set; technical release stays separate.

The private ledger detects accidental edits through a hash chain. It is not human
authentication, and cannot prevent a writer from replacing an entire ledger.
Corrections apply to the current output set only; historical rows remain intact.
"""
from __future__ import annotations

import hashlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import uuid

from .core import ROOT, digest, now, read_json, safe_relative, validate_config, write_json
from .validate import legacy_release

LEDGER = "runs/feedback.jsonl"
IDENTITY_FIELDS = ("id", "year", "country_name", "session_name", "event_date", "session_key", "meeting_key")
COMPANIONS = ("captions", "script", "thumbnail")
FEEDBACK_FIELDS = {"event_id", "manifest_sha256", "source", "outcome", "comments", "scope",
                   "model_runs", "preference_version", "correction_of", "comparison_id", "usage"}
PREFERENCE_FIELDS = {"event_id", "source", "key", "instruction", "scope", "source_feedback_ids"}


def _text(value, label, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError("Invalid " + label)
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Invalid SHA-256 binding")
    return value


def _source(value):
    if not isinstance(value, dict) or set(value) != {"kind", "reviewer", "reference"} or value["kind"] != "human":
        raise ValueError("An explicit human source is required")
    _text(value["reviewer"], "human reviewer")
    _text(value["reference"], "human source reference")


def _feedback_input(payload, event):
    if not isinstance(payload, dict) or set(payload) - FEEDBACK_FIELDS:
        raise ValueError("Unknown human feedback fields")
    if payload.get("event_id") != event["id"]:
        raise ValueError("Human feedback event identity mismatch")
    _source(payload.get("source"))
    if payload.get("outcome") not in ("approved", "rejected", "not_reviewed"):
        raise ValueError("Invalid human outcome")
    _text(payload.get("comments"), "verbatim comments", empty=True)
    sha = _hash(payload.get("manifest_sha256"))
    if payload.get("scope") != {"kind": "output", "target": sha}:
        raise ValueError("Feedback scope must identify the observed output manifest")
    for key in ("comparison_id", "correction_of", "preference_version"):
        if payload.get(key) is not None:
            _text(payload[key], key)
    usage = payload.get("usage", {})
    if not isinstance(usage, dict) or set(usage) - {"device", "observed_segment", "revision_minutes"}:
        raise ValueError("Invalid explicit usage context")
    for key in ("device", "observed_segment"):
        if usage.get(key) is not None:
            _text(usage[key], key)
    minutes = usage.get("revision_minutes")
    if minutes is not None and (type(minutes) not in (int, float) or not math.isfinite(minutes) or minutes < 0):
        raise ValueError("Revision minutes must be finite and nonnegative")


def _preference_input(payload, event):
    if not isinstance(payload, dict) or set(payload) - PREFERENCE_FIELDS:
        raise ValueError("Unknown preference fields")
    if payload.get("event_id") != event["id"]:
        raise ValueError("Preference event identity mismatch")
    _source(payload.get("source"))
    key = _text(payload.get("key"), "preference key")
    if not re.fullmatch("[a-z][a-z0-9_.-]{0,99}", key):
        raise ValueError("Preference key must be a stable lowercase identifier")
    _text(payload.get("instruction"), "verbatim preference instruction")
    scope = payload.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"kind", "target"}:
        raise ValueError("An explicit preference scope is required")
    target = _text(scope["target"], "preference scope target")
    kind = scope["kind"]
    if kind not in ("project", "event", "format", "output"):
        raise ValueError("Invalid preference scope")
    if kind == "event" and target != event["id"]:
        raise ValueError("Preference scope event mismatch")
    if kind == "format" and target not in ("vertical", "landscape"):
        raise ValueError("Invalid preference format")
    if kind == "output":
        _hash(target)
    ids = payload.get("source_feedback_ids", [])
    if not isinstance(ids, list) or any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Preference sources must be explicit human feedback IDs")


def _preference_view(history, event):
    preferences = [row for row in history if row["kind"] == "preference"]
    current = {}
    for record in preferences:
        current[(record["key"], record["scope"]["kind"], record["scope"]["target"])] = record
    return {"schema_version": 1, "event_id": event["id"],
            "version": preferences[-1]["id"] if preferences else None,
            "confirmed": list(current.values()), "history": preferences, "pending": []}


def _workspace(root):
    return Path(ROOT if root is None else root).resolve()


def _event(root):
    config = validate_config(read_json(safe_relative("config/event.json", root=root)), root=root)
    return {key: config[key] for key in IDENTITY_FIELDS}


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _relative(value, root, prefix):
    _text(value, "relative workspace path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value or not value.startswith(prefix):
        raise ValueError("Invalid relative workspace path: " + value)
    return safe_relative(value, root=root)


def _manifest_outputs(manifest, root, event, observed=None):
    if not isinstance(manifest, dict) or manifest.get("event_id") != event["id"]:
        raise ValueError("Output manifest event identity mismatch")
    videos = manifest.get("videos")
    if not isinstance(videos, list) or not videos or any(not isinstance(video, dict) for video in videos):
        raise ValueError("Output manifest requires videos")
    formats = [video.get("format") for video in videos]
    if any(value not in ("vertical", "landscape") for value in formats) or len(set(formats)) != len(formats):
        raise ValueError("Output manifest has invalid or duplicate formats")
    legacy = legacy_release(manifest, event_config=event)
    outputs = {}

    def add(relative, sha, required=True):
        path = _relative(relative, root, "outputs/" if legacy else "outputs/versions/")
        if sha is None and legacy and not required:
            sha = observed.get(relative) if observed is not None else digest(path)
        _hash(sha)
        if relative in outputs and outputs[relative] != sha:
            raise ValueError("Conflicting output hashes: " + relative)
        outputs[relative] = sha

    add(manifest.get("edit_plan", "outputs/edit-plan.json"), manifest.get("edit_plan_sha256"), required=False)
    for video in videos:
        add(video.get("path"), video.get("sha256"))
        companions = video.get("companion_sha256", {})
        if not isinstance(companions, dict) or (not legacy and set(companions) != set(COMPANIONS)):
            raise ValueError("Required companion hash bindings missing")
        for key in COMPANIONS:
            add(video.get(key), companions.get(key), required=False)
    return outputs, legacy


def _binding(root):
    raw = safe_relative("outputs/manifest.json", root=root).read_bytes().decode("utf-8")
    outputs, legacy = _manifest_outputs(json.loads(raw), root, _event(root))
    for relative, sha in outputs.items():
        path = safe_relative(relative, root=root)
        if not path.is_file() or digest(path) != sha:
            raise ValueError("Output file is missing or changed: " + relative)
    return {"manifest_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "manifest_snapshot": raw, "output_hashes": outputs, "legacy_observed_bindings": legacy}


def _model_runs(value, root, event, verify=True):
    if not isinstance(value, list):
        raise ValueError("Model attribution must use receipt path/hash links")
    seen = set()
    for link in value:
        if not isinstance(link, dict) or set(link) != {"path", "sha256"}:
            raise ValueError("Malformed model receipt link")
        path = _relative(link["path"], root, "runs/model-evaluations/")
        _hash(link["sha256"])
        if path.suffix != ".json" or link["path"] in seen:
            raise ValueError("Invalid or duplicate model receipt path")
        seen.add(link["path"])
        if verify:
            if not path.is_file() or digest(path) != link["sha256"]:
                raise ValueError("Model receipt is missing or changed: " + link["path"])
            receipt = read_json(path)
            if not isinstance(receipt, dict) or receipt.get("event_id") != event["id"]:
                raise ValueError("Model receipt event identity mismatch")
            if "event_identity" in receipt and receipt["event_identity"] != event:
                raise ValueError("Model receipt pinned identity mismatch")


def _read_history(raw, root):
    if raw and not raw.endswith("\n"):
        raise ValueError("Feedback ledger has an incomplete final record")
    event = _event(root)
    records = []
    seen = set()
    previous = None
    for line in raw.splitlines():
        record = json.loads(line)
        if (not isinstance(record, dict) or type(record.get("schema_version")) is not int
                or record["schema_version"] != 1):
            raise ValueError("Invalid feedback ledger schema")
        if not isinstance(record.get("id"), str) or not record["id"] or record["id"] in seen:
            raise ValueError("Invalid or duplicate feedback record ID")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        if record.get("previous_record_sha256") != previous or record.get("record_sha256") != _sha(unsigned):
            raise ValueError("Feedback ledger integrity failure")
        if record.get("event_id") != event["id"] or record.get("event_identity") != event:
            raise ValueError("Feedback ledger event identity mismatch")
        if record.get("kind") == "feedback":
            _feedback_input({key: record[key] for key in FEEDBACK_FIELDS if key in record}, event)
            _model_runs(record.get("model_runs", []), root, event, verify=False)
            _correction(record.get("correction_of"), records, record)
            if record.get("preference_version") != _preference_view(records, event)["version"]:
                raise ValueError("Feedback preference snapshot does not match its recorded version")
            snapshot = record.get("manifest_snapshot")
            _text(snapshot, "manifest snapshot")
            if hashlib.sha256(snapshot.encode()).hexdigest() != record["manifest_sha256"]:
                raise ValueError("Feedback manifest snapshot changed")
            outputs, legacy = _manifest_outputs(json.loads(snapshot), root, event, observed=record.get("output_hashes", {}))
            if outputs != record.get("output_hashes") or legacy != record.get("legacy_observed_bindings"):
                raise ValueError("Feedback output binding does not match its manifest snapshot")
        elif record.get("kind") == "preference":
            _preference_input({key: record[key] for key in PREFERENCE_FIELDS if key in record}, event)
            _preference_sources(record.get("source_feedback_ids", []), records)
        else:
            raise ValueError("Invalid feedback record kind")
        records.append(record)
        seen.add(record["id"])
        previous = record["record_sha256"]
    return records


def read_feedback(root=None):
    """Verify and read immutable history without requiring historical files to exist."""
    root = _workspace(root)
    path = safe_relative(LEDGER, root=root)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        return _read_history(stream.read(), root)


def _append(record, history, root):
    path = safe_relative(LEDGER, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        current = _read_history(stream.read(), root)
        if current != history:
            raise ValueError("Feedback ledger changed during capture; review and retry")
        record["previous_record_sha256"] = history[-1]["record_sha256"] if history else None
        record["record_sha256"] = _sha(record)
        stream.seek(0, os.SEEK_END)
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return record


def _correction(value, history, binding):
    if value is None:
        return
    target = next((row for row in history if row["id"] == value and row["kind"] == "feedback"), None)
    if target is None:
        raise ValueError("Correction refers to missing human feedback")
    if any(target[key] != binding[key] for key in ("manifest_sha256", "output_hashes")):
        raise ValueError("Historical corrections require the same current output binding")


def _preference_sources(ids, history):
    available = {row["id"] for row in history if row["kind"] == "feedback"}
    if set(ids) - available:
        raise ValueError("Preference references missing human feedback")


def preference_status(root=None):
    """Return confirmed human instructions and their immutable append-only versions."""
    root = _workspace(root)
    return _preference_view(read_feedback(root), _event(root))


def record_preference(payload, root=None):
    """Capture an explicitly requested human preference; never infer taste from use."""
    root = _workspace(root)
    event = _event(root)
    _preference_input(payload, event)
    history = read_feedback(root)
    ids = payload.get("source_feedback_ids", [])
    _preference_sources(ids, history)
    if payload["scope"]["kind"] == "output" and payload["scope"]["target"] != _binding(root)["manifest_sha256"]:
        raise ValueError("Output preference scope does not match the current manifest")
    record = {**payload, "schema_version": 1, "kind": "preference",
              "id": "preference-" + uuid.uuid4().hex, "at": now(),
              "event_identity": event, "source_feedback_ids": ids}
    _append(record, history, root)
    write_json(safe_relative("research/event/preferences.json", root=root), preference_status(root))
    return record


def record_feedback(payload, root=None):
    """Append one explicitly sourced human decision for the exact current manifest."""
    root = _workspace(root)
    event = _event(root)
    _feedback_input(payload, event)
    binding = _binding(root)
    if payload.get("manifest_sha256") != binding["manifest_sha256"]:
        raise ValueError("Observed manifest changed before human feedback capture")
    history = read_feedback(root)
    _correction(payload.get("correction_of"), history, binding)
    _model_runs(payload.get("model_runs", []), root, event)
    preference_version = _preference_view(history, event)["version"]
    if "preference_version" in payload and payload["preference_version"] != preference_version:
        raise ValueError("Observed preference version is stale or unknown")
    record = {**payload, **binding, "schema_version": 1, "kind": "feedback",
              "id": "feedback-" + uuid.uuid4().hex, "at": now(), "event_identity": event,
              "model_runs": payload.get("model_runs", []),
              "preference_version": preference_version,
              "correction_of": payload.get("correction_of")}
    _append(record, history, root)
    feedback_status(root, write_view=True)
    return record


def feedback_status(root=None, write_view=False):
    """Derive current human acceptance; no record means not reviewed."""
    root = _workspace(root)
    event = _event(root)
    result = {"schema_version": 1, "event_id": event["id"], "status": "not_reviewed",
              "feedback_id": None, "errors": [], "manifest_sha256": None,
              "output_hashes": {}, "model_runs": [], "preference_version": None,
              "ledger_valid": True, "binding_valid": False}
    history = []
    binding = None
    try:
        history = read_feedback(root)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result["ledger_valid"] = False
        result["errors"].append(str(exc))
    try:
        binding = _binding(root)
        result.update(binding_valid=True, manifest_sha256=binding["manifest_sha256"],
                      output_hashes=binding["output_hashes"])
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result["errors"].append(str(exc))
    matches = [] if binding is None or not result["ledger_valid"] else [
        record for record in history if record["kind"] == "feedback"
               and record["manifest_sha256"] == binding["manifest_sha256"]
               and record["output_hashes"] == binding["output_hashes"]]
    latest = matches[-1] if matches else None
    if latest:
        try:
            _model_runs(latest["model_runs"], root, event)
        except (ValueError, OSError) as exc:
            result["errors"].append(str(exc))
            latest = None
    if latest:
        result.update(status=latest["outcome"], feedback_id=latest["id"],
                      model_runs=latest["model_runs"], preference_version=latest["preference_version"])
    current_ids = {record["id"] for record in matches}
    result["stale_feedback_ids"] = [record["id"] for record in history
                                    if record["kind"] == "feedback" and record["id"] not in current_ids]
    if write_view:
        write_json(safe_relative("outputs/human-feedback.json", root=root), result)
    return result
