"""Synthetic structural variants only; no live records, accounts or private paths."""
import copy
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError
from zoneinfo import ZoneInfo
from test_checks import module, temporary_directory, SKILL, records

adapter = module("adapt_tracker")


def compact(**changes):
    return {"platform": "linkedin", "scheduler": "Simplified", "id": 123,
            "date": {"date": "2026-11-01", "time": "08:00", "timezone": "Asia/Dubai"},
            "status": "PENDING", "topic": "Synthetic topic", **changes}


def source(*rows):
    return {"schema_version": 1, "timezone": "Asia/Dubai", "scheduled": list(rows or [compact()]),
            "replyService": {"status": "active", "hoursDubai": [9, 18], "end": "2026-01-01"}}


def convert(doc):
    return adapter.convert(doc, "synthetic-workflow", adapter.digest(doc))


def codes(row):
    return {r["code"] for r in row["ingestion"]["requirements"]}


class AdapterTests(unittest.TestCase):
    def test_mixed_synthetic_shapes(self):
        legacy = [compact(release_id="EXAMPLE-" + str(i), id=i,
                          _full_legacy_record={"scheduler": {"name": "Simplified", "job_id": str(i)}},
                          scheduled_at="2026-11-01T04:00:00+00:00") for i in range(3)]
        small = [compact(id=100+i, uuid="job-"+str(i)) for i in range(2)]
        small.append(compact(id=None, scheduler="LinkedIn native", platform="LinkedIn", date="2026-11-01T04:00:00Z",
                             actual_post_url="https://www.linkedin.com/feed/update/urn:li:activity:1111111111111111111/"))
        doc = source(*(legacy + small))
        before = copy.deepcopy(doc)
        result = convert(doc)
        self.assertEqual(doc, before)
        self.assertEqual(result["adapter"]["source_document"], doc)
        report = adapter.summary(result)
        self.assertEqual((report["converted_rows"], report["preserved_ids"], report["proposed_ids"]), (6, 3, 3))
        self.assertEqual(len({r["release_id"] for r in result["releases"]}), 6)
        self.assertFalse(any("identity_unresolved" in codes(r) for r in result["releases"]))
        self.assertFalse(report["live_ready"])
        self.assertTrue(records.validate(result)["errors"])
        self.assertEqual(records.validate(result)["rows_checked"], 6)

    def test_idempotency_roundtrip_and_reorder(self):
        doc = source(compact(id=1), compact(id=2))
        first = convert(doc)
        self.assertEqual(first, convert(doc))
        self.assertEqual(first, convert(first))
        reversed_view = convert(source(*reversed(doc["scheduled"])))
        self.assertEqual([r["release_id"] for r in first["releases"]], list(reversed([r["release_id"] for r in reversed_view["releases"]])))
        doc["scheduled"][0].update(status="published", topic="Changed", account="newly-resolved", uuid="later-uuid", actual_post_url="https://www.linkedin.com/posts/added")
        self.assertEqual(first["releases"][0]["release_id"], convert(doc)["releases"][0]["release_id"])

    def test_snapshot_edits_rejected(self):
        for location in ("source_document_sha256", "mode", "namespace", "version"):
            result = convert(source())
            result["adapter"][location] = "tampered"
            with self.assertRaises(adapter.InvalidSource): convert(result)
        result = convert(source())
        result["releases"][0]["completion"]["complete"] = True
        with self.assertRaises(adapter.InvalidSource): convert(result)
        self.assertTrue(records.validate(result)["errors"])

    def test_malformed_and_duplicate_release_ids(self):
        for rid in (True, 17, "", "bad id", {}, [], "../bad"):
            row = convert(source(compact(release_id=rid)))["releases"][0]
            self.assertIn("release_id_malformed", codes(row))
            self.assertIn("identity_mapping_review", codes(row))
        result = convert(source(compact(release_id="SAME", id=1), compact(release_id="SAME", id=2)))
        self.assertEqual([r["release_id"] for r in result["releases"]], ["SAME", "SAME"])
        self.assertTrue(all("duplicate_release_id" in codes(r) for r in result["releases"]))

    def test_duplicate_jobs_and_alias_urls_never_silently_dropped(self):
        for rows in ((compact(id=7), compact(id="7")),
                     (compact(id=1, uuid="same"), compact(id=2, uuid="same")),
                     (compact(id=1, actual_post_url="https://www.linkedin.com/posts/synthetic-activity-1111111111111111111-TEST/?tracking=a"),
                      compact(id=2, scheduler="LinkedIn native", actual_post_url="https://linkedin.com/feed/update/urn:li:activity:1111111111111111111"))):
            result = convert(source(*rows))
            self.assertEqual(len(result["releases"]), 2)
            self.assertTrue(all("duplicate_native_identity" in codes(r) for r in result["releases"]))

    def test_existing_id_can_collide_with_generated_id(self):
        generated = convert(source())["releases"][0]["release_id"]
        result = convert(source(compact(), compact(id=2, release_id=generated)))
        self.assertTrue(all("duplicate_release_id" in codes(r) for r in result["releases"]))

    def test_no_identity_is_diagnostic_only(self):
        for bad in (None, True, -1, " ", {}, []):
            row = convert(source(compact(id=bad)))["releases"][0]
            self.assertIn("identity_unresolved", codes(row))
        for invalid_url in ("http://linkedin.com/posts/x", "https://linkedin.com.evil.test/posts/x", "https://linkedin.com/in/example", "https://user:pass@linkedin.com/posts/x"):
            self.assertIsNone(adapter.post_anchor(invalid_url, "linkedin"))

    def test_youtube_anchor_keeps_video_identity(self):
        first = adapter.post_anchor("https://www.youtube.com/watch?v=abcdefghijk", "youtube")
        self.assertEqual(first, adapter.post_anchor("https://youtu.be/abcdefghijk", "youtube"))
        self.assertNotEqual(first, adapter.post_anchor("https://www.youtube.com/watch?v=12345678901", "youtube"))
        self.assertIsNone(adapter.post_anchor("https://www.youtube.com/watch?list=abcdefghijk", "youtube"))

    def test_native_aliases_flag_duplicates_and_keep_proposed_identity(self):
        examples = {
            "instagram": ("https://www.instagram.com/p/Synthetic123/", "https://instagram.com/reel/Synthetic123/?igsh=example"),
            "linkedin": ("https://www.linkedin.com/posts/example_synthetic-activity-1111111111111111111-ABCD/", "https://www.linkedin.com/feed/update/urn%3Ali%3Aactivity%3A1111111111111111111/"),
            "tiktok": ("https://www.tiktok.com/@old_handle/video/1111111111111111111", "https://tiktok.com/@new_handle/video/1111111111111111111/"),
            "youtube": ("https://youtu.be/abcdefghijk", "https://www.youtube.com/shorts/abcdefghijk/")}
        for platform, urls in examples.items():
            with self.subTest(platform=platform):
                rows = [compact(platform=platform, id=None, actual_post_url=url) for url in urls]
                result = convert(source(*rows))["releases"]
                self.assertEqual(adapter.post_anchor(urls[0], platform), adapter.post_anchor(urls[1], platform))
                self.assertEqual(result[0]["release_id"], result[1]["release_id"])
                self.assertTrue(all("duplicate_native_identity" in codes(r) for r in result))
                rows[1]["scheduler"] = "LinkedIn native"
                self.assertEqual(convert(source(rows[1]))["releases"][0]["release_id"], result[0]["release_id"])

    def test_unknown_or_malformed_native_paths_stay_unresolved(self):
        examples = {
            "instagram": ("https://instagram.com/p/Synthetic123/extra", "https://instagram.com/reel//Synthetic123", "https://instagram.com/reel%2FSynthetic123"),
            "linkedin": ("https://linkedin.com/posts/", "https://linkedin.com/posts/arbitrary-slug", "https://linkedin.com/feed/update/anything", "https://linkedin.com/feed/update/urn:li:activity:0123"),
            "tiktok": ("https://tiktok.com/@someone/video/123/extra", "https://tiktok.com/@someone/video/0123"),
            "youtube": ("https://youtu.be////abcdefghijk", "https://youtube.com/shorts/extra/abcdefghijk", "https://youtube.com/live/extra/abcdefghijk", "https://youtube.com/watch?v=abcdefghijk&v=")}
        for platform, urls in examples.items():
            for url in urls:
                with self.subTest(platform=platform, url=url):
                    self.assertIsNone(adapter.post_anchor(url, platform))
                    row = convert(source(compact(platform=platform, id=None, actual_post_url=url)))["releases"][0]
                    self.assertTrue({"native_identity_unresolved", "identity_unresolved"} <= codes(row))

    def test_previous_snapshot_version_requires_explicit_reconciliation(self):
        snapshot = convert(source())
        snapshot["adapter"]["version"] = 1
        with self.assertRaises(adapter.InvalidSource): convert(snapshot)

    def test_conflicts_and_unknowns_are_explicit(self):
        row = convert(source(compact(_full_legacy_record={"platform": "instagram", "scheduler": {"name": "Metricool", "job_id": "other"}})))["releases"][0]
        self.assertTrue({"job_conflict", "legacy_identity_conflict", "scheduler_conflict"} <= codes(row))
        for platform in ("Instagram", "youtube ", "unknown", [], None):
            row = convert(source(compact(platform=platform)))["releases"][0]
            self.assertIn("platform_unknown", codes(row))
        for scheduler in ({"name": "Simplified"}, "unknown", None):
            self.assertIn("scheduler_unknown", codes(convert(source(compact(scheduler=scheduler)))["releases"][0]))

    def test_no_promotion_of_old_evidence(self):
        row = compact(status="verified", approval={"status": "approved"}, guide={"required": False},
                      automation={"status": "working", "end_to_end_evidence": "old"}, completion={"complete": True})
        result = convert(source(row))
        actual = result["releases"][0]
        self.assertEqual(actual["status"], "unknown")
        self.assertIsNone(actual["guide"]["required"])
        self.assertEqual(actual["automation"]["status"], "unreconciled")
        self.assertFalse(actual["completion"]["complete"])
        self.assertEqual(result["service"]["status"], "unreconciled")
        self.assertEqual(result["adapter"]["source_document"]["scheduled"][0], row)

    def test_unsupported_schema_and_invalid_json(self):
        for doc in (None, [], {}, {"schema_version": True, "scheduled": [{}]}, {"schema_version": 2, "scheduled": [{}]},
                    {"schema_version": 1, "scheduled": []}, {"schema_version": 1, "scheduled": [None]},
                    {"schema_version": 1, "scheduled": [{}], "releases": []}):
            with self.assertRaises(adapter.InvalidSource): convert(doc)
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff'):
            with self.assertRaises(adapter.InvalidSource): adapter.load_bytes(raw)
        self.assertEqual(adapter.load_bytes(b'\xef\xbb\xbf{"x":1}'), {"x": 1})

    def test_timezones_and_fractional_seconds(self):
        for value in ("2026-11-01T04:00:00Z", "2026-11-01T08:00:00+04:00", compact()["date"],
                      {"dateTime": "2026-11-01T08:00:00", "timezone": "Asia/Dubai"}):
            self.assertEqual(adapter.scheduled_time(value), "2026-11-01T04:00:00+00:00")
        self.assertEqual(adapter.scheduled_time("2026-11-01T04:00:00.2Z"), "2026-11-01T04:00:00.200000+00:00")
        for value in ("2026-11-01T08:00:00", {"date": "2026-11-01", "time": "08:00", "timezone": "Mars/City"},
                      {"date": "2026-11-01", "time": "08:00"}, {"date": "2026-13-01", "time": "08:00", "timezone": "UTC"}):
            with self.assertRaises(ValueError): adapter.scheduled_time(value)
        with patch.object(adapter, "ZoneInfo", side_effect=ZoneInfoNotFoundError):
            row = convert(source(compact(date={"date": "2026-11-01", "time": "01:30", "timezone": "America/New_York"})))["releases"][0]
            self.assertIn("schedule_time_unresolved", codes(row))
        # Legacy 'date' may be publication time, and is never used as a schedule.
        row = convert(source(compact(_full_legacy_record={"scheduler": {"name": "Simplified"}}, scheduled_at=None)))["releases"][0]
        self.assertNotIn("scheduled_at", row)
        for archive in ({}, None, []):
            row = convert(source(compact(_full_legacy_record=archive)))["releases"][0]
            self.assertNotIn("scheduled_at", row)

    def test_provider_uuid_can_start_with_dash(self):
        row = convert(source(compact(id=None, uuid="-SyntheticOpaqueId")))["releases"][0]
        self.assertEqual(row["ingestion"]["identity_basis"], "uuid")
        self.assertNotIn("job_id_malformed", codes(row))

    def test_offline_conversion_does_not_open_network(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            self.assertEqual(adapter.summary(convert(source()))["converted_rows"], 1)

    def test_dst_ambiguity_and_nonexistent_time_without_external_tzdata(self):
        # Minimal synthetic TZif: two known 2026 transition instants, no OS database.
        transitions = [1772953200, 1793512800]  # 8 March 07:00Z; 1 November 06:00Z.
        header = b"TZif\x00" + b"\x00" * 15 + struct.pack(">6l", 0, 0, 0, 2, 2, 8)
        payload = struct.pack(">2l", *transitions) + bytes([1, 0])
        payload += struct.pack(">lBB", -18000, 0, 0) + struct.pack(">lBB", -14400, 1, 4) + b"STD\x00DST\x00"
        zone = ZoneInfo.from_file(io.BytesIO(header + payload), key="Synthetic/Eastern")
        with patch.object(adapter, "ZoneInfo", return_value=zone):
            for day, hour in (("2026-03-08", "02:30"), ("2026-11-01", "01:30")):
                with self.assertRaises(ValueError): adapter.scheduled_time({"date": day, "time": hour, "timezone": "Synthetic/Eastern"})
            self.assertEqual(adapter.scheduled_time({"date": "2026-11-01", "time": "03:30", "timezone": "Synthetic/Eastern"}), "2026-11-01T08:30:00+00:00")

    def test_cli_default_read_only_unicode_and_safe_output(self):
        with temporary_directory() as folder:
            root = Path(folder) / "space café"
            root.mkdir()
            src = root / "tracker.json"
            original = adapter.encoded(source())
            src.write_bytes(original)
            base = [sys.executable, "-B", str(SKILL / "scripts/adapt_tracker.py"), str(src), "--namespace", "example"]
            before = list(root.iterdir())
            result = subprocess.run(base, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(list(root.iterdir()), before)
            self.assertFalse(json.loads(result.stdout)["external_actions_permitted"])
            self.assertNotIn("Synthetic topic", result.stdout)
            src.chmod(0o444)
            try:
                self.assertEqual(subprocess.run(base, capture_output=True).returncode, 0)
                out = root / "new.json"
                self.assertEqual(subprocess.run(base + ["--out", str(out)], capture_output=True).returncode, 0)
                for target in (src, out):
                    self.assertEqual(subprocess.run(base + ["--out", str(target)], capture_output=True).returncode, 1)
                self.assertEqual(src.read_bytes(), original)
                self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["adapter"]["source_sha256"], hashlib.sha256(original).hexdigest())
            finally:
                src.chmod(0o666)

    def test_source_change_refuses_output(self):
        with temporary_directory() as folder:
            src, out = Path(folder) / "input.json", Path(folder) / "new.json"
            data = adapter.encoded(source())
            src.write_bytes(data)
            with patch.object(sys, "argv", ["adapt_tracker.py", str(src), "--namespace", "test", "--out", str(out)]), \
                    patch.object(Path, "read_bytes", side_effect=[data, data + b" "]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(adapter.main(), 1)
            self.assertFalse(out.exists())
            self.assertEqual(src.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
