"""Offline, read-only scheduled-v1 ingestion. Never authorises an external action.

Default: print counts and requirements, without writing files or printing records.
--out: create a separate private snapshot, exclusively; never replace a source/output.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_guard_spec = importlib.util.spec_from_file_location("content_path_guard", Path(__file__).with_name("path_guard.py"))
path_guard = importlib.util.module_from_spec(_guard_spec)
_guard_spec.loader.exec_module(path_guard)

VERSION = 2
PLATFORMS = {"instagram": "instagram", "linkedin": "linkedin", "LinkedIn": "linkedin",
             "tiktok": "tiktok", "youtube": "youtube"}
PROVIDERS = {"Metricool", "Simplified", "LinkedIn native"}
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")
FIXED_UTC_PLUS_FOUR = timezone(timedelta(hours=4))


class InvalidSource(ValueError):
    """Deliberately safe diagnostics: never include raw record values or paths."""


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def load_bytes(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidSource("Duplicate JSON key; reconcile the source before ingestion")
            result[key] = value
        return result
    def finite(_):
        raise InvalidSource("Non-finite JSON number is unsupported")
    try:
        return json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique, parse_constant=finite)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as ex:
        raise InvalidSource("Source must be valid UTF-8 JSON") from ex


def valid_id(value):
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None


def job_token(value):
    if type(value) is int and value >= 0:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._:/-]{0,199}", value):
        return value
    return None


def post_anchor(value, platform):
    if not isinstance(value, str) or value != value.strip() or any(ord(c) < 32 for c in value):
        return None
    try:
        url = urlsplit(value)
        domains = {"instagram": {"instagram.com", "www.instagram.com"},
                   "linkedin": {"linkedin.com", "www.linkedin.com"},
                   "tiktok": {"tiktok.com", "www.tiktok.com"},
                   "youtube": {"youtube.com", "www.youtube.com", "youtu.be"}}
        if url.scheme != "https" or url.hostname not in domains.get(platform, set()) or url.username or url.password or url.port not in (None, 443):
            return None
        path = unquote(url.path, errors="strict")
        if path.count("/") != url.path.count("/") or "\\" in path:
            return None  # Encoded separators are not a known canonical post form.
        if platform == "instagram":
            match = re.fullmatch(r"/(?:p|reel)/([A-Za-z0-9_-]+)/?", path)
            return "instagram:" + match[1] if match else None
        if platform == "linkedin":
            match = re.fullmatch(r"/feed/update/urn:li:activity:([1-9][0-9]*)/?", path)
            if not match:
                match = re.fullmatch(r"/posts/[A-Za-z0-9_-]+-activity-([1-9][0-9]*)-[A-Za-z0-9_-]+/?", path)
            return "linkedin:activity:" + match[1] if match else None
        if platform == "tiktok":
            match = re.fullmatch(r"/@[A-Za-z0-9._]+/video/([1-9][0-9]*)/?", path)
            return "tiktok:video:" + match[1] if match else None
        if platform == "youtube":
            # Keep video query identity. Do not strip ?v= and collapse all watch URLs.
            if url.hostname == "youtu.be":
                match = re.fullmatch(r"/([A-Za-z0-9_-]{11})/?", path)
                video = match[1] if match else ""
            elif path == "/watch":
                values = parse_qs(url.query, keep_blank_values=True).get("v", [])
                video = values[0] if len(values) == 1 else ""
            elif re.fullmatch(r"/(?:shorts|live)/[A-Za-z0-9_-]{11}/?", path):
                video = path.rstrip("/").rsplit("/", 1)[-1]
            else:
                video = ""
            return "youtube:" + video if re.fullmatch(r"[A-Za-z0-9_-]{11}", video) else None
        return None
    except ValueError:
        return None


def aware_time(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp requires an explicit offset")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamp requires an explicit offset")
    return result.astimezone(timezone.utc).isoformat()


def scheduled_time(value):
    if isinstance(value, str):
        return aware_time(value)
    if isinstance(value, dict) and set(value) == {"dateTime", "timezone"}:
        stamp = value["dateTime"]
        if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", stamp):
            raise ValueError("Unsupported provider dateTime; resolve a verified offset-bearing instant")
        value = {"date": stamp[:10], "time": stamp[11:], "timezone": value["timezone"]}
    if not isinstance(value, dict) or set(value) != {"date", "time", "timezone"} or not all(isinstance(v, str) for v in value.values()):
        raise ValueError("Use offset-bearing ISO time or date/time/timezone fields")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value["date"]) or not re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", value["time"]):
        raise ValueError("Invalid local date/time")
    local = datetime.fromisoformat(value["date"] + "T" + value["time"])
    zone_name = value["timezone"]
    # Modern Asia/Dubai timezone dates have UTC+04 year-round. No third-party tzdata required.
    if zone_name == "Asia/Dubai" and local.year >= 2000:
        zone = FIXED_UTC_PLUS_FOUR
    elif zone_name in {"UTC", "Etc/UTC"}:
        zone = timezone.utc
    else:
        try:
            zone = ZoneInfo(zone_name)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as ex:
            raise ValueError("Timezone database unavailable or zone unknown; supply a verified offset-bearing instant") from ex
    candidates = set()
    for fold in (0, 1):
        candidate = local.replace(tzinfo=zone, fold=fold)
        utc = candidate.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == local:
            candidates.add(utc)
    if len(candidates) != 1:
        raise ValueError("Ambiguous or nonexistent local time; obtain a verified offset-bearing instant")
    return candidates.pop().astimezone(timezone.utc).isoformat()


def convert(source, namespace, source_sha256):
    """Return a lossless-source snapshot plus an explicitly unverified projection."""
    if not valid_id(namespace):
        raise InvalidSource("Namespace must be a stable non-secret identifier (1-200 ASCII ID characters)")
    if not isinstance(source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
        raise InvalidSource("Source fingerprint must be SHA-256")
    if not isinstance(source, dict):
        raise InvalidSource("Tracker must be an object")
    if "adapter" in source:
        meta = source.get("adapter")
        if not isinstance(meta, dict) or meta.get("version") != VERSION or meta.get("namespace") != namespace:
            raise InvalidSource("Unsupported snapshot or namespace mismatch")
        original = meta.get("source_document")
        if not isinstance(original, dict) or "adapter" in original:
            raise InvalidSource("Invalid nested snapshot")
        expected = convert(original, namespace, meta.get("source_sha256"))
        if expected != source:
            raise InvalidSource("Snapshot differs from its deterministic source projection; reconcile edits separately")
        return copy.deepcopy(source)
    if type(source.get("schema_version")) is not int or source["schema_version"] != 1 or "releases" in source:
        raise InvalidSource("Only canonical scheduled schema_version 1 is supported")
    rows = source.get("scheduled")
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        raise InvalidSource("Expected a non-empty scheduled array of objects")
    output = {"schema_version": 2, "releases": [], "service": {"status": "unreconciled"},
              "adapter": {"version": VERSION, "mode": "read_only_snapshot", "namespace": namespace,
                          "source_sha256": source_sha256, "source_document_sha256": digest(source),
                          "source_document": copy.deepcopy(source)}}
    identities, anchors = defaultdict(list), defaultdict(list)
    for index, original in enumerate(rows):
        requirements = []
        def need(code, actions, requirement):
            if not any(item["code"] == code for item in requirements):
                requirements.append({"code": code, "blocks": actions, "requirement": requirement})
        platform = PLATFORMS.get(original.get("platform")) if isinstance(original.get("platform"), str) else None
        provider = original.get("scheduler")
        if not isinstance(provider, str) or provider not in PROVIDERS:
            provider = "unknown"
            need("scheduler_unknown", ["schedule", "publish"], "Resolve the authoritative scheduler; do not create a replacement job.")
        if platform is None:
            platform = "unknown"
            need("platform_unknown", ["all_external"], "Resolve the platform explicitly; do not guess from case or whitespace.")
        legacy = original.get("_full_legacy_record", {})
        if not isinstance(legacy, dict):
            legacy = {}
            need("legacy_malformed", ["all_external"], "Reconcile the malformed archived record with its owner.")
        archived_scheduler = legacy.get("scheduler", {})
        if not isinstance(archived_scheduler, dict):
            archived_scheduler = {}
            need("scheduler_malformed", ["schedule", "publish"], "Reconcile the archived scheduler object.")
        if archived_scheduler.get("name") not in (None, provider):
            need("scheduler_conflict", ["schedule", "publish"], "Resolve disagreement between current provider label and archived provider.")
        for field in ("release_id", "platform", "account"):
            if field in legacy and field in original and legacy[field] != original[field]:
                need("legacy_identity_conflict", ["all_external"], "Reconcile conflicting identities; do not silently choose the archived record.")
        source_job = original.get("id")
        archived_job = archived_scheduler.get("job_id")
        job = job_token(source_job) if source_job is not None else job_token(archived_job)
        if source_job is not None and archived_job is not None and job_token(source_job) != job_token(archived_job):
            need("job_conflict", ["all_external"], "Resolve conflicting scheduler job identifiers.")
        uuid = job_token(original.get("uuid"))
        for value in (source_job, archived_job, original.get("uuid")):
            if value is not None and job_token(value) is None:
                need("job_id_malformed", ["all_external"], "Resolve malformed provider identifiers without publishing again.")
        url_anchor = post_anchor(original.get("actual_post_url"), platform)
        if original.get("actual_post_url") is not None and url_anchor is None:
            need("native_identity_unresolved", ["all_external"], "Resolve the native media ID from an authoritative post URL; this URL form is not a supported stable identity.")
        identity_anchors = [("job", job), ("uuid", uuid), ("post", url_anchor)]
        for kind, value in identity_anchors:
            if value is not None:
                # Account is intentionally excluded: missing accounts cannot hide job duplicates.
                anchors[(platform, provider if kind != "post" else "native", kind, value)].append(index)
        existing_id = original.get("release_id")
        if valid_id(existing_id):
            rid, basis = existing_id, "source_release_id"
        else:
            if existing_id is not None:
                need("release_id_malformed", ["all_external"], "Review the invalid original ID and approve its identity mapping.")
            basis, value = next(((kind, val) for kind, val in identity_anchors if val is not None), ("unresolved_row", digest(original)))
            identity_provider = "native" if basis == "post" else provider
            rid = "import-" + digest(["scheduled-v1-identity", namespace, platform, identity_provider, basis, value])
            need("identity_mapping_review", ["all_external"], "Review and persist this proposed release ID in the canonical writer before using it for actions.")
            if basis == "unresolved_row":
                need("identity_unresolved", ["all_external"], "No stable job, UUID or native-post identity exists; this diagnostic ID must not identify an actionable release.")
        identities[rid].append(index)
        row = {"release_id": rid, "platform": platform,
               "status": "unknown", "observed_status": "unknown", "evidence_level": "historical",
               "last_known_status": copy.deepcopy(original.get("status")),
               "scheduler": {"name": provider, "job_id": job},
               "guide": {"required": None}, "automation": {"status": "unreconciled"},
               "completion": {"complete": False},
               "ingestion": {"source_index": index, "source_pointer": "/scheduled/" + str(index),
                             "source_entry_sha256": digest(original), "identity_basis": basis,
                             "requirements": requirements}}
        # Copy descriptive identity only. Old verification/approval/delivery claims remain
        # losslessly in source_document; none are silently upgraded to current evidence.
        for field in ("campaign", "account", "edition", "title", "topic", "actual_post_url"):
            value = original.get(field)
            if isinstance(value, str) and value.strip():
                row[field] = value
        time_value = original.get("scheduled_at") if "_full_legacy_record" in original else original.get("date")
        if time_value is not None:
            try:
                row["scheduled_at"] = scheduled_time(time_value)
            except (ValueError, TypeError, OverflowError):
                need("schedule_time_unresolved", ["schedule", "publish"], "Resolve the saved job's exact offset-bearing instant; local time may be ambiguous or its timezone unavailable.")
        else:
            need("schedule_time_unknown", ["schedule", "publish"], "Inspect the original job for its scheduled instant; an old publication date is not a schedule.")
        if not row.get("account"):
            need("account_unknown", ["all_external"], "Verify the exact configured account against the original job/native post.")
        need("source_evidence_unreconciled", ["all_external"], "Resolve current handoffs, canonical revision, single writer and live evidence; this historical snapshot is not an action queue.")
        need("publication_unknown", ["publish", "bind_flow", "complete"], "Inspect the existing job and native post; record exact account, asset, caption, URL and current observation. Never retry from absence alone.")
        need("approval_unknown", ["schedule", "publish"], "Confirm applicable approval for the exact asset/caption hashes, account, instant and guide destination.")
        need("guide_applicability_unknown", ["publish", "deliver_guide", "complete"], "Record whether this release offers a guide from its approved content. If yes, verify exact keyword, version, public PDF and hash.")
        if platform == "instagram":
            need("guide_flow_unreconciled", ["bind_flow", "deliver_guide", "complete"], "For guide campaigns verify the exact live post trigger, approved source-template copy, follower gate and recheck loop; actual end-to-end evidence is separate from configuration.")
        need("reply_service_unreconciled", ["reply", "deliver_guide", "complete"], "Resolve explicitly authorised supported-cadence runner, owner, anchor, scope and expiry; inspect full comment and delivery history for duplicates.")
        output["releases"].append(row)
    for groups, code, message in ((identities, "duplicate_release_id", "Reconcile duplicate release IDs; no row was dropped or suffixed."),
                                  (anchors, "duplicate_native_identity", "Reconcile rows referring to the same provider job, UUID or native post before any action.")):
        for indices in groups.values():
            if len(indices) > 1:
                for index in indices:
                    reqs = output["releases"][index]["ingestion"]["requirements"]
                    if not any(r["code"] == code for r in reqs):
                        reqs.append({"code": code, "blocks": ["all_external"], "requirement": message})
    return output


def summary(snapshot):
    rows = snapshot["releases"]
    counts = Counter(r["code"] for row in rows for r in row["ingestion"]["requirements"])
    instructions = {r["code"]: r["requirement"] for row in rows for r in row["ingestion"]["requirements"]}
    return {"adapter_version": VERSION, "ingested": True, "source_rows": len(rows), "converted_rows": len(rows),
            "preserved_ids": sum(r["ingestion"]["identity_basis"] == "source_release_id" for r in rows),
            "proposed_ids": sum(r["ingestion"]["identity_basis"] != "source_release_id" for r in rows),
            "live_ready": False, "external_actions_permitted": False,
            "requirements": [{"code": code, "rows": count, "requirement": instructions[code]} for code, count in sorted(counts.items())]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--namespace", required=True, help="Stable workflow ID; reuse it across runs, never a credential/path")
    p.add_argument("--out", type=Path, help="Optional NEW private snapshot; contains source records, keep outside Git and AI uploads")
    args = p.parse_args()
    try:
        # Validate output syntax BEFORE filesystem access; NTFS streams are not
        # separate files, even when their unnamed source bytes remain unchanged.
        out = path_guard.checked_path(args.out, new_file=True) if args.out is not None else None
        path_guard.validate_path_text(args.source)
        source = args.source.resolve(strict=True)
        data = source.read_bytes()
        snapshot = convert(load_bytes(data), args.namespace, hashlib.sha256(data).hexdigest())
        if source.read_bytes() != data:
            raise InvalidSource("Source changed during ingestion; discard this view and retry after writer reconciliation")
        if out is not None:
            path_guard.checked_path(out, new_file=True)
            with out.open("xb") as handle:
                handle.write(encoded(snapshot) + b"\n")
        report = summary(snapshot)
        report.update(source_unchanged=source.read_bytes() == data, output_written=args.out is not None)
        if not report["source_unchanged"]:
            raise InvalidSource("Source changed during ingestion; output is stale and must not be used")
        print(json.dumps(report, indent=2))
        # 0 = ingestion only, NEVER permission. 1 is invalid/unreadable input/output.
        return 0
    except (InvalidSource, OSError, ValueError, RecursionError) as ex:
        print(json.dumps({"ingested": False, "live_ready": False, "external_actions_permitted": False,
                          "error": str(ex) if isinstance(ex, (InvalidSource, path_guard.UnsafePath)) else "Ingestion refused: malformed source or unavailable file/output. Use readable UTF-8 JSON and a new separate output path."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
