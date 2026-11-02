"""Offline packaged smoke check. Does not inspect accounts, upload data or start jobs."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path


def require(condition):
    if not condition:
        raise RuntimeError("Offline smoke expectation failed")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="unknown", choices=("unknown", "codex", "chatgpt", "claude-chat", "claude-code", "gemini-app", "gemini-cli"))
    args = p.parse_args()
    if sys.version_info < (3, 10):
        print(json.dumps({"passed": False, "reason": "Python 3.10+ required; do not install packages automatically"}))
        return 1
    try:
        from adapt_tracker import convert, digest, summary
        from check_records import validate, slots
        from check_production import validate as production_validate
        synthetic = {"schema_version": 1, "scheduled": [{"platform": "linkedin", "scheduler": "Simplified", "id": 101,
                     "date": {"date": "2026-11-01", "time": "08:00", "timezone": "Asia/Dubai"}, "status": "PENDING"}]}
        result = convert(synthetic, "synthetic-smoke", digest(synthetic))
        require(summary(result)["converted_rows"] == 1 and not summary(result)["live_ready"])
        require(validate(result)["errors"] and validate(result)["rows_checked"] == 1)
        review = {"schema_version": 2, "policy": {"next_step_text": "Synthetic next-step notice.", "approval_evidence": "synthetic-policy"},
                  "releases": [{"release_id": "synthetic-review", "platform": "instagram", "status": "planned", "guide": {"required": False}}]}
        event = {"acknowledgement_type": "next_step", "text": "Synthetic next-step notice.", "trigger_evidence": "synthetic-trigger", "follower_gate_evidence": "synthetic-gate"}
        require(not validate(review, [event])["errors"])
        for value in (" \t\n", 42, True, {"ref": "synthetic"}, ["synthetic"]):
            review["policy"]["approval_evidence"] = value
            require(validate(review, [event])["errors"])
        review["policy"]["approval_evidence"] = "synthetic-policy"
        for value in (" \t\n", True, ["synthetic"]):
            require(validate(review, [dict(event, follower_gate_evidence=value)])["errors"])
        review["releases"][0]["status"] = "approved"
        require(validate(review)["errors"])
        review["releases"][0]["status"] = "planned"
        require(not validate(review)["errors"])
        for field, value in (("actual_publication_at", False), ("native_verification", {"checked_at": 42}),
                             ("actual_post_url", "https://[invalid"), ("automation", {"status": []})):
            malformed = dict(review, releases=[dict(review["releases"][0], **{field: value})])
            require(validate(malformed)["errors"])
        require(slots("2026-11-01T08:00:00+04:00", "2026-11-01T14:00:00+04:00", anchor="2026-11-01T09:00:00+04:00", interval_hours=3, window_hours=168) == ["2026-11-01T09:00:00+04:00", "2026-11-01T12:00:00+04:00"])
        root = Path(__file__).resolve().parents[1]
        template = json.loads((root / "templates/production-manifest.template.json").read_text(encoding="utf-8"))
        require(production_validate(template, root)["errors"])
        require((root / "references/portable-hosts.md").is_file())
    except (RuntimeError, ImportError, OSError, ValueError) as ex:
        print(json.dumps({"passed": False, "failure_type": type(ex).__name__, "external_actions_permitted": False}))
        return 1
    print(json.dumps({"passed": True, "python": sys.version.split()[0], "declared_host": args.host,
                      "exercised": ["offline_adapter", "blocked_imported_evidence", "malformed_policy_rejection", "malformed_gate_evidence_rejection", "unapproved_state_rejection", "malformed_timestamp_rejection", "malformed_url_rejection", "nested_status_type_rejection", "configured_slots", "blank_production_rejection", "packaged_references"],
                      "host_import_or_activation_verified": False, "live_integrations_tested": False,
                      "external_actions_permitted": False, "capabilities": "unknown_until_discovered_in_this_session"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
