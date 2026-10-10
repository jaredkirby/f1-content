from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import ipaddress
import math
import re
import subprocess
import tempfile
import time
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlparse
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

CODE_ROOT = Path(__file__).resolve().parents[1]

def resolve_workspace(value=None):
    """Select one event workspace; relative environment overrides are ambiguous."""
    value = os.environ.get("F1_WORKSPACE") if value is None else value
    if value is None:
        return CODE_ROOT
    path = Path(value).expanduser()
    if not value or not path.is_absolute():
        raise ValueError("F1_WORKSPACE must be an absolute event-workspace path")
    return path.resolve()

ROOT = resolve_workspace()

def safe_relative(path, root=None):
    """Resolve a workspace file/directory, rejecting traversal and escaping symlinks."""
    root = Path(ROOT if root is None else root).resolve()
    p = (root / path).resolve()
    if root not in p.parents:
        raise ValueError("Path escapes event workspace: " + str(path))
    return p

def now():
    return datetime.now(timezone.utc).isoformat()

def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default

def write_json(path, data):
    """General atomic JSON utility; pipeline destinations use write_workspace_json."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=path.name+".",
                                         suffix=".tmp", dir=path.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)

def write_workspace_json(path, data, root=None):
    write_json(safe_relative(path, root=root), data)

def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

SESSION_NAMES = {"Practice 1", "Practice 2", "Practice 3", "Qualifying", "Sprint",
                 "Sprint Qualifying", "Sprint Shootout", "Race"}

def validate_config(value, root=None):
    if not isinstance(value, dict):
        raise ValueError("An event config object is required before collecting data")
    c = dict(value)
    for field in ("id", "year", "country_name", "session_name", "event_date", "session_key", "meeting_key"):
        if field not in c:
            raise ValueError("Missing event config identity: " + field)
    if not isinstance(c["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", c["id"]):
        raise ValueError("Event id must be a lowercase slug")
    if type(c["year"]) is not int or not 1950 <= c["year"] <= 2100:
        raise ValueError("Invalid event year")
    if (not isinstance(c["country_name"], str) or not c["country_name"].strip()
            or c["country_name"] != c["country_name"].strip()
            or any(ord(char) < 32 for char in c["country_name"])):
        raise ValueError("Invalid country_name")
    if not isinstance(c["session_name"], str) or c["session_name"] not in SESSION_NAMES:
        raise ValueError("Unsupported exact session_name")
    try:
        day = date.fromisoformat(c["event_date"])
    except (ValueError, TypeError):
        raise ValueError("event_date must be YYYY-MM-DD") from None
    if day.isoformat() != c["event_date"] or day.year != c["year"]:
        raise ValueError("Event date and year disagree")
    for field in ("session_key", "meeting_key"):
        if type(c[field]) is not int or c[field] <= 0:
            raise ValueError("A positive pinned identity is required: " + field)
    c.setdefault("timezone", "UTC")
    try:
        ZoneInfo(c["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        raise ValueError("Invalid event timezone") from None
    if "start_utc" in c:
        try:
            start = datetime.fromisoformat(c["start_utc"].replace("Z", "+00:00"))
            if start.utcoffset() is None or start.utcoffset().total_seconds() != 0:
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            raise ValueError("start_utc must contain an explicit UTC offset") from None
    for field, default, lower, upper in (
        ("reserve_bytes", 8 * 1024**3, 1, 1024**5),
        ("media_budget_bytes", 750 * 1024**2, 1, 1024**4),
        ("max_asset_bytes", 250 * 1024**2, 1, 1024**4),
        ("request_timeout_seconds", 45, 1, 300),
        ("max_retries", 2, 0, 5),
    ):
        c.setdefault(field, default)
        if type(c[field]) is not int or not lower <= c[field] <= upper:
            raise ValueError("Invalid bounded config value: " + field)
    if c["max_asset_bytes"] > c["media_budget_bytes"]:
        raise ValueError("Per-asset limit exceeds original-media budget")
    if "formats" in c and (not isinstance(c["formats"], list) or not c["formats"]
                           or any(f not in ("vertical", "landscape") for f in c["formats"])):
        raise ValueError("Invalid render formats")
    # Configured file paths are data, not an escape hatch to another workspace.
    paths = c.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError("Config paths must be an object")
    for key, path in list(paths.items()) + [(k, v) for k, v in c.items() if k.endswith("_path")]:
        if not isinstance(path, str) or not path:
            raise ValueError("Invalid configured path: " + key)
        safe_relative(path, root=root)
    samples = c.setdefault("telemetry_samples", [])
    if not isinstance(samples, list) or len(samples) > 16:
        raise ValueError("telemetry_samples must contain at most 16 explicit lap selections")
    seen = set()
    for sample in samples:
        if not isinstance(sample, dict) or set(sample) - {"driver", "driver_number", "lap", "max_seconds"}:
            raise ValueError("Invalid telemetry sample fields")
        if ("driver" in sample) == ("driver_number" in sample):
            raise ValueError("Telemetry sample needs exactly one driver identifier")
        if "driver" in sample and (not isinstance(sample["driver"], str) or not re.fullmatch(r"[A-Z]{3}", sample["driver"])):
            raise ValueError("Telemetry driver must be a three-letter session acronym")
        if "driver_number" in sample and (type(sample["driver_number"]) is not int or not 1 <= sample["driver_number"] <= 999):
            raise ValueError("Invalid telemetry driver_number")
        if type(sample.get("lap")) is not int or not 1 <= sample["lap"] <= 200:
            raise ValueError("Telemetry sample needs a lap from 1 to 200")
        cap = sample.get("max_seconds", 180)
        if type(cap) not in (int, float) or not math.isfinite(cap) or not 1 <= cap <= 600:
            raise ValueError("Invalid telemetry max_seconds")
        identity = (sample.get("driver", sample.get("driver_number")), sample["lap"])
        if identity in seen:
            raise ValueError("Duplicate telemetry selection")
        seen.add(identity)
    return c

def config():
    return validate_config(read_json(safe_relative("config/event.json")))

def ensure_space(additional=0, root=None, reserve=None):
    root = ROOT if root is None else root
    if type(additional) not in (int, float) or not math.isfinite(additional) or additional < 0:
        raise ValueError("Expected write size must be finite and nonnegative")
    reserve = config()["reserve_bytes"] if reserve is None else reserve
    free = shutil.disk_usage(root).free
    if free - additional < reserve:
        raise RuntimeError(f"Disk reserve: {free} free, need {additional} plus {reserve} reserve")

def log(stage, status, **kwargs):
    record = {"at": now(), "stage": stage, "status": status, **kwargs}
    path = safe_relative("runs/events.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record

def public_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS source URLs are accepted")
    if parsed.port not in (None, 443):
        raise ValueError("Nonstandard URL port")
    for addr in socket.getaddrinfo(parsed.hostname, 443):
        if not ipaddress.ip_address(addr[4][0]).is_global:
            raise ValueError("Non-public source address")
    return url

class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(url, destination, limit=32 * 1024 * 1024, force=False):
    """Stream bounded public data, write atomically, and persist a provenance receipt."""
    c = config()  # Fail before network or writes when event identity is not configured.
    destination = safe_relative(destination)
    if type(limit) is not int or limit <= 0:
        raise ValueError("Download byte limit must be a positive integer")
    receipt_path = safe_relative(destination.with_suffix(destination.suffix + ".receipt.json"))
    previous = read_json(receipt_path, {})
    if destination.exists() and not force:
        if previous.get("url") == url and previous.get("sha256") == digest(destination):
            return {**previous, "cached": True}
        raise RuntimeError(f"Existing file lacks matching source receipt: {destination}")
    public_url(url)
    ensure_space(limit)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = safe_relative(destination.with_suffix(destination.suffix + ".part"))
    attempts = c["max_retries"] + 1
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "F1ContentResearch/0.1 (personal research)", "Accept": "*/*"})
            opener = build_opener(PublicRedirects())
            with opener.open(request, timeout=c["request_timeout_seconds"]) as response:
                length = int(response.headers.get("Content-Length", 0))
                if length > limit:
                    raise ValueError(f"Source exceeds {limit} byte limit")
                total = 0
                with partial.open("wb") as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        total += len(block)
                        if total > limit:
                            raise ValueError(f"Download exceeds {limit} byte limit")
                        ensure_space(len(block))
                        output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
                if length and total != length:
                    raise ValueError("Incomplete response")
                if total == 0:
                    raise ValueError("Empty response")
                receipt = {"url": url, "final_url": response.url, "retrieved_at": now(),
                           "http_status": response.status, "content_type": response.headers.get("Content-Type"),
                           "bytes": total, "sha256": digest(partial), "path": str(destination.relative_to(ROOT)),
                           "etag": response.headers.get("ETag")}
            partial.replace(destination)
            write_workspace_json(receipt_path, receipt)
            log("download", "complete", **receipt)
            return receipt
        except Exception as e:
            partial.unlink(missing_ok=True)
            if isinstance(e, (ValueError, RuntimeError)) or attempt + 1 == attempts:
                log("download", "failed", url=url, error=str(e))
                raise
            time.sleep(2 ** attempt)

def run(args, timeout=600):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} failed: {result.stderr[-3000:]}")
    return result.stdout

def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", path]))
