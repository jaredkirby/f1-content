"""Offline model-work provenance and human-led quality/efficiency evaluation.

These workflows import observed work; they never launch models, infer a historical
model from defaults, or promote a route. Unknown measurements remain unknown.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re

from .core import ROOT, digest, ensure_space, now, read_json, safe_relative, validate_config

SCHEMA = "f1.model_work.v1"
IDENTITY_KEYS = ("id", "year", "country_name", "session_name", "event_date", "session_key", "meeting_key")
DETERMINISTIC_TASKS = frozenset({"hash_check", "arithmetic", "clip_bounds", "schema_validation",
                               "collect", "catalog", "render", "validate", "finalize", "report", "timeline"})


def route_advice(task, *, subscription_status="available", root=None):
    """Return bounded policy advice; availability is supplied, never probed here."""
    _, _, identity = _workspace(root)
    _slug(task, "task")
    if subscription_status not in {"available", "limited", "unavailable", "unknown"}:
        raise ValueError("subscription_status must be available, limited, unavailable or unknown")
    if task in DETERMINISTIC_TASKS:
        route, reason = "deterministic", "Use local code for this evidence/integrity operation."
    elif subscription_status == "available":
        route, reason = "codex_chatgpt_subscription", "Use the signed-in Codex subscription session as the quality reference."
    else:
        route, reason = "human_decision", "Preserve work; confirm access, wait, or choose an explicitly approved hosted route."
    return {"schema_version": "f1.model_route_advice.v1", "event_id": identity["id"], "task": task,
            "route": route, "reason": reason, "subscription_status": subscription_status,
            "requires_human_decision": route == "human_decision", "provider_calls": False,
            "automatic_promotion": False,
            "human_checkpoints": ["important editorial preferences", "voice changes", "finished output feedback",
                                  "model promotions", "new paid/data-processing scope"]}


def _workspace(root):
    root = Path(ROOT if root is None else root).resolve()
    config = validate_config(read_json(safe_relative("config/event.json", root=root)), root=root)
    return root, config, {key: config[key] for key in IDENTITY_KEYS}


def _slug(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", value):
        raise ValueError("Invalid model-work " + field)


def _bindings(items, root, verify_files, field):
    if not isinstance(items, list):
        raise ValueError(field + " must be a list of path/hash bindings")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("Invalid " + field + " binding")
        path, sha = item["path"], item["sha256"]
        if (not isinstance(path, str) or not path or Path(path).is_absolute()
                or not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha)):
            raise ValueError("Invalid " + field + " path/hash")
        if ".." in Path(path).parts or Path(path).as_posix() != path:
            raise ValueError(field + " requires a canonical relative path")
        target = safe_relative(path, root=root)
        if str(target) in seen:
            raise ValueError("Duplicate " + field + " path")
        seen.add(str(target))
        if verify_files and (not target.is_file() or digest(target) != sha):
            raise ValueError(field + " hash mismatch: " + path)


def _preference_binding(record, root):
    version, binding = record.get("preference_version"), record.get("preference_binding")
    if "preference_version" not in record or "preference_binding" not in record:
        raise ValueError("Missing confirmed preference version/binding; use null if unknown")
    if version is None:
        if binding is not None:
            raise ValueError("Unknown confirmed preference version needs a null binding")
        return
    if (not isinstance(version, str) or not isinstance(binding, dict)
            or set(binding) != {"version", "record_hashes"} or binding["version"] != version
            or not isinstance(binding["record_hashes"], dict)
            or not safe_relative("runs/feedback.jsonl", root=root).is_file()):
        raise ValueError("No matching confirmed preference record binding")
    from .feedback import read_feedback
    latest = {}
    for item in read_feedback(root=root):
        if item["kind"] != "preference":
            continue
        key = (item["key"], json.dumps(item["scope"], sort_keys=True))
        latest[key] = item
        if item["id"] == version:
            expected = {entry["id"]: entry["record_sha256"] for entry in latest.values()}
            if binding["record_hashes"] != expected:
                raise ValueError("Mismatched confirmed preference record hashes")
            return
    raise ValueError("Unknown confirmed preference version")


def validate_model_work(record, *, root=None, verify_files=True):
    """Validate a provider-neutral observed-work record in its pinned workspace."""
    root, _, identity = _workspace(root)
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported model-work schema")
    for field in ("work_id", "comparison_id", "task"):
        _slug(record.get(field), field)
    if record.get("event_id") != identity["id"] or record.get("event_identity") != identity:
        raise ValueError("Model work does not match the selected exact event identity")
    if record.get("format") not in {"vertical", "landscape", "text", "audio"}:
        raise ValueError("Invalid model-work format")
    for field in ("prompt_version", "rubric_version"):
        if field not in record or (record[field] is not None and
                (not isinstance(record[field], str) or not record[field].strip())):
            raise ValueError(field + " must be explicit observed text or null")
    _preference_binding(record, root)
    for field in ("inputs", "evidence"):
        _bindings(record.get(field), root, verify_files, field)
        if not record[field]:
            raise ValueError("Model work requires explicit " + field)
    attempts = record.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("Model work requires every actual attempt")
    attempt_ids = set()
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ValueError("Invalid model-work attempt")
        _slug(attempt.get("attempt_id"), "attempt_id")
        if attempt["attempt_id"] in attempt_ids:
            raise ValueError("Duplicate model-work attempt_id")
        attempt_ids.add(attempt["attempt_id"])
        if attempt.get("status") not in {"completed", "failed", "abstained"}:
            raise ValueError("Invalid model-work attempt status")
        if "error" not in attempt or (attempt["error"] is not None and
                (not isinstance(attempt["error"], str) or not attempt["error"].strip())):
            raise ValueError("Attempt error must be explicit text or null")
        if attempt["status"] == "failed" and attempt["error"] is None:
            raise ValueError("Failed attempt requires its observed error")
        model = attempt.get("model")
        if (not isinstance(model, dict) or model.get("access") not in
                {"chatgpt_subscription", "hosted_api", "deterministic"}
                or model.get("identity_source") not in {"observed", "unknown"}):
            raise ValueError("Observed model access and identity source are required")
        for field in ("provider", "model", "session_reference", "revision", "quantization"):
            if field not in model or (model[field] is not None and
                    (not isinstance(model[field], str) or not model[field].strip())):
                raise ValueError("Model " + field + " must be observed text or null")
        if "settings" not in model or (model["settings"] is not None and not isinstance(model["settings"], dict)):
            raise ValueError("Model settings must be observed object or null")
        _bindings(attempt.get("outputs"), root, verify_files, "outputs")
        if attempt["status"] == "completed" and not attempt["outputs"]:
            raise ValueError("Completed model work needs an actual output")
        _bindings(attempt.get("provenance"), root, verify_files, "provenance")
        eligibility = attempt.get("eligibility")
        if (not isinstance(eligibility, dict) or eligibility.get("status") not in
                {"passed", "failed", "not_reviewed"} or not isinstance(eligibility.get("failures"), list)
                or any(not isinstance(item, str) or not item.strip() for item in eligibility["failures"])):
            raise ValueError("Invalid declared eligibility review")
        if (eligibility["status"] == "passed" and (eligibility["failures"] or attempt["status"] != "completed")
                or eligibility["status"] == "failed" and not eligibility["failures"]):
            raise ValueError("Declared eligibility status contradicts its failures/attempt")
        _bindings(eligibility.get("review_files"), root, verify_files, "eligibility review_files")
        usage = attempt.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("Actual usage and unknown fields must be explicit")
        for field in ("input_tokens", "output_tokens", "reasoning_tokens", "cost_usd", "estimated_cost_usd",
                      "machine_seconds", "human_revision_seconds"):
            if field not in usage:
                raise ValueError("Missing measured/unknown usage field: " + field)
            value = usage[field]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                    or (field.endswith("tokens") and type(value) is not int)):
                raise ValueError("Invalid measured usage: " + field)
        if usage.get("token_scope") not in {"attributable", "account_shared", "unknown"}:
            raise ValueError("Usage token_scope is required")
        if usage.get("cost_source") not in {"provider_receipt", "operator_reported", "unknown"}:
            raise ValueError("Usage cost_source is required")
        if (usage["cost_usd"] is None) != (usage["cost_source"] == "unknown"):
            raise ValueError("Actual cost must have a measured source; unknown is null")
    # JSON serializability is part of the saved receipt contract, including settings.
    json.dumps(record, allow_nan=False)
    return deepcopy(record)


def import_model_work(record_path, *, root=None):
    """Save an immutable receipt for existing local work without invoking a model."""
    root, config, _ = _workspace(root)
    record = validate_model_work(read_json(safe_relative(record_path, root=root)), root=root)
    relative = f"runs/model-evaluations/{record['comparison_id']}/{record['work_id']}.json"
    destination = safe_relative(relative, root=root)
    record["imported_at"] = now()
    encoded = json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ensure_space(len(encoded.encode("utf-8")), root=root, reserve=config["reserve_bytes"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return {"work_id": record["work_id"], "comparison_id": record["comparison_id"],
            "receipt_path": relative, "sha256": digest(destination), "record": record}


def _measurements(attempts, accepted_outputs, incomplete=False):
    usage = [attempt["usage"] for attempt in attempts]
    cost = [item["cost_usd"] for item in usage]
    known_cost = sum(item for item in cost if item is not None)
    missing_cost = sum(item is None for item in cost)
    actual_total = None if missing_cost or incomplete else known_cost
    estimates = [item["estimated_cost_usd"] for item in usage if item["estimated_cost_usd"] is not None]
    result = {"known_actual_cost_usd": known_cost, "unknown_cost_attempts": missing_cost,
              "actual_total_cost_usd": actual_total,
              "cost_per_accepted_output_usd": actual_total / accepted_outputs
              if accepted_outputs and actual_total is not None else None,
              "known_estimated_cost_usd": sum(estimates), "estimated_cost_attempts": len(estimates),
              "account_shared_usage_attempts": sum(item["token_scope"] == "account_shared" for item in usage)}
    for field in ("input_tokens", "output_tokens", "reasoning_tokens", "machine_seconds", "human_revision_seconds"):
        values = [item[field] if not field.endswith("tokens") or item["token_scope"] == "attributable"
                  else None for item in usage]
        unknown = sum(value is None for value in values)
        known = sum(value for value in values if value is not None)
        result["known_" + field] = known
        result["unknown_" + field + "_attempts"] = unknown
        result["total_" + field] = None if unknown or incomplete else known
    return result


def _quality(receipts, root, invalid_paths=()):
    """Resolve human outcomes globally before selecting operator-attributed work.

    A later decision about identical output bytes supersedes the earlier outcome
    even when the human does not repeat its receipt links. Historical explicit
    links remain attribution evidence, rather than a claim about model causality.
    """
    result = {"authority": "explicit human feedback", "human_approved_outputs": 0,
              "human_rejected_outputs": 0, "feedback_count": 0, "comments": [],
              "stale_feedback": [], "approved_manifest_hashes": [], "approved_output_versions": [],
              "receipt_approvals": {}, "output_decisions": []}
    if not safe_relative("runs/feedback.jsonl", root=root).exists():
        return result
    from .feedback import read_feedback
    history = [item for item in read_feedback(root=root) if item["kind"] == "feedback"]
    indexed = {item["path"]: item for item in receipts}
    related = set(indexed) | set(invalid_paths)
    output_history = {}
    for item in history:
        # Legacy manifests omit companion hashes; their observed bindings can differ
        # while the manifest bytes stay identical. Strict manifests already pin them.
        version_key = json.dumps([item["manifest_sha256"], item["output_hashes"]], sort_keys=True)
        output_history.setdefault(version_key, []).append(item)
    selected = {}
    for version_key, rows in output_history.items():
        links = {(link["path"], link["sha256"]) for row in rows for link in row.get("model_runs", [])
                 if link["path"] in related}
        if links:
            selected[version_key] = (rows[-1], [{"path": path, "sha256": sha} for path, sha in sorted(links)])
    for item in history:
        version_key = json.dumps([item["manifest_sha256"], item["output_hashes"]], sort_keys=True)
        if version_key not in selected:
            continue
        result["feedback_count"] += 1
        result["comments"].append({"feedback_id": item["id"], "outcome": item["outcome"],
                                   "comments": item["comments"], "scope": item["scope"],
                                   "source": item["source"], "correction_of": item.get("correction_of"),
                                   "manifest_sha256": item["manifest_sha256"]})
    for version_key, (item, selected_links) in selected.items():
        links = [indexed[link["path"]] for link in selected_links if link["path"] in indexed]
        carried = any(link not in item.get("model_runs", []) for link in selected_links)
        result["output_decisions"].append({"feedback_id": item["id"], "outcome": item["outcome"],
            "manifest_sha256": item["manifest_sha256"], "operator_receipt_links": selected_links,
            "historical_operator_attribution_carried": carried})
        try:
            if len(links) != len(selected_links):
                raise ValueError("Linked model-work receipt is corrupt or invalid")
            _bindings([{"path": path, "sha256": sha} for path, sha in item["output_hashes"].items()],
                      root, True, "reviewed outputs")
            # The latest human decision owns its entire declared binding, even
            # when a requested comparison only carries earlier attribution links.
            _bindings(item.get("model_runs", []), root, True, "latest human decision model_runs")
            for latest_link in item.get("model_runs", []):
                latest_record = read_json(safe_relative(latest_link["path"], root=root))
                validate_model_work(latest_record, root=root)
            _bindings(selected_links, root, True, "reviewed model_runs")
            if not all(link["verified"] for link in links):
                raise ValueError("Model work input/output bindings are stale")
        except (ValueError, OSError) as exc:
            result["stale_feedback"].append({"feedback_id": item["id"], "error": str(exc)})
            continue
        if item["outcome"] == "approved":
            result["human_approved_outputs"] += 1
            result["approved_manifest_hashes"].append(item["manifest_sha256"])
            version_id = hashlib.sha256(version_key.encode()).hexdigest()
            result["approved_output_versions"].append({"version_id": version_id,
                "manifest_sha256": item["manifest_sha256"], "output_hashes": item["output_hashes"]})
            for link in links:
                result["receipt_approvals"].setdefault(link["path"], []).append(version_id)
        elif item["outcome"] == "rejected":
            result["human_rejected_outputs"] += 1
    return result


def _incomplete_executions(directory, comparison_id, root, identity, errors):
    """Retain execution intents lacking a saved work receipt without inventing runs."""
    incomplete = []
    for path in sorted(directory.glob(f"{comparison_id or '*'}/*.assets/intent.json")):
        relative = path.relative_to(root).as_posix()
        work_id = path.parent.name.removesuffix(".assets")
        comparison = path.parent.parent.name
        try:
            _slug(work_id, "work_id")
            _slug(comparison, "comparison_id")
            final = safe_relative(f"runs/model-evaluations/{comparison}/{work_id}.json", root=root)
            if final.exists():
                continue
            intent = read_json(safe_relative(relative, root=root))
            if not isinstance(intent, dict) or intent.get("event_identity") != identity:
                raise ValueError("Incomplete execution intent exact event identity mismatch")
            _slug(intent.get("task"), "task")
            if intent.get("format") not in {"vertical", "landscape", "text", "audio"}:
                raise ValueError("Incomplete execution intent format is invalid")
        except (ValueError, OSError, TypeError) as exc:
            errors.append({"path": relative, "error": str(exc)})
            continue
        item = {"work_id": work_id, "comparison_id": comparison, "task": intent["task"],
                "format": intent["format"], "event_id": identity["id"],
                "intent_path": relative, "intent_sha256": digest(path),
                "status": "incomplete_work_receipt", "intent_status": intent.get("status"),
                "execution_confirmed": None, "errors": [], "artifacts": []}
        for field in ("inputs", "evidence"):
            try:
                _bindings(intent.get(field), root, True, "execution intent " + field)
            except (ValueError, OSError) as exc:
                item["errors"].append(str(exc))
        for filename in ("request.json", "provider-receipt.json", "model-work-import.json", "result.txt"):
            artifact_relative = path.parent.relative_to(root).as_posix() + "/" + filename
            try:
                artifact = safe_relative(artifact_relative, root=root)
                if artifact.is_file():
                    item["artifacts"].append({"path": artifact_relative, "sha256": digest(artifact)})
                    if filename == "provider-receipt.json":
                        item["provider_receipt_observation"] = _provider_observation(read_json(artifact))
            except (ValueError, OSError) as exc:
                item["errors"].append(str(exc))
        incomplete.append(item)
    return incomplete


def _provider_observation(receipt):
    """Expose bounded raw receipt measurements without turning them into work runs."""
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "f1.hosted-inference.v1":
        raise ValueError("Incomplete execution has an invalid raw provider receipt schema")
    observation = {"schema_version": receipt["schema_version"], "usage": None, "cost": None}
    for field in ("provider", "status", "observed_model"):
        value = receipt.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 256):
            raise ValueError("Invalid raw provider receipt " + field)
        observation[field] = value
    for field in ("inference_attempted", "actual_model_inference"):
        value = receipt.get(field)
        if value is not None and type(value) is not bool:
            raise ValueError("Invalid raw provider receipt " + field)
        observation[field] = value
    attempts = receipt.get("attempts")
    if attempts is not None and (type(attempts) is not int or attempts < 0):
        raise ValueError("Invalid raw provider receipt attempts")
    observation["attempts"] = attempts
    usage = receipt.get("usage")
    if usage is not None:
        if not isinstance(usage, dict):
            raise ValueError("Invalid raw provider usage")
        measured = {}
        for field in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "total_tokens"):
            value = usage.get(field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Invalid raw provider usage " + field)
            measured[field] = value
        observation["usage"] = measured
    cost = receipt.get("cost")
    if cost is not None:
        if not isinstance(cost, dict):
            raise ValueError("Invalid raw provider cost")
        measured = {}
        for field in ("provider_estimated_cost_usd", "usage_rate_estimate_usd", "actual_billing_usd"):
            value = cost.get(field)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError("Invalid raw provider cost " + field)
            measured[field] = value
        observation["cost"] = measured
    elapsed = receipt.get("elapsed_seconds")
    if elapsed is not None and (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
        raise ValueError("Invalid raw provider elapsed_seconds")
    observation["elapsed_seconds"] = elapsed
    return observation


def evaluation_report(comparison_id=None, *, root=None):
    """Describe saved observations; human feedback alone supplies subjective quality."""
    root, _, identity = _workspace(root)
    if comparison_id is not None:
        _slug(comparison_id, "comparison_id")
    directory = safe_relative("runs/model-evaluations", root=root)
    receipts, errors, binding_failures = [], [], []
    paths = sorted(directory.glob(f"{comparison_id or '*'}/*.json"))
    for path in paths:
        relative = str(path.relative_to(root))
        try:
            record = validate_model_work(read_json(safe_relative(relative, root=root)), root=root, verify_files=False)
        except (ValueError, OSError, TypeError) as exc:
            errors.append({"path": relative, "error": str(exc)})
            continue
        if comparison_id is not None and record["comparison_id"] != comparison_id:
            errors.append({"path": relative, "error": "Receipt comparison identity mismatch"})
            continue
        try:
            validate_model_work(record, root=root)
            verified = True
        except (ValueError, OSError) as exc:
            verified = False
            binding_failures.append({"path": relative, "error": str(exc)})
        receipts.append({"path": relative, "sha256": digest(path), "record": record, "verified": verified})
    incomplete = _incomplete_executions(directory, comparison_id, root, identity, errors)
    attempts = [attempt for item in receipts for attempt in item["record"]["attempts"]]
    try:
        quality = _quality(receipts, root, [item["path"] for item in errors])
    except (ValueError, OSError, TypeError, KeyError) as exc:
        quality = {"authority": "explicit human feedback", "human_approved_outputs": 0,
                   "human_rejected_outputs": 0, "feedback_count": 0, "comments": [],
                   "errors": [str(exc)]}
    grouped = {}
    for receipt in receipts:
        record = receipt["record"]
        for attempt in record["attempts"]:
            model = {key: attempt["model"][key] for key in
                     ("provider", "model", "access", "identity_source", "settings", "revision", "quantization")}
            key = json.dumps([record["task"], record["format"], model], sort_keys=True)
            group = grouped.setdefault(key, {"task": record["task"], "format": record["format"],
                                             "model": model, "attempts": [], "works": set(), "approved": set()})
            group["attempts"].append(attempt)
            group["works"].add(receipt["path"])
            group["approved"].update(quality.get("receipt_approvals", {}).get(receipt["path"], []))
    groups = [{"task": group["task"], "format": group["format"], "model": group["model"],
               "work_count": len(group["works"]), "attempt_count": len(group["attempts"]),
               "linked_human_approved_outputs": len(group["approved"]),
               "measurements": _measurements(group["attempts"], len(group["approved"]))}
              for _, group in sorted(grouped.items())]
    return {"schema_version": "f1.model_evaluation.v1", "event_id": identity["id"],
            "comparison_id": comparison_id, "work_count": len(receipts), "attempt_count": len(attempts),
            "incomplete_execution_evidence_count": len(incomplete), "incomplete_execution_evidence": incomplete,
            "failed_attempts": sum(item["status"] == "failed" for item in attempts),
            "abstained_attempts": sum(item["status"] == "abstained" for item in attempts),
            "declared_eligibility_failed_attempts": sum(item["eligibility"]["status"] == "failed" for item in attempts),
            "unreviewed_eligibility_attempts": sum(item["eligibility"]["status"] == "not_reviewed" for item in attempts),
            "quality": quality,
            "measurements": _measurements(attempts, quality["human_approved_outputs"], bool(errors or incomplete)),
            "groups": groups,
            "errors": errors, "binding_failures": binding_failures,
            "limitations": ["No model promotion or quality parity is inferred.",
                            "Unknown usage or cost is not zero; estimates are not settled charges.",
                            "Execution intents without final work receipts are incomplete evidence, excluded from known attempt_count; execution, charges and missing usage remain unknown.",
                            "Model groups cover saved work receipts; incomplete execution evidence remains unassigned to an observed model.",
                            "Machine/human seconds are sums of recorded effort, not wall-clock time to acceptance.",
                            "Account-shared token readings are not attributable and are excluded from token totals.",
                            "Latest human decisions apply to prior explicit operator receipt links for the same exact output binding; carried links do not prove model causality.",
                            "Model-to-finished-output links are operator supplied, not causal proof."]}
