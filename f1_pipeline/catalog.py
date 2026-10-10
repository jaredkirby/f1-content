"""Catalog original bytes, validated derivative recipes, and hash-bound reviews."""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import tempfile
from .core import ROOT, config, digest, ensure_space, log, probe, read_json, run, safe_relative, write_workspace_json as write_json

TAXONOMY = {
    "race_start": r"start|lights out|opening lap|lap 1",
    "incident": r"crash|collid|collision|contact|spin|retir",
    "weather": r"\brain\b|\bwet\b|\bdry\b|weather|intermediate",
    "strategy": r"\btyres?\b|\btires?\b|strategy|\bpit\b|restart",
    "result": r"\bwin(?:s|ner|ning)?\b|victory|finish|classification|result",
    "reaction": r"interview|react|says|verdict|reflect",
    "highlights": r"highlight|recap",
}
PROXY_RECIPE = {"version": 1, "kind": "proxy", "scale": "960:-2", "video_codec": "libx264",
                "preset": "fast", "crf": 26, "pixel_format": "yuv420p", "audio_codec": "aac",
                "audio_bitrate": "96k", "faststart": True, "validation": "probe_and_full_decode"}
CONTACT_RECIPE = {"version": 1, "kind": "contact_sheet", "frames": 12, "scale": "320:-2",
                  "tile": "4x3", "validation": "probe_and_full_decode"}


def labels(text):
    return [label for label, pattern in TAXONOMY.items() if re.search(pattern, text, re.I)] or ["context"]


def sources_list(document):
    if isinstance(document, list):
        return document
    if isinstance(document, dict) and isinstance(document.get("sources"), list):
        return document["sources"]
    raise ValueError("Media inventory must be a source array or an object with sources[]")


def recipe_digest(recipe):
    return hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def cached_derivative(path, original_sha256, recipe):
    path = safe_relative(path)
    receipt_path = safe_relative(path.with_suffix(".receipt.json"))
    try:
        receipt = read_json(receipt_path, {})
        return bool(path.is_file() and isinstance(receipt, dict)
                    and receipt.get("original_sha256") == original_sha256
                    and receipt.get("recipe_sha256") == recipe_digest(recipe)
                    and receipt.get("validation") == "probe_and_full_decode"
                    and receipt.get("bytes") == path.stat().st_size > 0
                    and receipt.get("sha256") == digest(path))
    except (ValueError, TypeError, OSError):
        return False


def video_details(info):
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video or any(type(video.get(k)) is not int or video[k] <= 0 for k in ("width", "height")):
        raise ValueError("Missing valid video dimensions")
    return video


def validate_derivative(path, kind, duration, source_has_audio):
    info = probe(path)
    video = video_details(info)
    if kind == "proxy":
        value = float(info.get("format", {}).get("duration", "nan"))
        if not math.isfinite(value) or abs(value - duration) > .25:
            raise ValueError("Proxy duration mismatch")
        if video["width"] != 960 or video["height"] % 2:
            raise ValueError("Proxy dimensions do not match recipe")
        if source_has_audio and not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
            raise ValueError("Proxy lost source audio stream")
    elif video["width"] != 1280:
        raise ValueError("Contact sheet does not contain the configured four columns")
    run(["ffmpeg", "-v", "error", "-xerror", "-i", path, "-map", "0:v:0", "-f", "null", "-"], timeout=600)
    return info


def build_derivative(original, destination, sha, duration, has_audio, recipe):
    destination = safe_relative(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = safe_relative(destination.with_suffix(".receipt.json"))
    kind = recipe["kind"]
    fd, name = tempfile.mkstemp(prefix="." + destination.stem + "-", suffix=destination.suffix, dir=destination.parent)
    os.close(fd)
    pending = Path(name)
    try:
        args = ["ffmpeg", "-v", "error", "-xerror", "-y", "-i", original]
        if kind == "proxy":
            args += ["-vf", "scale=" + recipe["scale"], "-c:v", recipe["video_codec"],
                     "-preset", recipe["preset"], "-crf", str(recipe["crf"]), "-pix_fmt", recipe["pixel_format"],
                     "-c:a", recipe["audio_codec"], "-b:a", recipe["audio_bitrate"], "-movflags", "+faststart"]
        else:
            args += ["-vf", f"fps={recipe['frames']}/{duration},scale={recipe['scale']},tile={recipe['tile']}", "-frames:v", "1"]
        run(args + [pending])
        info = validate_derivative(pending, kind, duration, has_audio)
        receipt = {"original_sha256": sha, "recipe": recipe, "recipe_sha256": recipe_digest(recipe),
                   "sha256": digest(pending), "bytes": pending.stat().st_size,
                   "validation": "probe_and_full_decode", "duration": duration,
                   "width": video_details(info)["width"], "height": video_details(info)["height"]}
        with pending.open("rb") as stream:
            os.fsync(stream.fileno())
        pending.replace(destination)
        write_json(receipt_path, receipt)
    finally:
        pending.unlink(missing_ok=True)


def review_ranges(review, sha, duration, original):
    """Reject stale reviews instead of attaching observations to different bytes."""
    if not isinstance(review, dict):
        raise ValueError("Malformed clip review")
    hashes = [review[k] for k in ("sha256", "original_sha256") if k in review]
    if not hashes or any(value != sha for value in hashes):
        raise ValueError("Clip review has missing or stale original SHA-256")
    if review.get("local_path") and safe_relative(review["local_path"]) != original:
        raise ValueError("Clip review refers to a different local original")
    segments = review.get("segments", [])
    if not isinstance(segments, list):
        raise ValueError("Clip review segments must be an array")
    ranges = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("Malformed reviewed segment")
        start, end = segment.get("in_seconds", segment.get("in")), segment.get("out_seconds", segment.get("out"))
        if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end))
                or not 0 <= start < end <= duration):
            raise ValueError("Reviewed interval lies outside original media duration")
        row = {"in": start, "out": end}
        for key in ("observation", "label", "review_evidence"):
            if key in segment:
                if not isinstance(segment[key], str):
                    raise ValueError("Review observation fields must be strings")
                row[key] = segment[key]
        if "event_ids" in segment:
            if not isinstance(segment["event_ids"], list) or any(not isinstance(v, str) or not v for v in segment["event_ids"]):
                raise ValueError("Review event_ids must be strings")
            row["event_ids"] = list(segment["event_ids"])
        ranges.append(row)
    return ranges


def catalog():
    c = config()
    document = read_json(safe_relative(ROOT / "research/media/sources.json"))
    if document is None:
        raise RuntimeError("Media discovery has not produced sources.json")
    if isinstance(document, dict) and document.get("event_id", c["id"]) != c["id"]:
        raise ValueError("Media inventory event mismatch")
    sources, assets, duplicates = sources_list(document), [], {}
    review_path = safe_relative(ROOT / "research/media/clip_review.json")
    review_doc = read_json(review_path, {})
    if not isinstance(review_doc, dict) or review_doc.get("event_id", c["id"]) != c["id"]:
        raise ValueError("Clip review event mismatch")
    review_rows = review_doc.get("reviews", [])
    if not isinstance(review_rows, list) or any(not isinstance(r, dict) or not isinstance(r.get("source_id"), str) for r in review_rows):
        raise ValueError("Malformed clip review records")
    reviews = {r["source_id"]: r for r in review_rows}
    if len(reviews) != len(review_rows):
        raise ValueError("Duplicate source IDs in clip review")
    review_sha = digest(review_path) if review_path.exists() else None

    total, source_ids = 0, set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("Every media source must be an object")
        source.setdefault("id", f"source-{index:03d}")
        if not isinstance(source["id"], str) or not source["id"] or source["id"] in source_ids:
            raise ValueError("Missing or duplicate media source ID")
        source_ids.add(source["id"])
        if source.get("event_id", c["id"]) != c["id"]:
            raise ValueError("Media source event mismatch")
        source.setdefault("url", source.get("source_url"))
        source["labels"] = sorted(set(source.get("categories", []) + labels(source.get("title", "") + " " + source.get("description", ""))))
        source["label_method"] = "research-agent metadata + versioned keyword taxonomy; not automated video understanding"
        if not source.get("local_path"):
            continue
        original = safe_relative(source["local_path"])
        if not original.is_file():
            raise ValueError("Missing downloaded asset: " + str(source["local_path"]))
        sha = digest(original)
        if not source.get("sha256") or sha != source["sha256"]:
            raise ValueError("Original integrity mismatch or missing acquisition hash: " + str(original))
        size = original.stat().st_size
        if size > c.get("max_asset_bytes", c["media_budget_bytes"]):
            raise ValueError("Original exceeds configured per-asset byte limit")
        info = probe(original)
        video = video_details(info)
        duration = float(info.get("format", {}).get("duration", "nan"))
        if not math.isfinite(duration) or not 0 < duration <= 3600:
            raise ValueError("Unreasonable original duration")
        review = reviews.get(source["id"])
        ranges = review_ranges(review, sha, duration, original) if review is not None else []
        source["reviewed_ranges"] = ranges
        if review is not None:
            source["review_receipt_sha256"] = review_sha
        if sha in duplicates:
            asset = duplicates[sha]
            source["asset_id"] = asset["id"]
            asset["source_ids"].append(source["id"])
            if ranges:
                asset["reviews"].append({"source_id": source["id"], "ranges": ranges, "receipt_sha256": review_sha})
                asset["reviewed_ranges"].extend(r for r in ranges if r not in asset["reviewed_ranges"])
                asset["review_status"] = "sampled_visual_review_complete"
                asset["review_receipt_sha256"] = review_sha
                asset["review_receipt"] = "research/media/clip_review.json"
            continue
        total += size
        if total > c["media_budget_bytes"]:
            raise RuntimeError("Media collection exceeds configured budget")
        asset_id = "asset-" + sha[:16]
        proxy = safe_relative(ROOT / "media/proxies" / f"{asset_id}.mp4")
        contact = safe_relative(ROOT / "media/contact_sheets" / f"{asset_id}.jpg")
        has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
        for destination, recipe in ((proxy, PROXY_RECIPE), (contact, CONTACT_RECIPE)):
            if not cached_derivative(destination, sha, recipe):
                ensure_space(int(duration * 160000 + 2000000) if recipe["kind"] == "proxy" else 2000000)
                build_derivative(original, destination, sha, duration, has_audio, recipe)
        asset = {"id": asset_id, "source_id": source["id"], "source_ids": [source["id"]],
                 "sha256": sha, "original_sha256": sha, "original": str(original.relative_to(ROOT)),
                 "bytes": size, "duration": duration, "width": video["width"], "height": video["height"],
                 "codec": video.get("codec_name"), "has_audio": has_audio,
                 "proxy": str(proxy.relative_to(ROOT)), "proxy_sha256": digest(proxy),
                 "proxy_recipe_sha256": recipe_digest(PROXY_RECIPE),
                 "contact_sheet": str(contact.relative_to(ROOT)), "contact_sheet_sha256": digest(contact),
                 "contact_sheet_recipe_sha256": recipe_digest(CONTACT_RECIPE), "labels": source["labels"],
                 "rights_status": source.get("rights_status", "unknown"),
                 "review_status": "sampled_visual_review_complete" if ranges else "contact_sheet_pending",
                 "reviewed_ranges": list(ranges), "reviews": []}
        if ranges:
            asset.update(review_method=review.get("review_method", "Unspecified review method"),
                         review_receipt="research/media/clip_review.json", review_receipt_sha256=review_sha)
            asset["reviews"].append({"source_id": source["id"], "ranges": ranges, "receipt_sha256": review_sha})
        assets.append(asset)
        duplicates[sha] = asset
        source["asset_id"] = asset_id
        print(f"Processed: {source.get('title', source['id'])} ({duration:.1f}s)", flush=True)
    result = {"event_id": c["id"], "sources": sources, "assets": assets, "original_bytes": total,
              "scope_note": "Bounded discovery; indexed URLs and successfully downloaded files are counted separately."}
    write_json(ROOT / "data/processed/catalog.json", result)
    log("catalog", "complete", sources=len(sources), assets=len(assets), bytes=total)
    return result
