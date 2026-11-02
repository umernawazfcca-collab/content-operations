"""Synthetic evidence-time/URL/type regressions; no live records or network."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from test_checks import records, tracker, SKILL, temporary_directory


BAD_TIMES = ("", " \t\n", "not-a-time", "2026-10-31", "2026-10-31T06:00:00",
             "2026-02-30T06:00:00Z", "2026-10-31T06:00:00+25:00",
             42, 0, True, False, [], {}, ["2026-10-31T06:00:00Z"])
GOOD_TIMES = ("2026-10-31T06:00:00Z", "2026-10-31T10:00:00+04:00",
              "2026-10-31T01:00:00-05:00", "2026-10-31T11:45:00.000000+05:45")


def planned():
    return {"schema_version": 2, "service": {"window_hours": 168}, "releases": [{
        "release_id": "synthetic-planned", "platform": "instagram", "status": "planned",
        "guide": {"required": False}, "observed_status": "unknown", "evidence_level": "historical"}]}


def set_path(doc, path, value):
    node = doc
    for part in path[:-1]:
        if isinstance(node, dict):
            node = node.setdefault(part, {})
        else:
            node = node[part]
    node[path[-1]] = value


ROW = ("releases", 0)
OPTIONAL_TIMES = [("updated_at",), ("writer", "lease_expires_at"), ("service", "start_at"),
                  ("service", "expires_at"), ("service", "cadence", "anchor_at")]
OPTIONAL_TIMES += [ROW + (field,) for field in ("checked_at", "planned_at", "scheduled_at", "actual_publication_at")]
OPTIONAL_TIMES += [ROW + (section, field) for section, field in (
    ("approval", "approved_at"), ("native_verification", "checked_at"),
    ("guide", "public_pdf_verified_at"), ("guide", "article_journey_verified_at"),
    ("automation", "configuration_verified_at"), ("automation", "verified_at"),
    ("comments", "latest_comment_check"), ("comments", "last_attempt_at"),
    ("comments", "next_due_at"), ("comments", "window_end_at"), ("performance", "observed_at"))]


def required_cases():
    yield "native inspection", tracker(), ROW + ("native_verification", "checked_at")
    doc = planned()
    doc["releases"][0].update(status="scheduled", scheduled_at=GOOD_TIMES[0],
        asset={"sha256": "a" * 64}, caption_sha256="b" * 64,
        approval={"status": "approved", "bound_asset_sha256": "a" * 64,
                  "bound_caption_sha256": "b" * 64, "evidence": "synthetic-approval"},
        scheduler={"verification_evidence": "synthetic-saved-job", "job_id": "synthetic-job"})
    yield "scheduled job", doc, ROW + ("scheduled_at",)
    for status in ("configured", "working"):
        doc = tracker()
        row = doc["releases"][0]
        row["automation"]["status"] = status
        if status == "configured":
            row["completion"] = {"publication": True}
        yield status + " PDF", copy.deepcopy(doc), ROW + ("guide", "public_pdf_verified_at")
        yield status + " configuration", copy.deepcopy(doc), ROW + ("automation", "configuration_verified_at")
        if status == "working":
            yield "delivery test", doc, ROW + ("automation", "verified_at")
    for platform in ("linkedin", "tiktok", "youtube"):
        doc = tracker()
        row = doc["releases"][0]
        row.update(platform=platform, automation={})
        row["guide"].update(delivery_route="public_link", delivery_evidence="synthetic-delivery")
        yield platform + " final guide", doc, ROW + ("guide", "public_pdf_verified_at")
    doc = planned()
    doc["service"] = {"status": "active", "owner": "synthetic-owner", "approval_evidence": "synthetic-approval",
                      "scope_evidence": "synthetic-scope", "window_hours": 168,
                      "cadence": {"interval_hours": 3, "anchor_at": GOOD_TIMES[0]}}
    yield "active service anchor", doc, ("service", "cadence", "anchor_at")


def rebind(doc):
    row = doc["releases"][0]
    if row.get("automation", {}).get("status") == "working":
        # Synthetic bindings deliberately refreshed so stale-binding rejection
        # cannot mask a broken field validator. Never do this to live evidence.
        row["automation"]["end_to_end_binding"] = records.tested_configuration(row)


class RecordTypeTests(unittest.TestCase):
    def assert_invalid_unchanged(self, doc, events=()):
        before = copy.deepcopy((doc, events))
        first = records.validate(doc, events)
        self.assertTrue(first["errors"])
        self.assertEqual(first, records.validate(doc, events))
        self.assertEqual((doc, events), before)

    def test_required_evidence_instants_reject_all_malformed_types(self):
        for name, original, path in required_cases():
            for value in (None, *BAD_TIMES):
                with self.subTest(claim=name, value=value):
                    doc = copy.deepcopy(original)
                    set_path(doc, path, value)
                    rebind(doc)
                    self.assert_invalid_unchanged(doc)
            doc = copy.deepcopy(original)
            node = doc
            for part in path[:-1]:
                node = node[part]
            del node[path[-1]]
            rebind(doc)
            self.assert_invalid_unchanged(doc)

    def test_required_evidence_accepts_equivalent_offset_instants(self):
        for name, original, path in required_cases():
            for value in GOOD_TIMES:
                with self.subTest(claim=name, value=value):
                    doc = copy.deepcopy(original)
                    set_path(doc, path, value)
                    rebind(doc)
                    before = copy.deepcopy(doc)
                    self.assertEqual(records.validate(doc)["errors"], [])
                    self.assertEqual(doc, before)

    def test_optional_instants_reject_falsey_and_nonstring_supplied_values(self):
        for path in OPTIONAL_TIMES:
            for value in BAD_TIMES:
                with self.subTest(path=path, value=value):
                    doc = planned()
                    set_path(doc, path, value)
                    self.assert_invalid_unchanged(doc)

    def test_optional_instants_preserve_unknown_and_historical_records(self):
        self.assertFalse(records.validate(planned())["errors"])
        for path in OPTIONAL_TIMES:
            for value in (None, *GOOD_TIMES):
                with self.subTest(path=path, value=value):
                    doc = planned()
                    set_path(doc, path, value)
                    doc["releases"][0].setdefault("comments", {})["latest_success_evidence"] = "synthetic-scan"
                    self.assertFalse(records.validate(doc)["errors"])
        template = json.loads((SKILL / "templates/release-tracker.template.json").read_text(encoding="utf-8"))
        self.assertFalse(records.validate(template)["errors"])

    def test_event_instants_and_post_urls_are_validated_without_mutation(self):
        for field in ("timestamp", "slot_due_at"):
            for value in BAD_TIMES:
                with self.subTest(field=field, value=value):
                    self.assert_invalid_unchanged(planned(), [{field: value}])
            for value in (None, *GOOD_TIMES):
                self.assertFalse(records.validate(planned(), [{field: value}])["errors"])
        self.assert_invalid_unchanged(planned(), [{"post_url": "https://[invalid"}])
        self.assertFalse(records.validate(planned(), [{"post_url": "https://example.com/post/1"}])["errors"])

    def test_url_syntax_errors_are_structured_even_with_matching_native_id(self):
        paths = [ROW + ("actual_post_url",)] + [ROW + pair for pair in (
            ("asset", "remote_url"), ("guide", "article_url"), ("guide", "pdf_url"),
            ("automation", "flow_url"), ("automation", "destination_pdf_url"))]
        malformed = ("https://[invalid", "https://[vX.invalid]/", "https://example.com:bad/x",
                     "https://example.com:65536/x", "https:///post", "relative/post", " ", "",
                     "https://example.com/\npost", "https://user:secret@example.com/post",
                     "file:///tmp/post", 42, False, [], {})
        for path in paths:
            for value in malformed:
                with self.subTest(path=path, value=value):
                    doc = planned()
                    set_path(doc, path, value)
                    self.assert_invalid_unchanged(doc)
            for value in (None, "http://example.com/post", "https://example.com:8443/p?q=1#section", "https://[::1]/p"):
                doc = planned()
                set_path(doc, path, value)
                self.assertFalse(records.validate(doc)["errors"])
        doc = tracker()
        doc["releases"][0].update(actual_post_url="https://[invalid", native_media_id="exact")
        rebind(doc)
        self.assert_invalid_unchanged(doc)

    def test_nested_enum_types_never_escape_as_tracebacks(self):
        paths = [("service", "status")] + [ROW + pair for pair in (
            ("approval", "status"), ("automation", "status"), ("comments", "coverage"), ("guide", "delivery_route"))]
        for path in paths:
            for value in ([], {}, ["working"], 42, True, False, 0):
                with self.subTest(path=path, value=value):
                    doc = planned()
                    set_path(doc, path, value)
                    self.assert_invalid_unchanged(doc)
            doc = planned()
            set_path(doc, path, None)
            self.assertFalse(records.validate(doc)["errors"])

    def test_publication_window_bounds_compare_instants_and_report_overflow(self):
        doc = planned()
        doc["service"]["window_hours"] = 1
        doc["releases"][0].update(actual_publication_at="2026-10-31T11:30:00+05:30",
                                   comments={"window_end_at": "2026-10-31T07:00:00Z"})
        self.assertFalse(records.validate(doc)["errors"])
        doc["releases"][0]["comments"]["window_end_at"] = "2026-10-31T07:00:01Z"
        self.assert_invalid_unchanged(doc)
        doc["releases"][0]["actual_publication_at"] = "9999-12-31T23:59:59Z"
        self.assert_invalid_unchanged(doc)

    def test_cli_field_errors_exit_one_with_json_and_preserve_inputs(self):
        cases = []
        for name, doc, path in required_cases():
            set_path(doc, path, 42)
            rebind(doc)
            cases.append((doc, []))
        for path, value in ((ROW + ("actual_post_url",), "https://[invalid"),
                            (ROW + ("automation", "status"), []),
                            (ROW + ("comments", "coverage"), {}),
                            (ROW + ("guide", "delivery_route"), []),
                            (ROW + ("actual_publication_at",), False)):
            doc = planned()
            set_path(doc, path, value)
            cases.append((doc, []))
        cases.append((planned(), [{"timestamp": False}]))
        cases.append((planned(), [{"post_url": "https://[invalid"}]))
        with temporary_directory() as folder:
            folder = Path(folder)
            for index, (doc, events) in enumerate(cases + [(tracker(), [])]):
                with self.subTest(case=index):
                    source, log = folder / "tracker.json", folder / "actions.jsonl"
                    source.write_bytes(json.dumps(doc).encode("utf-8"))
                    log.write_bytes("\n".join(json.dumps(event) for event in events).encode("utf-8"))
                    before = {p.name: p.read_bytes() for p in folder.iterdir()}
                    command = [sys.executable, "-B", str(SKILL / "scripts/check_records.py"), str(source), "--log", str(log)]
                    results = [subprocess.run(command, capture_output=True, text=True) for _ in range(2)]
                    expected = 0 if index == len(cases) else 1
                    for result in results:
                        self.assertEqual(result.returncode, expected, result.stderr)
                        self.assertEqual(bool(json.loads(result.stdout)["errors"]), bool(expected))
                        self.assertEqual(result.stderr, "")
                    self.assertEqual(results[0].stdout, results[1].stdout)
                    self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)


if __name__ == "__main__":
    unittest.main()
