"""Check an explicit local planning snapshot. Never grants release or send authority."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit


def text(value):
    return isinstance(value, str) and bool(value.strip())


def instant(value):
    if not text(value):
        raise ValueError("offset-bearing timestamp required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("offset-bearing timestamp required")
    return result.astimezone(timezone.utc)


FIELDS = {
    "brand": "schema_version brand_id revision status audience positioning language voice_examples avoid forbidden_claims asset_policy_ref approval_evidence",
    "claims": "schema_version brand_id revision claims",
    "brief": "schema_version brief_id brand_id brand_revision claims_revision status evidence audience problem goal claim_ids channels creative_spec_ref hook_options call_to_action success_metric production_effort release_id",
    "policies": "schema_version brand_id records",
    "claim": "claim_id status statement conditions source_ref verified_at valid_until allowed_channels approval_evidence",
    "evidence": "source_ref observed_at captured_at valid_until",
    "channel": "platform account_ref community policy_ref",
    "policy": "policy_id platform account_ref community status checked_at review_due_at source_urls posting_mode comment_mode promotion_rule ai_content_rule flair_rule notes",
}


def validate(brand, claims, brief, policies, *, as_of=None):
    errors = []
    now = as_of if as_of is not None else datetime.now(timezone.utc)
    try:
        now = instant(now.isoformat())
    except (ValueError, TypeError, AttributeError, OverflowError):
        return {"errors": ["as_of: timezone-aware datetime required"], "ready_for_drafting": False,
                "release_authorized": False, "live_state_verified": False}

    def obj(value, kind, label):
        if not isinstance(value, dict):
            errors.append(label + ": object required")
            return {}
        allowed = set(FIELDS[kind].split())
        if set(value) != allowed:
            errors.append(label + ": fields must match the versioned template (no extra authority fields)")
        return value

    def required(value, keys, label):
        for key in keys.split():
            if not text(value.get(key)):
                errors.append(label + ": nonblank " + key + " required")

    def rows(value, label, *, nonempty=True):
        if not isinstance(value, list) or (nonempty and not value):
            errors.append(label + ": " + ("nonempty " if nonempty else "") + "array required")
            return []
        return value

    def strings(value, label, *, nonempty=True):
        result = rows(value, label, nonempty=nonempty)
        if any(not text(v) for v in result):
            errors.append(label + ": nonblank strings required")
        return [v for v in result if text(v)]

    def fresh(value, start_key, end_key, label):
        try:
            start, end = instant(value.get(start_key)), instant(value.get(end_key))
            if not start <= now < end:
                raise ValueError("future observation or expired evidence")
            return start, end
        except (ValueError, TypeError, OverflowError):
            errors.append(label + ": valid current " + start_key + "/" + end_key + " required")
            return None

    documents = {}
    for kind, raw in (("brand", brand), ("claims", claims), ("brief", brief), ("policies", policies)):
        doc = obj(raw, kind, kind)
        documents[kind] = doc
        if type(doc.get("schema_version")) is not int or doc.get("schema_version") != 1:
            errors.append(kind + ": unsupported schema_version")
        required(doc, "brand_id", kind)
    brand, claims, brief, policies = (documents[k] for k in ("brand", "claims", "brief", "policies"))
    if any(doc.get("brand_id") != brand.get("brand_id") for doc in documents.values()):
        errors.append("All planning documents must have the same explicit brand_id")
    required(brand, "revision audience positioning language asset_policy_ref approval_evidence", "brand")
    for key in ("voice_examples", "avoid", "forbidden_claims"):
        strings(brand.get(key), "brand." + key, nonempty=key == "voice_examples")
    if brand.get("status") != "approved":
        errors.append("brand: owner-approved context required for drafting")
    required(claims, "revision", "claims")
    required(brief, "brief_id brand_revision claims_revision audience problem goal creative_spec_ref call_to_action success_metric production_effort", "brief")
    if brief.get("brand_revision") != brand.get("revision") or brief.get("claims_revision") != claims.get("revision"):
        errors.append("brief: pinned brand and claim revisions must match supplied current records")
    if brief.get("status") != "ready_for_drafting" or brief.get("release_id") is not None:
        errors.append("brief: ready_for_drafting with release_id null required; releases use the release protocol")
    hooks = strings(brief.get("hook_options"), "brief.hook_options")
    if len(hooks) != 3 or len(set(hooks)) != 3:
        errors.append("brief: three distinct hook options required")
    for i, raw in enumerate(rows(brief.get("evidence"), "brief.evidence")):
        label = "evidence " + str(i)
        row = obj(raw, "evidence", label)
        required(row, "source_ref", label)
        period = fresh(row, "observed_at", "valid_until", label)
        try:
            captured = instant(row.get("captured_at"))
            if period and not period[0] <= captured <= now:
                raise ValueError("capture must follow observation and not be future-dated")
        except (ValueError, TypeError, OverflowError):
            errors.append(label + ": valid captured_at required")

    claim_map = {}
    for raw in rows(claims.get("claims"), "claims.claims", nonempty=False):
        row = obj(raw, "claim", "claim")
        key = row.get("claim_id")
        if not text(key) or key in claim_map:
            errors.append("claim: unique nonblank claim_id required")
            continue
        claim_map[key] = row
        if row.get("status") not in ("proposed", "approved", "revoked"):
            errors.append(key + ": invalid claim status")
    selected = strings(brief.get("claim_ids"), "brief.claim_ids", nonempty=False)
    if len(set(selected)) != len(selected):
        errors.append("brief: duplicate claim IDs")
    channel_rows = [obj(r, "channel", "channel") for r in rows(brief.get("channels"), "brief.channels")]
    for key in selected:
        row = claim_map.get(key)
        if row is None:
            errors.append(key + ": unknown claim")
            continue
        required(row, "statement conditions source_ref approval_evidence", key)
        if row.get("status") != "approved":
            errors.append(key + ": selected claim is not approved or has been revoked")
        fresh(row, "verified_at", "valid_until", key)
        allowed = strings(row.get("allowed_channels"), key + ".allowed_channels")
        if any(channel.get("platform") not in allowed for channel in channel_rows):
            errors.append(key + ": claim not allowed on every proposed channel")

    policy_map = {}
    for raw in rows(policies.get("records"), "policies.records"):
        row = obj(raw, "policy", "policy")
        key = row.get("policy_id")
        if not text(key) or key in policy_map:
            errors.append("policy: unique nonblank policy_id required")
            continue
        policy_map[key] = row
    seen = set()
    for channel in channel_rows:
        required(channel, "platform account_ref policy_ref", "channel")
        if channel.get("platform") not in ("instagram", "linkedin", "facebook", "tiktok", "youtube", "reddit", "wordpress", "google_business_profile", "newsletter"):
            errors.append("channel: unsupported or noncanonical platform name")
        if not isinstance(channel.get("community"), str):
            errors.append("channel: community must be a string (empty outside a community)")
        binding = tuple(channel.get(k) for k in ("platform", "account_ref", "community"))
        if not all(isinstance(v, str) for v in binding):
            continue
        if binding in seen:
            errors.append("brief: duplicate channel/account/community")
        seen.add(binding)
        key = channel.get("policy_ref")
        row = policy_map.get(key) if text(key) else None
        if row is None:
            errors.append("channel: unknown policy_ref")
            continue
        if tuple(row.get(k) for k in ("platform", "account_ref", "community")) != binding:
            errors.append("channel: policy must bind to exact platform/account/community")
        if row.get("status") != "reviewed":
            errors.append("policy: reviewed record required")
        fresh(row, "checked_at", "review_due_at", "policy")
        urls = strings(row.get("source_urls"), "policy.source_urls")
        def valid_url(url):
            try:
                parsed = urlsplit(url)
                return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
            except ValueError:
                return False
        if any(not valid_url(u) for u in urls):
            errors.append("policy: HTTPS source URLs required")
        if row.get("posting_mode") not in ("draft_only", "human_only", "provider_review_required"):
            errors.append("policy: unsupported posting mode")
        if row.get("comment_mode") not in ("draft_only", "human_only", "provider_review_required"):
            errors.append("policy: unsupported comment mode")
        if channel.get("platform") == "linkedin" and row.get("comment_mode") != "human_only":
            errors.append("LinkedIn comments require human posting; routine approval cannot enable automated comments")
        if channel.get("platform") == "reddit":
            required(row, "community promotion_rule ai_content_rule flair_rule", "Reddit policy")
            if not channel.get("community", "").startswith("r/"):
                errors.append("Reddit: exact r/community required")
            def community_url(url):
                if not valid_url(url):
                    return False
                parsed = urlsplit(url)
                return (parsed.hostname == "reddit.com" or parsed.hostname.endswith(".reddit.com")) and parsed.path.lower().startswith('/r/' + channel.get('community', '')[2:].lower() + '/')
            if not any(community_url(u) for u in urls):
                errors.append("Reddit: include the exact community rules URL")

    fingerprint = hashlib.sha256(json.dumps(documents, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return {"errors": errors, "ready_for_drafting": not errors, "release_authorized": False,
            "live_state_verified": False, "checked_at": now.isoformat(), "snapshot_sha256": fingerprint,
            "limitations": "Structural snapshot check only; does not verify truth, permissions, source freshness in the service, claim coverage in draft text or approval authenticity."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("brand", "claims", "brief", "policies"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--as-of", help="Offset-bearing instant for reproducible offline review; defaults to current UTC")
    args = parser.parse_args()
    try:
        spec = importlib.util.spec_from_file_location("planning_path_guard", Path(__file__).with_name("path_guard.py"))
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        docs = []
        for key in ("brand", "claims", "brief", "policies"):
            path = guard.checked_path(getattr(args, key))
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Planning input exceeds the 2 MiB per-document limit")
            docs.append(json.loads(path.read_text(encoding="utf-8")))
        result = validate(*docs, as_of=instant(args.as_of) if args.as_of else None)
    except (OSError, ValueError, TypeError, RecursionError, OverflowError):
        print(json.dumps({"errors": ["Invalid or unreadable planning input; use the versioned templates and offset-bearing dates"],
                          "ready_for_drafting": False, "release_authorized": False, "live_state_verified": False}))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
