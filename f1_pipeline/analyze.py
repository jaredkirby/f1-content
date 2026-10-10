from datetime import datetime, timedelta
import os
from .core import ROOT, config, read_json, write_json, log, now, digest, safe_relative

# Reviewed official source clips. A single incident can appear in several replays;
# these are source-relative editorial boundaries, not universal broadcast offsets.
MATCHES = {
    "E01": [("f1-1878660960273042920", 0, 7)], "E02": [],
    "E03": [("f1-1878655716565678004", 0, 20)],
    "E04": [("f1-1878656351618049423", 0, 12)],
    "E05": [("f1-1878657260508982950", 0, 15)],
    "E06": [("f1-1878658590900950386", 0, 6)],
    "E07": [("f1-1878658723525130166", 0, 18)],
    "E08": [("f1-1878660960273042920", 199, 215)],
    "E09": [("f1-1878660960273042920", 285, 314)], "E10": [("f1-1878660960273042920", 315, 339)],
    "E11": [("f1-1878659297812319467", 0, 24)],
    "E12": [("f1-1878660117633008506", 0, 15), ("f1-1878661025872049286", 0, 25)],
    "E13": [],
}

def reconcile_results(official, api):
    errors=[]
    for name,rows in (("official",official),("API",api)):
        ids=[r.get("driver_number") for r in rows]
        if None in ids or len(ids)!=len(set(ids)):
            errors.append(f"{name} classification has missing/duplicate driver IDs")
    if {r.get('driver_number') for r in official}!={r.get('driver_number') for r in api}:
        errors.append('Official/API classification driver sets differ')
    if errors:return errors
    by_number = {r["driver_number"]: r for r in api}
    for row in official:
        other = by_number.get(row["driver_number"])
        if not other:
            errors.append(f"Missing API result for car {row['driver_number']}")
            continue
        for official_key, api_key in (("laps_completed", "number_of_laps"), ("points", "points")):
            if row[official_key] != other[api_key]:
                errors.append(f"Car {row['driver_number']} {official_key} conflict")
        if (row["status"] == "DNF") != other["dnf"]:
            errors.append(f"Car {row['driver_number']} DNF conflict")
        if row.get("classified") and row.get("position") != other.get("position"):
            errors.append(f"Car {row['driver_number']} position conflict")
        gap = row.get("gap_seconds")
        if isinstance(gap, (int, float)) and isinstance(other.get("gap_to_leader"), (int, float)):
            if abs(gap - other["gap_to_leader"]) > .001:
                errors.append(f"Car {row['driver_number']} gap conflict")
    return errors

def lap_finish_gaps(laps, drivers):
    numbers = {d["name_acronym"]: d["driver_number"] for d in drivers}
    finishes = {}
    for acronym in ("VER", "HAM", "LEC", "ANT"):
        finishes[acronym] = {}
        for row in laps:
            if row["driver_number"] == numbers.get(acronym) and row.get("date_start") and row.get("lap_duration"):
                finishes[acronym][row["lap_number"]] = datetime.fromisoformat(row["date_start"]) + timedelta(seconds=row["lap_duration"])
    gaps = []
    for lap, leader_time in sorted(finishes.get("VER", {}).items()):
        gaps.append({"lap": lap, **{a: round((rows[lap] - leader_time).total_seconds(), 3) for a, rows in finishes.items() if lap in rows}})
    return gaps

def sprint_media_matches(event_id, sources, assets, review_sha, verified_assets=None):
    """Intersect historical editorial selections with current hash-bound reviews.

    Adjacent sampled review segments remain distinct. Gaps and unreviewed lead-in
    frames cannot be silently promoted into the selected incident interval.
    """
    from .analyze_session import within_review
    verified_assets=set() if verified_assets is None else verified_assets
    matches=[]
    for source_id,start,end in MATCHES.get(event_id,[]):
        source=sources.get(source_id,{})
        asset=assets.get(source.get('asset_id'))
        if not asset:continue  # Discovery reference without downloaded media.
        sha=asset.get('sha256')
        if not sha or source.get('sha256')!=sha:
            raise ValueError('Sprint media source has stale or missing acquisition hash: '+source_id)
        if asset.get('review_receipt_sha256')!=review_sha or not review_sha:
            raise ValueError('Sprint catalog visual review changed; rerun catalog: '+source_id)
        if asset['id'] not in verified_assets:
            original=safe_relative(asset['original'])
            if not original.is_file() or digest(original)!=sha:
                raise ValueError('Sprint original changed since catalog: '+source_id)
            verified_assets.add(asset['id'])
        selected=[]
        for approved in asset.get('reviewed_ranges',[]):
            left=max(start,approved['in']);right=min(end,approved['out'],asset['duration'])
            if left<right and within_review(asset,left,right):
                selected.append((left,right))
        if not selected:
            raise ValueError('Sprint incident selection has no currently reviewed footage: '+source_id)
        for left,right in sorted(set(selected)):
            matches.append({'asset_id':asset['id'],'source_id':source_id,'in':left,'out':right,
                            'source_sha256':sha,'review_receipt_sha256':review_sha,
                            'requested_in':start,'requested_out':end,
                            'alignment':'Historical incident selection intersected with current hash-bound sampled visual review'})
    return matches

def analyze():
    if config().get('session_type')=='qualifying':
        from .analyze_session import analyze_qualifying
        return analyze_qualifying()
    bundle = read_json(ROOT / "research/event/event_bundle.json")
    catalog = read_json(ROOT / "data/processed/catalog.json")
    if bundle["event"]["id"] != config()["id"] or catalog["event_id"] != config()["id"]:
        raise ValueError("Event identity mismatch")
    raw = ROOT / "data/raw/openf1"
    manifest = read_json(ROOT / "data/processed/data_manifest.json", {})
    if manifest.get("event_id") != config()["id"]:
        raise ValueError("Data manifest event mismatch")
    verified = set()
    for receipt in manifest.get("receipts", []):
        path = safe_relative(receipt["path"])
        if not path.exists() or digest(path) != receipt["sha256"]:
            raise ValueError(f"Raw data integrity mismatch: {path}")
        rows = read_json(path)
        if not isinstance(rows, list) or any(r.get("session_key") != config()["session_key"] for r in rows):
            raise ValueError(f"Raw data session mismatch: {path}")
        verified.add(path.name)
    for required in ("drivers.json", "laps.json", "session_result.json", "weather.json", "pit.json"):
        if required not in verified:
            raise ValueError(f"Required validated data unavailable: {required}")
    conflicts = reconcile_results(bundle["results"], read_json(raw / "session_result.json", []))
    if conflicts:
        raise ValueError("Classification gate failed: " + "; ".join(conflicts))
    sources = {s["id"]: s for s in catalog["sources"]}
    assets = {a["id"]: a for a in catalog["assets"]}
    review_path=safe_relative('research/media/clip_review.json')
    review_sha=digest(review_path) if review_path.is_file() else None
    verified_media=set()
    timeline = bundle["timeline"]
    data_assets=[dict(a) for a in bundle["assets"] if a["kind"]=="data"]
    fixed_paths={"D_GRID":"research/event/fia_final_grid.pdf", "D_RESULTS":"research/event/fia_final_classification.pdf",
                 "D_CHAMPIONSHIP":"research/event/fia_championship_after_sprint.pdf", "D_STEWARDS":"data/processed/stewards_decisions.json"}
    decision_files={"fia_perez":"fia_perez_decision.pdf", "fia_norris":"fia_mclaren_norris_decision.pdf", "fia_albon":"fia_albon_decision.pdf", "fia_bottas":"fia_bottas_decision.pdf"}
    write_json(ROOT/"data/processed/stewards_decisions.json", {"decisions":[{"source_id":sid,"path":"research/event/"+name,"sha256":digest(ROOT/"research/event"/name),"source":next(s for s in bundle["sources"] if s["id"]==sid)} for sid,name in decision_files.items()]})
    for a in data_assets:
        if a["id"] in fixed_paths:a["local_path"]=fixed_paths[a["id"]]
        elif a.get("local_path"):
            a["local_path"]=str((ROOT/"research/event"/a["local_path"]).resolve().relative_to(ROOT))
        if a["id"]=="D_INTERVALS":
            a.update(status="derived_lap_finish_gaps_not_continuous_intervals",local_path="data/processed/lap_finish_gaps.json",source_ids=["openf1_laps"])
        if a["id"]=="D_CAR_DATA":
            a.update(status="partial_context_only" if manifest.get("telemetry_samples") else "unavailable",local_paths=[r["path"] for r in manifest["receipts"] if "/car_data_" in r["path"]],description="Bounded VER and HAM lap-7 car data; not incident-driver brake evidence",required_scope_gap="Incident-driver brake traces are not collected or validated")
    for event in timeline:
        matches = sprint_media_matches(event['id'],sources,assets,review_sha,verified_media)
        event["media_matches"] = matches
        event["assembly_status"] = "footage_available" if matches else "data_graphics_or_additional_footage"
        event["data_assets"] = [a for a in data_assets if a["id"] in event["required_asset_ids"]]
    ideas = bundle["ranked_ideas"]
    for idea in ideas:
        if idea["id"] == "I01":
            idea["research_working_title"] = idea["title"]
            idea["title"] = "Singapore Sprint: three turning points"
            idea["angle"] = "A short vertical recap and expanded landscape analysis of the start, changing conditions and final-lap McLaren contact."
        relevant = [e for e in timeline if e["id"] in idea["event_ids"]]
        idea["available_asset_ids"] = sorted({m["asset_id"] for e in relevant for m in e["media_matches"]})
        idea["footage_event_coverage"] = round(sum(bool(e["media_matches"]) for e in relevant) / max(1,len(relevant)), 3)
        idea["ranking_method"] = "AI editorial research judgment; explicit score basis and deterministic asset-availability accounting"
        idea["status"] = "assembly_ready" if idea["available_asset_ids"] else "graphics_ready"
        produced=[v for v in read_json(ROOT/"outputs/manifest.json",{}).get("videos",[]) if v.get("idea_id")==idea["id"]]
        if produced:
            idea["produced_outputs"]=[{k:v[k] for k in ("format","path","duration","status")} for v in produced]
            idea["status"]="produced"
    drivers = read_json(raw / "drivers.json")
    laps = read_json(raw / "laps.json")
    gaps = lap_finish_gaps(laps, drivers)
    write_json(ROOT/"data/processed/lap_finish_gaps.json",{"method":"Difference of recorded lap end timestamps, not continuous intervals", "source":"data/raw/openf1/laps.json", "records":gaps})
    weather = read_json(raw / "weather.json")
    race_weather = [w for w in weather if config()["event_date"]+"T09:36" <= w["date"] <= config()["event_date"]+"T10:17"]
    pit = read_json(raw / "pit.json")
    telemetry = {}
    for acronym in ("VER", "HAM"):
        name = f"car_data_{acronym}_lap7.json"
        rows = read_json(raw / name, []) if name in verified else []
        speeds = [r["speed"] for r in rows if isinstance(r.get("speed"), (int,float))]
        telemetry[acronym] = {"lap": 7, "samples": len(rows), "max_observed_speed_kmh": max(speeds) if speeds else None,
                              "interpretation": "Sample maximum, not a top-speed specification or causal crash finding"}
    insights = {"lap_finish_gaps": gaps, "gap_method": "Difference between each car's recorded lap end UTC; lap start + duration. Not continuous intervals.",
                "race_weather_samples": len(race_weather),
                "track_temperature_range_c": [min(w["track_temperature"] for w in race_weather), max(w["track_temperature"] for w in race_weather)] if race_weather else None,
                "pit_lane_records": len(pit), "stationary_stop_records": sum(p.get("stop_duration") is not None for p in pit),
                "pit_interpretation": "Lane transit is not evidence of a stationary stop or tyre change; retain unknown stop durations.",
                "car_data": telemetry, "classification_crosscheck": {"matched_drivers": len(bundle["results"]), "conflicts": conflicts}}
    result = {"event": bundle["event"], "sources": bundle["sources"], "timeline": timeline,
              "results": bundle["results"], "ideas": ideas, "derived_facts": bundle["derived_facts"],
              "conflicts": bundle["conflicts"], "unknowns": bundle["unknowns"], "insights": insights, "data_assets":data_assets}
    write_json(ROOT / "data/processed/editorial.json", result)
    write_json(ROOT / "data/processed/decisions.json", {"at": now(), "actual_jev_inference": False,
               "jev_status": "credential_present_not_invoked" if os.environ.get("TYPESAFE_API_KEY") else "credential_missing",
               "model_adapter": "f1_pipeline/jev_adapter.py", "classification_method": "research agent labels + keyword taxonomy",
               "ranking_method": "AI editorial judgments in ranked_ideas.json, not a Jev model result", "ideas": ideas})
    log("analyze", "complete", timeline_segments=len(timeline), ideas=len(ideas), matched_results=22)
    return result
