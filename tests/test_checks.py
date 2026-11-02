import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "content-operations"


def temporary_directory():
    # Keep disposable files inside this checkout, including on restricted Windows hosts.
    parent = (ROOT / "build" / "test-work").resolve()
    parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(dir=parent)
    Path(temporary.name).resolve().relative_to(parent)  # Bound cleanup to the test workspace.
    return temporary


def module(name):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


records = module("check_records")
production = module("check_production")


def tracker():
    doc = {"schema_version": 2, "policy": {"source_template": "synthetic-template", "next_step_text": "Synthetic next-step notice.", "approval_evidence": "synthetic-policy"}, "releases": [{
        "release_id": "TEST-instagram", "campaign": "TEST", "platform": "instagram", "account": "synthetic-account",
        "status": "verified", "observed_status": "verified", "evidence_refs": ["synthetic-native-observation"],
        "actual_post_url": "https://www.instagram.com/reel/exact/",
        "native_verification": {"checked_at": "2026-10-31T10:00:00+04:00", "evidence": "synthetic-native"},
        "guide": {"required": True, "keyword": "TEST", "pdf_url": "https://example.com/guide.pdf", "pdf_sha256": "a" * 64, "public_pdf_verified_at": "2026-10-31T10:00:00+04:00", "evidence": "synthetic-pdf-check"},
        "automation": {"status": "working", "flow_id": "copy", "source_flow_id": "original", "source_template": "synthetic-template", "reel_id": "exact", "trigger_scope": "exact_post", "trigger_live": True,
                       "keyword": "TEST", "saved_config_evidence": "synthetic-config", "configuration_verified_at": "2026-10-31T10:00:00+04:00", "follower_gate_verified": True, "follower_gate_evidence": "synthetic-gate", "recheck_loop_verified": True, "recheck_loop_evidence": "synthetic-loop", "destination_pdf_url": "https://example.com/guide.pdf", "destination_pdf_sha256": "a" * 64, "end_to_end_pdf_sha256": "a" * 64, "end_to_end_evidence": "synthetic-receipt", "verified_at": "2026-10-31T10:00:00+04:00"},
        "completion": {"complete": True, "publication": True, "delivery": True, "service": True, "review": True, "unresolved": []}
    }]}
    row = doc["releases"][0]
    row["asset"] = {"sha256": "b" * 64}
    row["guide"]["version"] = "guide-v1"
    row["automation"]["configuration_version"] = "synthetic-config-v1"
    row["automation"]["variants"] = ["TEST", "test"]
    row["automation"]["end_to_end_binding"] = records.tested_configuration(row)
    return doc


def guide_event(doc, state="sent"):
    row = doc["releases"][0]
    event = {"says_check_your_dm": True, "delivery_state": state, "release_id": row["release_id"], "recipient_reference": "synthetic-recipient", "guide_version": row["guide"]["version"], "guide_destination_verified": True, "dm_delivery_key": "synthetic-account/synthetic-recipient/TEST/guide-v1"}
    key = {"sent": "send_evidence", "delivered": "delivery_evidence", "recipient_confirmed": "recipient_confirmation_evidence"}[state]
    event[key] = {"reference": "synthetic-final-resource", "binding": records.requested_guide_binding(row, event)}
    return event


def review_export(export):
    for key in ("media_probe_evidence", "playback_evidence", "audio_evidence", "caption_safe_area_evidence", "disclosure_review_evidence"):
        export[key] = {"reference": "synthetic-output-review", "reviewed_export": production.export_fingerprint(export)}


class RecordTests(unittest.TestCase):
    def test_valid_complete_record(self):
        self.assertEqual(records.validate(tracker())["errors"], [])

    def test_unknown_empty_and_legacy_schemas_fail(self):
        for doc in ({}, [], {"schema_version": 99, "releases": []}, {"schema_version": True, "releases": [{}]}, {"schema_version": 2, "releases": []}, {"schema_version": 2, "scheduled": [{}]}, {"schema_version": 2, "releases": "wrong"}, {"schema_version": 2, "releases": [None]}, {"schema_version": 2, "releases": [{"release_id": "x", "scheduler": None}]}):
            with self.subTest(doc=doc):
                self.assertTrue(records.validate(doc)["errors"])

    def test_legacy_array_cli_exits_nonzero(self):
        with temporary_directory() as folder:
            path = Path(folder) / "legacy.json"
            path.write_text(json.dumps({"scheduled": [{"status": "verified"}]}))
            result = subprocess.run([sys.executable, str(SKILL / "scripts/check_records.py"), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertTrue(json.loads(result.stdout)["errors"])

    def test_gate_mapping_and_trigger_are_required(self):
        for key, value in (("source_flow_id", None), ("keyword", "WRONG"), ("destination_pdf_url", "https://example.com/other.pdf"), ("destination_pdf_sha256", "b" * 64), ("follower_gate_verified", False), ("follower_gate_evidence", None), ("recheck_loop_verified", False), ("trigger_live", False), ("trigger_scope", "all_posts"), ("reel_id", "exa"), ("end_to_end_pdf_sha256", "b" * 64)):
            with self.subTest(key=key):
                doc = tracker()
                doc["releases"][0]["automation"][key] = value
                self.assertTrue(records.validate(doc)["errors"])

    def test_configured_flow_requires_explicit_template_policy(self):
        for policy in (None, {}, {"source_template": "synthetic-template"}, {"source_template": "other", "approval_evidence": "synthetic"}):
            doc = tracker()
            doc["policy"] = policy
            self.assertTrue(records.validate(doc)["errors"])

    def test_configured_flow_rejects_blank_or_nonstring_policy_approval(self):
        for value in (None, "", " \t\n", 42, 0, True, False, {}, {"ref": "synthetic"}, [], ["synthetic"]):
            with self.subTest(value=value):
                doc = tracker()
                doc["policy"]["approval_evidence"] = value
                self.assertTrue(records.validate(doc)["errors"])

    def test_source_template_types_fail_even_when_matching_and_rebound(self):
        for value in (None, "", " \t\n", 42, 0, True, False, {}, {"name": "synthetic"}, [], ["synthetic"]):
            for target in ("policy", "flow", "both"):
                with self.subTest(value=value, target=target):
                    doc = tracker()
                    row = doc["releases"][0]
                    if target in ("policy", "both"):
                        doc["policy"]["source_template"] = value
                    if target in ("flow", "both"):
                        row["automation"]["source_template"] = value
                    row["automation"]["end_to_end_binding"] = records.tested_configuration(row)
                    self.assertTrue(records.validate(doc)["errors"])

    def test_next_step_rejects_blank_or_nonstring_approval_without_flow(self):
        doc = tracker()
        row = doc["releases"][0]
        row.update(automation={}, guide={"required": False}, completion={})
        event = {"acknowledgement_type": "next_step", "text": doc["policy"]["next_step_text"], "trigger_evidence": "synthetic", "follower_gate_evidence": "synthetic"}
        self.assertFalse(records.validate(doc, [event])["errors"])
        for value in (None, "", " \t\n", 42, 0, True, False, {}, {"ref": "synthetic"}, [], ["synthetic"]):
            with self.subTest(value=value):
                changed = copy.deepcopy(doc)
                changed["policy"]["approval_evidence"] = value
                self.assertTrue(records.validate(changed, [event])["errors"])

    def test_next_step_wording_types_fail_even_when_equal(self):
        for value in (None, "", " \t\n", 42, 0, True, False, {}, {"text": "synthetic"}, [], ["synthetic"]):
            for target in ("policy", "event", "both"):
                with self.subTest(value=value, target=target):
                    doc = tracker()
                    event = {"acknowledgement_type": "next_step", "text": doc["policy"]["next_step_text"], "trigger_evidence": "synthetic", "follower_gate_evidence": "synthetic"}
                    if target in ("policy", "both"):
                        doc["policy"]["next_step_text"] = value
                    if target in ("event", "both"):
                        event["text"] = value
                    self.assertTrue(records.validate(doc, [event])["errors"])

    def test_policy_validation_is_limited_to_applicable_features(self):
        doc = tracker()
        doc["releases"][0].update(automation={}, guide={"required": False}, completion={})
        for policy in (None, {}, [], {"approval_evidence": "   ", "source_template": 42, "next_step_text": True}):
            with self.subTest(policy=policy):
                doc["policy"] = policy
                self.assertFalse(records.validate(doc)["errors"])
        doc = tracker()
        del doc["policy"]["next_step_text"]
        self.assertFalse(records.validate(doc)["errors"])
        doc["releases"][0].update(automation={}, guide={"required": False}, completion={})
        doc["policy"] = {"approval_evidence": "synthetic", "next_step_text": "Synthetic notice."}
        event = {"acknowledgement_type": "next_step", "text": "Synthetic notice.", "trigger_evidence": "synthetic", "follower_gate_evidence": "synthetic"}
        self.assertFalse(records.validate(doc, [event])["errors"])

    def test_nonblank_policy_does_not_relax_exact_matching(self):
        doc = tracker()
        doc["policy"]["source_template"] += " "
        self.assertTrue(records.validate(doc)["errors"])
        event = {"acknowledgement_type": "next_step", "text": "Synthetic next-step notice. ", "trigger_evidence": "synthetic", "follower_gate_evidence": "synthetic"}
        self.assertTrue(records.validate(tracker(), [event])["errors"])

    def test_malformed_policy_approval_cli_exits_one_and_preserves_input(self):
        with temporary_directory() as folder:
            path = Path(folder) / "synthetic-policy.json"
            for value in ("   ", 42, True, {"ref": "synthetic"}, ["synthetic"]):
                with self.subTest(value=value):
                    doc = tracker()
                    doc["policy"]["approval_evidence"] = value
                    original = json.dumps(doc).encode("utf-8")
                    path.write_bytes(original)
                    result = subprocess.run([sys.executable, "-B", str(SKILL / "scripts/check_records.py"), str(path)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertTrue(json.loads(result.stdout)["errors"])
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(path.read_bytes(), original)

    def test_configured_is_not_delivered(self):
        doc = tracker()
        doc["releases"][0]["automation"]["status"] = "configured"
        self.assertTrue(records.validate(doc)["errors"])
        doc["releases"][0]["completion"].update(complete=False, delivery=False)
        self.assertFalse(records.validate(doc)["errors"])

    def test_guide_publication_requires_configuration(self):
        doc = tracker()
        doc["releases"][0]["automation"] = {"status": "planned"}
        doc["releases"][0]["completion"].update(complete=False, delivery=False)
        self.assertTrue(records.validate(doc)["errors"])

    def test_other_platforms_keep_supported_routes_without_manychat(self):
        for platform in ("linkedin", "youtube", "tiktok"):
            doc = tracker()
            row = doc["releases"][0]
            row["platform"] = platform
            row["automation"] = {"status": "not_applicable"}
            row["guide"].update(delivery_route="public_link", delivery_evidence="synthetic-public-journey")
            self.assertFalse(records.validate(doc)["errors"])
            row["guide"]["delivery_evidence"] = None
            self.assertTrue(records.validate(doc)["errors"])

    def test_youtube_cannot_claim_private_delivery(self):
        doc = tracker()
        row = doc["releases"][0]
        row.update(platform="youtube", automation={"status": "not_applicable"})
        row["guide"].update(delivery_route="manual_dm", delivery_evidence="incorrect-route")
        self.assertTrue(records.validate(doc)["errors"])

    def test_next_step_ack_does_not_claim_final_delivery(self):
        event = {"acknowledgement_type": "next_step", "text": "Synthetic next-step notice.", "trigger_evidence": "synthetic", "follower_gate_evidence": "synthetic"}
        self.assertFalse(records.validate(tracker(), [event])["errors"])
        for change in ({"text": "Guide delivered"}, {"trigger_evidence": None}, {"claims_final_delivery": True}):
            self.assertTrue(records.validate(tracker(), [{**event, **change}])["errors"])

    def test_manual_ack_needs_verified_requested_guide_send(self):
        doc = tracker()
        event = guide_event(doc)
        self.assertFalse(records.validate(doc, [event])["errors"])
        for change in ({"send_evidence": None}, {"delivery_state": "pending"}, {"guide_destination_verified": False}, {"claims_final_delivery": True}):
            self.assertTrue(records.validate(tracker(), [{**event, **change}])["errors"])

    def test_duplicates_still_fail(self):
        event = {"result": "success", "dm_delivery_key": "same"}
        self.assertTrue(records.validate(tracker(), [event, event])["errors"])

    def test_delivered_label_alone_is_not_evidence(self):
        for state, evidence_field in (("delivered", "delivery_evidence"), ("recipient_confirmed", "recipient_confirmation_evidence")):
            event = {"says_check_your_dm": True, "delivery_state": state}
            self.assertTrue(records.validate(tracker(), [event])["errors"])
            event[evidence_field] = "synthetic-confirmation"
            self.assertTrue(records.validate(tracker(), [event])["errors"])
            doc = tracker()
            self.assertFalse(records.validate(doc, [guide_event(doc, state)])["errors"])

    def test_noncanonical_platforms_cannot_bypass_routes(self):
        for value in (None, "", "Instagram", "youtube ", "YOUTUBE", " facebook", "unknown", []):
            doc = tracker()
            row = doc["releases"][0]
            row.update(platform=value, automation={"status": "not_applicable"})
            row["guide"].update(delivery_route="manual_dm", delivery_evidence="synthetic")
            self.assertTrue(records.validate(doc)["errors"], value)

    def test_changed_flow_cannot_reuse_end_to_end_evidence(self):
        for change in ("keyword", "reel", "variants", "gate", "pdf", "version", "asset"):
            doc = tracker()
            row = doc["releases"][0]
            flow, guide = row["automation"], row["guide"]
            if change == "keyword": guide["keyword"] = flow["keyword"] = "NEW"
            if change == "reel": row["actual_post_url"], flow["reel_id"] = "https://www.instagram.com/reel/new/", "new"
            if change == "variants": flow["variants"].append("new-variant")
            if change == "gate": flow["follower_gate_evidence"] = "changed-gate-configuration"
            if change == "pdf": guide["pdf_sha256"] = flow["destination_pdf_sha256"] = flow["end_to_end_pdf_sha256"] = "c" * 64
            if change == "version": flow["configuration_version"] = "v2"
            if change == "asset": row["asset"]["sha256"] = "c" * 64
            self.assertTrue(records.validate(doc)["errors"], change)

    def test_end_to_end_binding_cannot_hide_old_test_time(self):
        doc = tracker()
        row = doc["releases"][0]
        row["automation"].update(configuration_verified_at="2026-10-31T11:00:00+04:00", saved_config_evidence="synthetic-new-snapshot")
        row["automation"]["end_to_end_binding"] = records.tested_configuration(row)
        self.assertTrue(records.validate(doc)["errors"])
        # A separately observed test after that configuration can establish new evidence.
        row["automation"].update(verified_at="2026-10-31T07:01:00Z", end_to_end_evidence="synthetic-new-test")
        self.assertFalse(records.validate(doc)["errors"])

    def test_final_delivery_requires_exact_resource_and_recipient_binding(self):
        for state in ("sent", "delivered", "recipient_confirmed"):
            doc = tracker()
            event = guide_event(doc, state)
            for key, value in (("guide_destination_verified", False), ("recipient_reference", "someone-else"), ("guide_version", "v2"), ("release_id", "other-release"), ("dm_delivery_key", None)):
                bad = copy.deepcopy(event)
                bad[key] = value
                self.assertTrue(records.validate(doc, [bad])["errors"], (state, key))
            evidence_key = {"sent": "send_evidence", "delivered": "delivery_evidence", "recipient_confirmed": "recipient_confirmation_evidence"}[state]
            for field, value in (("resource_kind", "opening_dm"), ("pdf_sha256", "c" * 64), ("pdf_url", "https://example.com/other.pdf")):
                bad = copy.deepcopy(event)
                bad[evidence_key]["binding"][field] = value
                self.assertTrue(records.validate(doc, [bad])["errors"], (state, field))

    def test_hash_format_applies_to_all_guide_routes(self):
        for platform in ("linkedin", "youtube", "tiktok"):
            doc = tracker()
            row = doc["releases"][0]
            row.update(platform=platform, automation={"status": "not_applicable"})
            row["guide"].update(delivery_route="public_link", delivery_evidence="synthetic", pdf_sha256="not-a-hash")
            self.assertTrue(records.validate(doc)["errors"], platform)

    def test_three_hour_slots_preserve_anchor_and_expiry(self):
        slots = records.slots("2026-10-31T10:00:00+04:00", "2026-11-01T11:30:00+04:00", anchor="2026-10-31T09:30:00+04:00", interval_hours=3, window_hours=168)
        self.assertEqual(slots[0], "2026-10-31T12:30:00+04:00")
        self.assertEqual(slots[-1], "2026-11-01T09:30:00+04:00")
        self.assertEqual(len(slots), 8)
        for first, second in zip(slots, slots[1:]):
            self.assertEqual((records.instant(second) - records.instant(first)).total_seconds(), 10800)

    def test_timing_has_no_implicit_cadence_or_window(self):
        for kwargs in ({}, {"interval_hours": 2}, {"window_hours": 12}, {"interval_hours": 0, "window_hours": 12}, {"interval_hours": True, "window_hours": 12}):
            with self.assertRaises(ValueError):
                records.slots("2030-01-01T10:00:00Z", anchor="2030-01-01T09:00:00Z", **kwargs)
        values = records.slots("2030-01-01T10:00:00Z", anchor="2030-01-01T09:00:00Z", interval_hours=2, window_hours=5)
        self.assertEqual(values, ["2030-01-01T11:00:00+00:00", "2030-01-01T13:00:00+00:00", "2030-01-01T15:00:00+00:00"])

    def test_missing_anchor_fails(self):
        with self.assertRaises(ValueError):
            records.slots("2026-10-31T10:00:00+04:00")

    def test_late_start_does_not_extend_window(self):
        slots = records.slots("2026-10-31T10:00:00+04:00", anchor="2026-10-31T09:00:00+04:00", service_start="2026-11-06T10:00:00+04:00", interval_hours=3, window_hours=168)
        self.assertEqual(len(slots), 8)
        self.assertEqual(slots[-1], "2026-11-07T09:00:00+04:00")

    def test_slot_at_service_start_is_included_after_publication(self):
        slots = records.slots("2026-10-31T10:00:00+04:00", anchor="2026-10-31T09:00:00+04:00", service_start="2026-10-31T12:00:00+04:00", interval_hours=3, window_hours=168)
        self.assertEqual(slots[0], "2026-10-31T12:00:00+04:00")

    def test_partial_check_cannot_advance_success(self):
        doc = tracker()
        doc["releases"][0]["comments"] = {"coverage": "partial", "last_attempt_at": "2026-10-31T12:00:00+04:00", "latest_comment_check": "2026-10-31T12:00:00+04:00", "latest_success_evidence": "some-platform-only"}
        self.assertTrue(records.validate(doc)["errors"])

    def test_partial_scan_compares_instants_not_timestamp_spelling(self):
        for coverage in ("partial", "failed", "not_checked"):
            doc = tracker()
            comments = {"coverage": coverage, "last_attempt_at": "2026-10-31T12:00:00+04:00", "latest_comment_check": "2026-10-31T08:00:00Z", "latest_success_evidence": "synthetic"}
            doc["releases"][0]["comments"] = comments
            self.assertTrue(records.validate(doc)["errors"])
            comments["latest_comment_check"] = "2026-10-31T07:00:00Z"
            self.assertFalse(records.validate(doc)["errors"])
            comments["last_attempt_at"] = "2026-10-31T12:00:00"
            self.assertTrue(records.validate(doc)["errors"])

    def test_active_service_needs_actual_anchor_and_authority(self):
        doc = tracker()
        doc["service"] = {"status": "active", "owner": "one-runner", "approval_evidence": "synthetic", "scope_evidence": "synthetic", "window_hours": 168, "cadence": {"interval_hours": 3, "anchor_at": "2026-10-31T09:00:00+04:00"}}
        self.assertFalse(records.validate(doc)["errors"])
        doc["service"]["cadence"]["interval_hours"] = 0
        self.assertTrue(records.validate(doc)["errors"])


    def test_release_evidence_rejects_blank_or_nonstring_values(self):
        malformed = ("", " \t\n", 42, 0, True, False, {}, {"ref": "synthetic"}, [], ["synthetic"])
        paths = (("approval", "evidence"), ("native_verification", "evidence"), ("guide", "evidence"),
                 ("automation", "saved_config_evidence"), ("automation", "follower_gate_evidence"),
                 ("automation", "recheck_loop_evidence"), ("automation", "end_to_end_evidence"))
        for section, key in paths:
            for value in malformed:
                with self.subTest(field=section + "." + key, value=value):
                    doc = tracker()
                    row = doc["releases"][0]
                    row["caption_sha256"] = "c" * 64
                    row["approval"] = {"status": "approved", "bound_asset_sha256": "b" * 64, "bound_caption_sha256": "c" * 64, "evidence": "synthetic-approval"}
                    row["automation"]["end_to_end_binding"] = records.tested_configuration(row)
                    self.assertFalse(records.validate(doc)["errors"])
                    row[section][key] = value
                    row["automation"]["end_to_end_binding"] = records.tested_configuration(row)
                    self.assertTrue(records.validate(doc)["errors"])
        for value in ([], [""], ["  "], [42], "synthetic", {"ref": "synthetic"}):
            with self.subTest(evidence_refs=value):
                doc = tracker()
                doc["releases"][0]["evidence_refs"] = value
                self.assertTrue(records.validate(doc)["errors"])

    def test_approval_hashes_must_be_real_sha256_even_when_equal(self):
        for value in (" ", "old", True, 7, "B" * 64):
            with self.subTest(value=value):
                doc = tracker()
                row = doc["releases"][0]
                row.update(automation={}, guide={"required": False}, completion={}, status="approved")
                row["asset"]["sha256"] = value
                row["caption_sha256"] = value
                row["approval"] = {"status": "approved", "bound_asset_sha256": value, "bound_caption_sha256": value, "evidence": "synthetic-approval"}
                self.assertTrue(records.validate(doc)["errors"])

    def test_approved_or_scheduled_state_needs_recorded_approval(self):
        for status in ("approved", "scheduled"):
            for approval in (None, {}, {"status": "pending"}, {"status": "rejected", "evidence": "synthetic"}):
                with self.subTest(status=status, approval=approval):
                    doc = tracker()
                    row = doc["releases"][0]
                    row.update(automation={}, guide={"required": False}, completion={}, status=status,
                               scheduled_at="2026-11-02T09:00:00+04:00", scheduler={"name": "synthetic", "active_job_ids": [], "job_id": "j1", "verification_evidence": "synthetic-job"})
                    if approval is None:
                        row.pop("approval", None)
                    else:
                        row["approval"] = approval
                    self.assertTrue(records.validate(doc)["errors"])
                    row["caption_sha256"] = "c" * 64
                    row["approval"] = {"status": "approved", "bound_asset_sha256": "b" * 64, "bound_caption_sha256": "c" * 64, "evidence": "synthetic-approval"}
                    self.assertFalse(records.validate(doc)["errors"])

    def test_acknowledgement_trigger_and_gate_evidence_reject_malformed_values(self):
        doc = tracker()
        doc["releases"][0].update(automation={}, guide={"required": False}, completion={})
        for key in ("trigger_evidence", "follower_gate_evidence"):
            for value in (None, "", " \t\n", 42, 0, True, False, {}, {"ref": "synthetic"}, [], ["synthetic"]):
                with self.subTest(field=key, value=value):
                    event = {"acknowledgement_type": "next_step", "text": doc["policy"]["next_step_text"], "trigger_evidence": "synthetic", "follower_gate_evidence": "synthetic"}
                    self.assertFalse(records.validate(doc, [event])["errors"])
                    event[key] = value
                    self.assertTrue(records.validate(doc, [event])["errors"])

    def test_malformed_field_types_report_errors_instead_of_crashing(self):
        cases = (("guide", {"required": True, "pdf_url": 1}), ("actual_publication_at", 5),
                 ("comments", {"latest_comment_check": 5, "latest_success_evidence": "synthetic"}))
        for key, value in cases:
            with self.subTest(field=key):
                doc = tracker()
                doc["service"] = {"window_hours": 168}
                doc["releases"][0][key] = value
                self.assertTrue(records.validate(doc)["errors"])
        doc = tracker()
        doc["service"] = {"window_hours": 168}
        doc["releases"][0].update(actual_publication_at="2026-10-31T10:00:00+04:00", comments={"window_end_at": 5})
        self.assertTrue(records.validate(doc)["errors"])

    def test_cli_unreadable_input_exits_two_and_preserves_files(self):
        with temporary_directory() as folder:
            folder = Path(folder)
            broken = folder / "synthetic-broken.json"
            broken.write_bytes(b"{not json")
            crashing = folder / "synthetic-types.json"
            doc = tracker()
            doc["releases"][0]["guide"]["pdf_url"] = 1
            crashing.write_bytes(json.dumps(doc).encode("utf-8"))
            before = {path: path.read_bytes() for path in folder.iterdir()}
            for args, code in (([str(broken)], 2), ([str(folder / "absent.json")], 2), ([str(crashing)], 1)):
                with self.subTest(args=args):
                    result = subprocess.run([sys.executable, "-B", str(SKILL / "scripts/check_records.py"), *args], capture_output=True, text=True)
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
            self.assertEqual({path: path.read_bytes() for path in folder.iterdir()}, before)


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = json.loads((SKILL / "templates/production-manifest.template.json").read_text())
        self.doc["status"] = "ready_for_review"
        self.doc["policy"] = {"context": "synthetic-context", "expected_speaker": "Synthetic Presenter", "expected_presenter": "Synthetic Presenter", "approval_evidence": "synthetic-policy"}
        self.doc["context"] = "synthetic-context"
        self.doc["narration"]["speaker"] = "Synthetic Presenter"
        self.doc["assets"][0]["identity"] = "Synthetic Presenter"
        for label, record in (("script", self.doc["script"]), ("narration", self.doc["narration"]), ("captions", self.doc["captions"]), ("presenter", self.doc["assets"][0]), ("export", self.doc["exports"][0])):
            # Synthetic bytes exercise contracts only, not real media playback or rendering.
            data = ("synthetic-" + label).encode()
            (self.root / (label + ".dat")).write_bytes(data)
            record.update(path=label + ".dat", sha256=hashlib.sha256(data).hexdigest())
        self.doc["script"]["approval_evidence"] = "synthetic-script-review"
        self.doc["narration"]["approval_evidence"] = "synthetic-voice-review"
        self.doc["captions"].update(script_sha256=self.doc["script"]["sha256"], review_evidence="synthetic-caption-review")
        self.doc["assets"][0]["rights_evidence"] = "synthetic-owned-recording"
        inputs = {"script_sha256": self.doc["script"]["sha256"], "narration_sha256": self.doc["narration"]["sha256"], "captions_sha256": self.doc["captions"]["sha256"], "asset_sha256": {"presenter": self.doc["assets"][0]["sha256"]}}
        self.doc["review"].update(inputs=copy.deepcopy(inputs), voice_evidence="synthetic", claims_evidence="synthetic", privacy_evidence="synthetic")
        self.doc["exports"][0].update(inputs=copy.deepcopy(inputs), duration_seconds=30, media_probe_evidence="synthetic", playback_evidence="synthetic", audio_evidence="synthetic", caption_safe_area_evidence="synthetic", disclosure_review_evidence="synthetic")
        review_export(self.doc["exports"][0])

    def test_complete_contract_does_not_authorise_publication(self):
        result = production.validate(self.doc, self.root)
        self.assertFalse(result["errors"])
        self.assertIs(result["publication_authorised"], False)

    def test_missing_or_changed_identity_policy_blocks(self):
        for policy in (None, {}, {"context": "synthetic-context"}):
            doc = copy.deepcopy(self.doc)
            doc["policy"] = policy
            self.assertTrue(production.validate(doc, self.root)["errors"])
        for key in ("context", "expected_speaker", "expected_presenter", "approval_evidence"):
            doc = copy.deepcopy(self.doc)
            doc["policy"][key] = ""
            self.assertTrue(production.validate(doc, self.root)["errors"])

    def test_script_and_audio_changes_invalidate_review(self):
        for key in ("script", "narration"):
            path = self.root / self.doc[key]["path"]
            path.write_bytes(b"changed")
            self.assertTrue(production.validate(self.doc, self.root)["errors"])

    def test_hash_updates_alone_cannot_preserve_approval(self):
        data = b"new-script"
        (self.root / self.doc["script"]["path"]).write_bytes(data)
        self.doc["script"]["sha256"] = hashlib.sha256(data).hexdigest()
        self.assertTrue(production.validate(self.doc, self.root)["errors"])

    def test_voice_rights_and_caption_requirements(self):
        for section, key, value in (("narration", "mode", "stock_tts"), ("narration", "speaker", "Another person"), ("script", "approval_evidence", None), ("captions", "review_evidence", None), ("review", "privacy_evidence", None)):
            doc = copy.deepcopy(self.doc)
            doc[section][key] = value
            self.assertTrue(production.validate(doc, self.root)["errors"])
        self.doc["assets"][0]["rights_evidence"] = None
        self.assertTrue(production.validate(self.doc, self.root)["errors"])


    def test_evidence_fields_reject_blank_or_nonstring_values(self):
        fields = (("script", "approval_evidence"), ("narration", "approval_evidence"), ("captions", "review_evidence"),
                  ("review", "voice_evidence"), ("review", "claims_evidence"), ("review", "privacy_evidence"))
        for value in ("", " \t\n", 42, 0, True, False, {}, {"ref": "synthetic"}, [], ["synthetic"]):
            for section, key in fields:
                with self.subTest(field=section + "." + key, value=value):
                    doc = copy.deepcopy(self.doc)
                    doc[section][key] = value
                    self.assertTrue(production.validate(doc, self.root)["errors"])
            with self.subTest(field="rights_evidence", value=value):
                doc = copy.deepcopy(self.doc)
                doc["assets"][0]["rights_evidence"] = value
                self.assertTrue(production.validate(doc, self.root)["errors"])
            with self.subTest(field="export reference", value=value):
                doc = copy.deepcopy(self.doc)
                doc["exports"][0]["playback_evidence"]["reference"] = value
                self.assertTrue(production.validate(doc, self.root)["errors"])

    def test_exports_need_measured_dimensions_and_reviews(self):
        for key, value in (("width", 1920), ("height", -1), ("duration_seconds", float("nan")), ("audio_evidence", None), ("caption_safe_area_evidence", None), ("inputs", {})):
            doc = copy.deepcopy(self.doc)
            doc["exports"][0][key] = value
            self.assertTrue(production.validate(doc, self.root)["errors"])

    def test_variant_can_pass_with_separate_reviewed_export(self):
        second = copy.deepcopy(self.doc["exports"][0])
        second.update(export_id="square", width=1080, height=1080, aspect_ratio="1:1")
        self.doc["exports"].append(second)
        self.assertTrue(production.validate(self.doc, self.root)["errors"])
        review_export(second)
        self.assertFalse(production.validate(self.doc, self.root)["errors"])
        second["export_id"] = self.doc["exports"][0]["export_id"]
        self.assertTrue(production.validate(self.doc, self.root)["errors"])

    def test_rerender_needs_independent_review_of_each_exact_output(self):
        export = self.doc["exports"][0]
        data = b"synthetic rerender with changed output"
        (self.root / export["path"]).write_bytes(data)
        export["sha256"] = hashlib.sha256(data).hexdigest()
        self.assertTrue(production.validate(self.doc, self.root)["errors"])
        for key in ("media_probe_evidence", "playback_evidence", "audio_evidence", "caption_safe_area_evidence"):
            export[key] = {"reference": "synthetic-new-review", "reviewed_export": production.export_fingerprint(export)}
            self.assertTrue(production.validate(self.doc, self.root)["errors"])
        export["disclosure_review_evidence"] = {"reference": "synthetic-new-disclosure-review", "reviewed_export": production.export_fingerprint(export)}
        self.assertFalse(production.validate(self.doc, self.root)["errors"])
        export["duration_seconds"] = 29
        self.assertTrue(production.validate(self.doc, self.root)["errors"])

    def test_paths_cannot_fetch_or_escape_root(self):
        for value in ("../outside.dat", "https://example.com/audio.wav", "C:\\outside.wav", "//server/share/file.wav", "audio.dat:stream"):
            doc = copy.deepcopy(self.doc)
            doc["narration"]["path"] = value
            self.assertTrue(production.validate(doc, self.root)["errors"])

    def test_blank_template_is_not_ready(self):
        doc = json.loads((SKILL / "templates/production-manifest.template.json").read_text())
        self.assertTrue(production.validate(doc, self.root)["errors"])


class DistributionTests(unittest.TestCase):
    def command(self, script, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)], capture_output=True, text=True)

    def test_disposable_install_identical_and_conflicting_copies(self):
        with temporary_directory() as folder:
            home = Path(folder)
            check = self.command("install.py", "--host", "both", "--home", home, "--check")
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertFalse((home / ".agents").exists())
            result = self.command("install.py", "--host", "both", "--home", home)
            self.assertEqual(result.returncode, 0, result.stderr)
            target = home / ".agents/skills/content-operations/SKILL.md"
            self.assertEqual(target.read_bytes(), (SKILL / "SKILL.md").read_bytes())
            self.assertEqual(self.command("install.py", "--host", "both", "--home", home).returncode, 0)
            target.write_text("preserve this differing installation")
            self.assertNotEqual(self.command("install.py", "--host", "both", "--home", home).returncode, 0)
            self.assertEqual(target.read_text(), "preserve this differing installation")

    def test_package_contains_only_skill_and_refuses_overwrite(self):
        with temporary_directory() as folder:
            archive = Path(folder) / "skill.zip"
            result = self.command("package.py", "--out", archive)
            self.assertEqual(result.returncode, 0, result.stderr)
            before = archive.read_bytes()
            with zipfile.ZipFile(archive) as packaged:
                self.assertIsNone(packaged.testzip())
                self.assertIn("content-operations/scripts/check_production.py", packaged.namelist())
                for name in packaged.namelist():
                    self.assertTrue(name.startswith("content-operations/"))
                    source = SKILL / Path(name).relative_to("content-operations")
                    self.assertEqual(packaged.read(name), source.read_bytes())
                    self.assertNotIn("__pycache__", name)
            self.assertNotEqual(self.command("package.py", "--out", archive).returncode, 0)
            self.assertEqual(archive.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
