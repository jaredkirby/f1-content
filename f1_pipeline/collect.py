"""Collect the pinned session only; telemetry is an explicit config selection."""
from datetime import datetime, timedelta, timezone
import math
import time
from urllib.parse import urlencode, quote
from zoneinfo import ZoneInfo
from .core import ROOT, config, fetch, read_json, write_workspace_json as write_json, log, safe_relative


def telemetry_url(session, driver, start, end):
    base = "https://api.openf1.org/v1/car_data?" + urlencode({"session_key": session, "driver_number": driver})
    return base + "&date>=" + quote(start, safe=":-T.") + "&date<=" + quote(end, safe=":-T.")


def validate_session(sessions, c):
    if not isinstance(sessions, list) or any(not isinstance(s, dict) for s in sessions):
        raise ValueError("Sessions endpoint must return record objects")
    matches = [s for s in sessions if type(s.get("session_key")) is int and s["session_key"] == c["session_key"]]
    if len(matches) != 1:
        raise ValueError("Pinned session must resolve to exactly one record")
    selected = matches[0]
    for key in ("session_key", "meeting_key", "year", "country_name", "session_name"):
        if type(selected.get(key)) is not type(c[key]) or selected.get(key) != c[key]:
            raise ValueError("Session identity mismatch or missing field: " + key)
    if selected.get("is_cancelled"):
        raise ValueError("Pinned session is canceled")
    try:
        start = datetime.fromisoformat(selected["date_start"].replace("Z", "+00:00"))
        if start.utcoffset() is None:
            raise ValueError
        event_day = start.astimezone(ZoneInfo(c.get("timezone", "UTC"))).date().isoformat()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("Session start needs an explicit valid timestamp") from None
    if event_day != c["event_date"]:
        raise ValueError("Session date does not match the configured local event date")
    return selected


def validate_records(rows, session_key, *, driver_number=None, time_bounds=None, allow_empty=True):
    if not isinstance(rows, list) or (not allow_empty and not rows):
        raise ValueError("Expected a nonempty record array" if not allow_empty else "Expected a record array")
    for row in rows:
        if not isinstance(row, dict) or type(row.get("session_key")) is not int or row["session_key"] != session_key:
            raise ValueError("Missing or mismatched record session_key")
        if driver_number is not None and (type(row.get("driver_number")) is not int or row["driver_number"] != driver_number):
            raise ValueError("Missing or mismatched telemetry driver_number")
        if time_bounds is not None:
            try:
                instant = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
                if instant.utcoffset() is None or not time_bounds[0] <= instant <= time_bounds[1]:
                    raise ValueError
            except (KeyError, TypeError, ValueError, AttributeError):
                raise ValueError("Telemetry sample lies outside its verified UTC interval") from None
    return rows


def endpoints_for(c):
    endpoints = ["drivers", "laps", "stints", "race_control", "weather", "position", "session_result", "pit"]
    if c["session_name"] in ("Race", "Sprint"):
        endpoints.append("starting_grid")
    return endpoints


def collect_data(force=False):
    c = config()  # No request or file mutation before strict identity validation.
    folder = safe_relative(ROOT / "data/raw/openf1")
    receipts, failures, accepted = [], [], {}
    query = {"year": c["year"], "country_name": c["country_name"], "session_name": c["session_name"]}
    url = "https://api.openf1.org/v1/sessions?" + urlencode(query)
    session_receipt = fetch(url, folder / "sessions.json", force=force)
    session = validate_session(read_json(folder / "sessions.json"), c)
    receipts.append({**session_receipt, "identity_verified": True})
    for endpoint in endpoints_for(c):
        path = folder / (endpoint + ".json")
        try:
            time.sleep(2.1)
            receipt = fetch("https://api.openf1.org/v1/" + endpoint + "?" + urlencode({"session_key": c["session_key"]}), path, force=force)
            data = validate_records(read_json(path), c["session_key"], allow_empty=endpoint not in ("drivers", "laps", "session_result"))
            receipts.append({**receipt, "records": len(data), "identity_verified": True})
            accepted[endpoint] = data
            print(f"{endpoint}: {len(data)} records", flush=True)
        except Exception as exc:
            failures.append({"endpoint": endpoint, "name": endpoint, "error": str(exc)})
            print(f"{endpoint}: unavailable ({exc})", flush=True)

    sampled = []
    for selection in c.get("telemetry_samples", []):
        label = selection.get("driver", str(selection.get("driver_number")))
        lap_number = selection["lap"]
        try:
            if "drivers" not in accepted or "laps" not in accepted:
                raise ValueError("Telemetry needs successfully validated drivers and laps from this collection")
            drivers = [d for d in accepted["drivers"] if (
                d.get("name_acronym") == selection["driver"] if "driver" in selection
                else d.get("driver_number") == selection["driver_number"])]
            if len(drivers) != 1 or type(drivers[0].get("driver_number")) is not int:
                raise ValueError("Telemetry driver does not resolve uniquely in this session")
            driver = drivers[0]
            laps = [lap for lap in accepted["laps"] if lap.get("driver_number") == driver["driver_number"]
                    and lap.get("lap_number") == lap_number]
            if len(laps) != 1:
                raise ValueError("Telemetry lap does not resolve uniquely in this session")
            lap = laps[0]
            start = datetime.fromisoformat(lap["date_start"].replace("Z", "+00:00"))
            if start.utcoffset() is None:
                raise ValueError("Lap start lacks a UTC offset")
            start = start.astimezone(timezone.utc)
            seconds = lap.get("lap_duration")
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
                raise ValueError("Selected lap has no verified finite positive duration")
            end = start + timedelta(seconds=min(seconds, selection.get("max_seconds", 180)))
            filename = f"car_data_{label}_lap{lap_number}.json"
            path = safe_relative(folder / filename)
            time.sleep(2.1)
            receipt = fetch(telemetry_url(c["session_key"], driver["driver_number"], start.replace(tzinfo=None).isoformat(), end.replace(tzinfo=None).isoformat()), path, force=force)
            rows = validate_records(read_json(path), c["session_key"], driver_number=driver["driver_number"],
                                    time_bounds=(start, end), allow_empty=False)
            receipts.append({**receipt, "records": len(rows), "identity_verified": True})
            sampled.append({"driver": driver.get("name_acronym"), "driver_number": driver["driver_number"],
                            "lap": lap_number, "start": start.isoformat(), "end": end.isoformat(),
                            "records": len(rows), "path": str(path.relative_to(ROOT))})
            print(f"{filename}: {len(rows)} records", flush=True)
        except Exception as exc:
            failures.append({"endpoint": "car_data", "driver": label, "lap": lap_number, "error": str(exc)})
            print(f"car_data {label} lap {lap_number}: unavailable ({exc})", flush=True)
    manifest = {"event_id": c["id"], "session": session, "receipts": receipts, "failures": failures,
                "status": "partial" if failures else "complete", "telemetry_requested": c.get("telemetry_samples", []),
                "telemetry_scope": ("Explicit configured driver/lap intervals only; no reconstruction of missing samples"
                                    if c.get("telemetry_samples") else "No telemetry samples configured or requested"),
                "telemetry_samples": sampled}
    write_json(ROOT / "data/processed/data_manifest.json", manifest)
    log("collect_data", manifest["status"], receipts=len(receipts), failures=failures)
    return manifest
