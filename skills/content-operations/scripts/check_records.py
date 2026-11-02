"""Read-only release checks. No network, sends, schedules or record writes."""
import argparse
import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

STATES = {"planned", "approved", "scheduled", "published", "failed", "verified"}
PLATFORMS = ("instagram", "linkedin", "tiktok", "youtube")

def nonblank_string(value):
    return isinstance(value, str) and bool(value.strip())

def valid_sha256(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None

def evidence_refs(value):
    return isinstance(value, list) and bool(value) and all(nonblank_string(item) for item in value)

def checked_instant(value):
    """Parse a recorded timestamp; any malformed type is a ValueError, never a crash."""
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an offset-bearing ISO string")
    return instant(value)

def timestamp_fields(record, fields, errors, prefix="", required=()):
    """Null/missing is unknown unless required; every supplied value must parse."""
    parsed = {}
    for field in fields:
        value = record.get(field)
        if value is None and field not in required:
            continue
        try:
            parsed[field] = checked_instant(value)
        except ValueError:
            errors.append(prefix + field + " needs a valid offset-bearing timestamp")
    return parsed

def web_url(value):
    """Syntax only: this never fetches a URL or proves its destination/publicity."""
    if not nonblank_string(value) or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and parsed.port != 0 and not parsed.username and not parsed.password
    except ValueError:
        return False

def tested_configuration(release):
    """Snapshot to capture at the actual end-to-end test, never refresh after an edit."""
    flow, guide = release.get("automation", {}), release.get("guide", {})
    return copy.deepcopy({
        "release": {key: release.get(key) for key in ("release_id", "platform", "account", "actual_post_url", "native_media_id", "caption_sha256")},
        "asset_sha256": release.get("asset", {}).get("sha256"),
        "guide": {key: guide.get(key) for key in ("keyword", "version", "pdf_url", "pdf_sha256")},
        "flow": {key: flow.get(key) for key in ("flow_id", "configuration_version", "source_flow_id", "source_template", "reel_id", "keyword", "variants", "trigger_scope", "trigger_live", "follower_gate_verified", "follower_gate_evidence", "recheck_loop_verified", "recheck_loop_evidence", "destination_pdf_url", "destination_pdf_sha256", "public_acknowledgement", "saved_config_evidence", "configuration_verified_at")}
    })

def requested_guide_binding(release, event):
    """Exact final-resource identity for a send, delivery or recipient confirmation."""
    if not release or release.get("platform") == "youtube":
        return None
    guide = release.get("guide", {})
    for value in (release.get("release_id"), release.get("platform"), release.get("account"), release.get("campaign"), guide.get("version"), guide.get("pdf_url"), event.get("recipient_reference"), event.get("dm_delivery_key")):
        if not isinstance(value, str) or not value.strip():
            return None
    if not valid_sha256(guide.get("pdf_sha256")) or event.get("guide_version") != guide.get("version") or event.get("guide_destination_verified") is not True:
        return None
    return {"release_id": release["release_id"], "platform": release["platform"], "account": release["account"], "campaign": release["campaign"], "recipient_reference": event["recipient_reference"], "guide_version": guide["version"], "pdf_url": guide["pdf_url"], "pdf_sha256": guide["pdf_sha256"], "dm_delivery_key": event["dm_delivery_key"], "resource_kind": "requested_guide"}

def bound_guide_evidence(evidence, expected):
    return expected is not None and isinstance(evidence, dict) and nonblank_string(evidence.get("reference")) and evidence.get("binding") == expected

def exact_reel(flow, release):
    reel = flow.get("reel_id")
    if not isinstance(reel, str) or not reel:
        return False
    if reel == release.get("native_media_id"):
        return True
    post_url = release.get("actual_post_url")
    if not web_url(post_url):
        return False
    url = urlsplit(post_url)
    parts = url.path.strip("/").split("/")
    return url.hostname in {"instagram.com", "www.instagram.com"} and len(parts) == 2 and parts[0] in {"reel", "p"} and parts[1] == reel

def instant(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Timestamp needs an offset")
    return d

def slots(publication, approval_expiry=None, *, anchor=None, service_start=None, interval_hours=None, window_hours=None):
    """Explicitly configured slots from a recorded anchor, never a scheduler."""
    if not anchor:
        raise ValueError("Provide the existing service's offset-bearing schedule anchor")
    if type(interval_hours) is not int or interval_hours <= 0 or type(window_hours) is not int or window_hours <= 0:
        raise ValueError("Explicit positive integer interval_hours and window_hours required")
    start = instant(publication)
    try:
        end = start + timedelta(hours=window_hours)
        if approval_expiry:
            end = min(end, instant(approval_expiry))
        step = timedelta(hours=interval_hours)
        first = instant(anchor).astimezone(start.tzinfo)
        advance = max(0, (start - first) // step + 1) * step
        if service_start:
            advance = max(advance, max(0, -((first - instant(service_start)) // step)) * step)
        # A next slot beyond the window is unnecessary, even if unrepresentable.
        if first > end or advance > end - first:
            return []
        first += advance
        result = []
        while first <= end:
            result.append(first.isoformat())
            # Do not construct an unnecessary next instant beyond datetime.max.
            if end - first < step:
                break
            first += step
        return result
    except OverflowError as ex:
        raise ValueError("Slot calculation is outside the supported timestamp range") from ex

def validate(doc, events=()):
    errors, warnings, seen = [], [], set()
    # Never mistake a retired, unrecognised or malformed tracker for zero good rows.
    if not isinstance(doc, dict) or type(doc.get("schema_version")) is not int or doc["schema_version"] not in (1, 2):
        return {"errors": ["Unsupported tracker schema_version; resolve the canonical tracker and schema first"], "warnings": [], "rows_checked": 0}
    rows = doc.get("releases")
    if "scheduled" in doc or not isinstance(rows, list) or not rows:
        return {"errors": ["Expected a non-empty releases array; legacy scheduled trackers need explicit reconciliation, not automatic conversion"], "warnings": [], "rows_checked": 0}
    if "adapter" in doc:
        # Imported history cannot become action authority by editing status flags.
        return {"errors": ["Read-only imported snapshot: reconcile its action requirements with the canonical writer and current live evidence; no external action or completion is authorised"], "warnings": [], "rows_checked": len(rows)}
    for row in rows:
        if not isinstance(row, dict):
            errors.append("Release rows must be objects")
            continue
        for key in ("asset", "approval", "scheduler", "native_verification", "guide", "automation", "comments", "completion", "production", "performance"):
            if key in row and not isinstance(row[key], dict):
                errors.append("Release " + key + " must be an object")
        if not isinstance(row.get("release_id"), str):
            errors.append("release_id must be a string")
        for key in ("campaign", "platform", "account", "edition", "status", "actual_post_url"):
            if row.get(key) is not None and not isinstance(row[key], str):
                errors.append(key + " must be a string")
        if row.get("platform") not in PLATFORMS:
            errors.append("platform must be exactly instagram, linkedin, tiktok or youtube")
        for section, field in (("approval", "status"), ("automation", "status"), ("comments", "coverage"), ("guide", "delivery_route")):
            nested = row.get(section, {})
            if isinstance(nested, dict) and nested.get(field) is not None and not isinstance(nested[field], str):
                errors.append(section + "." + field + " must be a string")
        for section, field in ((None, "actual_post_url"), ("asset", "remote_url"), ("guide", "article_url"), ("guide", "pdf_url"), ("automation", "flow_url"), ("automation", "destination_pdf_url")):
            nested = row if section is None else row.get(section, {})
            if isinstance(nested, dict) and nested.get(field) is not None and not web_url(nested[field]):
                errors.append((section + "." if section else "") + field + " must be a valid HTTP(S) URL without credentials")
        scheduler = row.get("scheduler", {})
        if isinstance(scheduler, dict):
            jobs = scheduler.get("active_job_ids", [])
            if not isinstance(jobs, list) or any(not isinstance(job, str) for job in jobs):
                errors.append("active_job_ids must be an array of strings")
            if scheduler.get("name") is not None and not isinstance(scheduler["name"], str):
                errors.append("scheduler.name must be a string")
    if errors:
        return {"errors": errors, "warnings": [], "rows_checked": 0}
    service = doc.get("service", {})
    if not isinstance(service, dict):
        return {"errors": ["service must be an object"], "warnings": [], "rows_checked": 0}
    writer, cadence = doc.get("writer", {}), service.get("cadence", {})
    if not isinstance(writer, dict) or not isinstance(cadence, dict):
        return {"errors": ["writer and service.cadence must be objects when supplied"], "warnings": [], "rows_checked": 0}
    if service.get("status") is not None and not isinstance(service["status"], str):
        errors.append("service.status must be a string")
    timestamp_fields(doc, ("updated_at",), errors)
    timestamp_fields(writer, ("lease_expires_at",), errors, "writer.")
    timestamp_fields(service, ("start_at", "expires_at"), errors, "service.")
    timestamp_fields(cadence, ("anchor_at",), errors, "service.cadence.", required=("anchor_at",) if service.get("status") == "active" else ())
    if service.get("status") == "active":
        if type(cadence.get("interval_hours")) is not int or cadence.get("interval_hours") <= 0:
            errors.append("Active service needs an explicit positive integer cadence")
        if type(service.get("window_hours")) is not int or service["window_hours"] <= 0:
            errors.append("Active service needs an explicit positive integer window_hours")
        if not all(nonblank_string(service.get(k)) for k in ("owner", "approval_evidence", "scope_evidence")):
            errors.append("Active service lacks owner, authority or scope evidence")
    policy = doc.get("policy", {})
    if not isinstance(policy, dict):
        policy = {}
    logical_jobs = {}
    for r in rows:
        rid = r.get("release_id")
        def err(s): errors.append(str(rid) + ": " + s)
        if not rid or rid in seen: err("missing or duplicate release_id")
        seen.add(rid)
        if r.get("status") not in STATES: err("invalid status")
        historical = r.get("evidence_level") == "historical"
        if historical or r.get("observed_status") == "unknown":
            warnings.append(str(rid) + ": current state needs live reconciliation")
        s = r.get("scheduler", {})
        jobs = s.get("active_job_ids", [])
        key = (r.get("campaign"), r.get("platform"), r.get("account"), r.get("edition", "initial"))
        logical_jobs.setdefault(key, set()).update((s.get("name"), j) for j in jobs)
        if len(jobs) > 1: err("multiple active jobs for one output")
        if r.get("status") in {"published", "verified"}:
            if not nonblank_string(r.get("actual_post_url")) or not evidence_refs(r.get("evidence_refs")): err("publication lacks URL or evidence")
        if r.get("status") == "scheduled":
            if not nonblank_string(s.get("verification_evidence")): err("scheduled state lacks saved-job evidence")
            if not s.get("job_id"): warnings.append(str(rid) + ": historical job ID unresolved; no retry allowed")
        if r.get("status") == "verified":
            v = r.get("native_verification", {})
            if not nonblank_string(v.get("evidence")): err("verified lacks native inspection")
        prefix = str(rid) + ": "
        row_times = timestamp_fields(r, ("checked_at", "planned_at", "scheduled_at", "actual_publication_at"), errors, prefix, required=("scheduled_at",) if r.get("status") == "scheduled" else ())
        timestamp_fields(r.get("native_verification", {}), ("checked_at",), errors, prefix + "native_verification.", required=("checked_at",) if r.get("status") == "verified" else ())
        timestamp_fields(r.get("approval", {}), ("approved_at",), errors, prefix + "approval.")
        timestamp_fields(r.get("performance", {}), ("observed_at",), errors, prefix + "performance.")
        a = r.get("approval", {})
        if r.get("status") in {"approved", "scheduled"} and a.get("status") != "approved":
            err("approved/scheduled state needs a recorded approval of the exact output")
        if a.get("status") == "approved":
            if not valid_sha256(a.get("bound_asset_sha256")) or a["bound_asset_sha256"] != r.get("asset", {}).get("sha256"): err("approval asset hash does not match")
            if not valid_sha256(a.get("bound_caption_sha256")) or a["bound_caption_sha256"] != r.get("caption_sha256"): err("approval caption hash does not match")
            if not nonblank_string(a.get("evidence")): err("approval lacks evidence")
        flow = r.get("automation", {})
        g = r.get("guide", {})
        guide_required = g.get("required") is True or bool(g.get("pdf_url"))
        if g.get("pdf_sha256") is not None and not valid_sha256(g["pdf_sha256"]):
            err("approved PDF needs a valid SHA-256 fingerprint on every delivery route")
        needs_flow = guide_required and r.get("platform") == "instagram"
        if doc["schema_version"] == 2 and type(g.get("required")) is not bool:
            err("guide.required must explicitly identify whether guide delivery applies")
        config_claimed = flow.get("status") in {"configured", "working"}
        complete = r.get("completion", {})
        guide_completion = guide_required and not needs_flow and (complete.get("delivery") or complete.get("complete"))
        timestamp_fields(g, ("public_pdf_verified_at", "article_journey_verified_at"), errors, prefix + "guide.", required=("public_pdf_verified_at",) if config_claimed or guide_completion else ())
        flow_required = (("configuration_verified_at",) if config_claimed else ()) + (("verified_at",) if flow.get("status") == "working" else ())
        flow_times = timestamp_fields(flow, ("configuration_verified_at", "verified_at"), errors, prefix + "automation.", required=flow_required)
        if config_claimed:
            for field in ("flow_id", "configuration_version", "reel_id", "source_flow_id", "saved_config_evidence", "follower_gate_evidence", "recheck_loop_evidence"):
                if not flow.get(field) or (field.endswith("_evidence") and not nonblank_string(flow[field])): err("configured flow lacks " + field)
            if (not all(nonblank_string(value) for value in (policy.get("source_template"), policy.get("approval_evidence"), flow.get("source_template"))) or flow.get("source_template") != policy.get("source_template")) or flow.get("trigger_scope") != "exact_post" or flow.get("trigger_live") is not True:
                err("configured flow needs approved source-template provenance and a live exact-post trigger")
            if flow.get("follower_gate_verified") is not True or flow.get("recheck_loop_verified") is not True:
                err("configured flow must withhold the resource until following is verified and preserve the recheck loop")
            if not g.get("keyword") or flow.get("keyword") != g.get("keyword"):
                err("flow keyword does not match the approved guide keyword")
            if not g.get("pdf_url") or flow.get("destination_pdf_url") != g.get("pdf_url") or not g.get("pdf_sha256") or flow.get("destination_pdf_sha256") != g.get("pdf_sha256"):
                err("flow destination does not match the approved PDF")
            if not valid_sha256(g.get("pdf_sha256")):
                err("approved PDF needs a valid SHA-256 fingerprint")
            if not nonblank_string(g.get("evidence")):
                err("guide destination lacks public PDF verification")
            if not exact_reel(flow, r):
                err("configured flow is not bound to this exact reel")
        if flow.get("status") == "working":
            if not all(flow.get(k) for k in ("flow_id", "reel_id")) or not all(nonblank_string(flow.get(k)) for k in ("saved_config_evidence", "end_to_end_evidence")):
                err("working flow lacks saved configuration or delivery test")
            if flow.get("end_to_end_pdf_sha256") != g.get("pdf_sha256") or not g.get("pdf_sha256"):
                err("working flow lacks evidence for the exact final guide")
            if not valid_sha256(r.get("asset", {}).get("sha256")) or not g.get("version") or flow.get("end_to_end_binding") != tested_configuration(r):
                err("end-to-end evidence must bind to the exact tested configuration, reel, keyword, gates, guide version and release asset")
            if len(flow_times) == 2 and flow_times["verified_at"] < flow_times["configuration_verified_at"]:
                err("end-to-end evidence predates the current configuration verification")
        if g.get("pdf_url") is not None and not isinstance(g["pdf_url"], str):
            err("guide.pdf_url must be a string")
        elif g.get("pdf_url") and any(x in g["pdf_url"].lower().split("?")[0] for x in (".docx", ".pptx", ".xlsx", ".zip")):
            err("public guide points to an editable/private format")
        c = r.get("comments", {})
        comment_times = timestamp_fields(c, ("latest_comment_check", "last_attempt_at", "next_due_at", "window_end_at"), errors, prefix + "comments.")
        if c.get("latest_comment_check") is not None and not nonblank_string(c.get("latest_success_evidence")):
            err("successful comment check lacks evidence")
        if c.get("coverage") in {"partial", "failed", "not_checked"} and {"latest_comment_check", "last_attempt_at"} <= comment_times.keys() and comment_times["latest_comment_check"] >= comment_times["last_attempt_at"]:
            err("partial/failed attempt cannot become the latest successful check")
        if "actual_publication_at" in row_times:
            try:
                window_hours = service.get("window_hours")
                if type(window_hours) is not int or window_hours <= 0:
                    raise ValueError("Publication comment window requires explicit positive integer service.window_hours")
                expected_end = row_times["actual_publication_at"] + timedelta(hours=window_hours)
                if "window_end_at" in comment_times and comment_times["window_end_at"] > expected_end:
                    err("comment window exceeds configured duration")
            except ValueError as ex: err(str(ex))
            except OverflowError: err("publication comment window is outside the supported timestamp range")
        if needs_flow and complete.get("publication") and not config_claimed:
            err("guide publication handoff lacks verified live configuration")
        if needs_flow and (complete.get("delivery") or complete.get("complete")) and flow.get("status") != "working":
            err("guide delivery completion needs actual end-to-end evidence, not configuration alone")
        if guide_required and not needs_flow and (complete.get("delivery") or complete.get("complete")):
            if not all(g.get(k) for k in ("pdf_url", "pdf_sha256")) or not all(nonblank_string(g.get(k)) for k in ("evidence", "delivery_evidence")) or g.get("delivery_route") not in {"manual_dm", "public_link"}:
                err("non-Instagram guide completion needs verified evidence for its supported delivery route")
            if r.get("platform") == "youtube" and g.get("delivery_route") == "manual_dm":
                err("YouTube has no private guide DM route")
        production = r.get("production", {})
        if production and (not all(production.get(k) for k in ("manifest_sha256", "export_id")) or not nonblank_string(production.get("qa_evidence")) or production.get("export_sha256") != r.get("asset", {}).get("sha256")):
            err("production handoff lacks QA evidence or does not match the release asset")
        if complete.get("complete"):
            if r.get("status") != "verified" or not all(complete.get(k) for k in ("publication", "delivery", "service", "review")) or complete.get("unresolved"):
                err("complete has unresolved or unverified obligations")
    for key, jobs in logical_jobs.items():
        if len(jobs) > 1: errors.append(str(key) + ": duplicate active schedulers/jobs across rows")
    delivered, public = set(), set()
    for e in events:
        if not isinstance(e, dict):
            errors.append("Action events must be objects")
            continue
        timestamp_fields(e, ("timestamp", "slot_due_at"), errors, str(e.get("event_id")) + ": ")
        if e.get("post_url") is not None and not web_url(e["post_url"]):
            errors.append(str(e.get("event_id")) + ": post_url must be a valid HTTP(S) URL without credentials")
        if e.get("acknowledgement_type") == "next_step":
            if (not all(nonblank_string(value) for value in (policy.get("next_step_text"), policy.get("approval_evidence"), e.get("text"))) or e.get("text") != policy.get("next_step_text")) or not nonblank_string(e.get("trigger_evidence")) or not nonblank_string(e.get("follower_gate_evidence")) or e.get("claims_final_delivery"):
                errors.append(str(e.get("event_id")) + ": next-step acknowledgement lacks approved wording/trigger/gate evidence or claims final delivery")
        elif e.get("says_check_your_dm") or e.get("claims_final_delivery"):
            release = next((row for row in rows if row["release_id"] == e.get("release_id")), None)
            binding = requested_guide_binding(release, e)
            verified_send = e.get("delivery_state") == "sent" and bound_guide_evidence(e.get("send_evidence"), binding) and not e.get("claims_final_delivery")
            verified_delivery = e.get("delivery_state") == "delivered" and bound_guide_evidence(e.get("delivery_evidence"), binding)
            verified_receipt = e.get("delivery_state") == "recipient_confirmed" and bound_guide_evidence(e.get("recipient_confirmation_evidence"), binding)
            if not (verified_send or verified_delivery or verified_receipt):
                errors.append(str(e.get("event_id")) + ": DM acknowledgement lacks verified requested-guide send evidence")
        for field, seen_keys in (("dm_delivery_key", delivered), ("public_reply_key", public)):
            k = e.get(field)
            if k and e.get("result") == "success":
                if not isinstance(k, str):
                    errors.append(str(e.get("event_id")) + ": invalid " + field)
                    continue
                if k in seen_keys: errors.append(str(e.get("event_id")) + ": duplicate successful " + field)
                seen_keys.add(k)
    return {"errors": errors, "warnings": warnings, "rows_checked": len(doc.get("releases", []))}

def self_test():
    r = {"release_id": "SYNTHETIC-instagram-test", "campaign": "SYNTHETIC", "platform": "instagram", "account": "synthetic-account",
         "status": "published", "observed_status": "published", "actual_post_url": "https://www.instagram.com/reel/exact/",
         "evidence_refs": ["provider-read"], "scheduler": {"name": "Metricool", "active_job_ids": []}}
    base = {"schema_version": 1, "releases": [r]}
    assert not validate(base)["errors"]
    tests = 1
    for change in (
        {"status": "verified"},
        {"actual_post_url": None},
        {"automation": {"status": "working"}},
        {"scheduler": {"name": "Metricool", "active_job_ids": ["one", "two"]}},
        {"guide": {"pdf_url": "https://example.com/private.pptx"}},
        {"completion": {"complete": True}},
        {"comments": {"latest_comment_check": "2026-09-14T09:00:00+04:00"}},
        {"approval": {"status": "approved", "bound_asset_sha256": "old"}},
        {"actual_publication_at": "2026-09-09T16:00:00+04:00", "comments": {"window_end_at": "2026-09-17T18:00:00+04:00"}}
    ):
        row = copy.deepcopy(r); row.update(change)
        assert validate({"schema_version": 1, "releases": [row]})["errors"], change
        tests += 1
    a = copy.deepcopy(r); a["scheduler"] = {"name": "Metricool", "active_job_ids": ["a"]}
    z = copy.deepcopy(a); z["release_id"] = "renamed-duplicate"; z["scheduler"] = {"name": "Other", "active_job_ids": ["b"]}
    assert validate({"schema_version": 1, "releases": [a,z]})["errors"]; tests += 1
    assert validate(base, [{"event_id":"false-dm","says_check_your_dm":True,"delivery_state":"sent"}])["errors"]; tests += 1
    assert validate(base, [{"event_id":str(i),"result":"success","dm_delivery_key":"same"} for i in (1,2)])["errors"]; tests += 1
    anchor = "2026-09-09T00:00:00+04:00"
    ss = slots("2026-09-09T16:00:00+04:00", anchor=anchor, interval_hours=3, window_hours=168)
    assert len(ss) == 56 and ss[0] == "2026-09-09T18:00:00+04:00" and ss[-1] == "2026-09-16T15:00:00+04:00"; tests += 1
    assert len(slots("2026-09-09T09:00:00+04:00", anchor=anchor, interval_hours=3, window_hours=168)) == 56; tests += 1
    assert all(instant(t) <= instant("2026-09-12T12:00:00+04:00") for t in slots("2026-09-09T16:00:00+04:00","2026-09-12T12:00:00+04:00", anchor=anchor, interval_hours=3, window_hours=168)); tests += 1
    print(json.dumps({"structural_scenarios_passed": tests, "external_actions": 0}))

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tracker", nargs="?")
    p.add_argument("--log")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--slots", help="Confirmed actual publication ISO timestamp")
    p.add_argument("--anchor", help="Existing service's confirmed offset-bearing schedule anchor")
    p.add_argument("--service-start", help="Do not generate slots before this recorded service start")
    p.add_argument("--interval-hours", type=int, help="Explicit authorised cadence")
    p.add_argument("--window-hours", type=int, help="Explicit authorised maximum window")
    p.add_argument("--expires-at", help="Earlier approval/service expiry")
    args = p.parse_args()
    if args.self_test: self_test()
    elif args.slots:
        try: print(json.dumps(slots(args.slots, args.expires_at, anchor=args.anchor, service_start=args.service_start, interval_hours=args.interval_hours, window_hours=args.window_hours), indent=2))
        except (ValueError, TypeError, AttributeError) as ex: p.error(str(ex))
    elif args.tracker:
        try:
            doc = json.loads(Path(args.tracker).read_text(encoding="utf-8-sig"))
            events = [json.loads(line) for line in Path(args.log).read_text(encoding="utf-8-sig").splitlines() if line.strip()] if args.log else []
        except RecursionError:
            p.error("Unreadable tracker or log; JSON nesting exceeds the parser limit; nothing was checked")
        except (OSError, ValueError) as ex:
            p.error("Unreadable tracker or log; nothing was checked: " + str(ex))
        result = validate(doc, events); print(json.dumps(result, indent=2))
        raise SystemExit(bool(result["errors"]))
    else: p.error("Provide tracker, --self-test or --slots")
