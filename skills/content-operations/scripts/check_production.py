"""Read-only local draft QA. No rendering, uploads, providers or publication permission."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path, PureWindowsPath

RATIOS = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1), "4:5": (4, 5)}


def nonblank_string(value):
    return isinstance(value, str) and bool(value.strip())


def export_fingerprint(export):
    """Identity to record separately when each output review actually occurs."""
    return {key: export.get(key) for key in ("sha256", "width", "height", "aspect_ratio", "duration_seconds")}


def validate(doc, root):
    errors = []
    root = Path(root).resolve()
    if not isinstance(doc, dict) or type(doc.get("schema_version")) is not int or doc.get("schema_version") != 1:
        return {"errors": ["Unsupported production schema"], "exports_checked": 0}
    policy = doc.get("policy", {})
    if not isinstance(policy, dict):
        policy = {}
    if not all(nonblank_string(policy.get(k)) for k in ("context", "expected_speaker", "expected_presenter", "approval_evidence")):
        errors.append("Explicit context, speaker, presenter and policy approval evidence are required")
    if not policy.get("context") or doc.get("context") != policy["context"] or doc.get("status") != "ready_for_review":
        errors.append("A configured-context ready_for_review handoff is required; drafts are incomplete")

    def file_record(record, label):
        if not isinstance(record, dict):
            errors.append(label + ": expected an object")
            return {}
        value, digest = record.get("path"), record.get("sha256")
        if not isinstance(value, str) or not value or ":" in value or PureWindowsPath(value).is_absolute() or Path(value).is_absolute():
            errors.append(label + ": use a local relative path inside the explicit media root")
            return record
        try:
            path = (root / value).resolve()
            path.relative_to(root)
            if not path.is_file():
                raise ValueError("file missing")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("SHA-256 missing or malformed")
            # Stream large local media; never follow a remote URL or execute a media tool.
            with path.open("rb") as handle:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
                actual = hasher.hexdigest()
            if actual != digest:
                raise ValueError("SHA-256 differs from the reviewed file")
        except (OSError, ValueError) as ex:
            errors.append(label + ": " + str(ex))
        return record

    script = file_record(doc.get("script"), "script")
    narration = file_record(doc.get("narration"), "narration")
    captions = file_record(doc.get("captions"), "captions")
    if not nonblank_string(script.get("approval_evidence")):
        errors.append("script: exact script approval evidence required")
    if narration.get("speaker") != policy.get("expected_speaker") or narration.get("mode") not in ("original_recording", "approved_existing_voice") or not nonblank_string(narration.get("approval_evidence")):
        errors.append("narration: preserve the configured approved authentic voice; no stock voice substitution")
    if not nonblank_string(captions.get("review_evidence")) or captions.get("script_sha256") != script.get("sha256"):
        errors.append("captions: reviewed wording must bind to this script")
    assets = doc.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("assets: record the owned or rights-cleared footage/images, including presenter footage")
        assets = []
    asset_hashes = {}
    for asset in assets:
        asset = file_record(asset, "asset")
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id or asset_id in asset_hashes:
            errors.append("asset: unique asset_id required")
            continue
        asset_hashes[asset_id] = asset.get("sha256")
        if asset.get("rights") not in ("owned", "licensed", "cleared") or not nonblank_string(asset.get("rights_evidence")):
            errors.append(asset_id + ": reuse rights need evidence, including any music")
        if asset.get("role") not in ("presenter", "b_roll", "graphic", "music"):
            errors.append(asset_id + ": identify the asset role")
        if asset.get("role") == "presenter" and asset.get("identity") != policy.get("expected_presenter"):
            errors.append(asset_id + ": presenter must match the approved policy")
    review = doc.get("review", {})
    if not isinstance(review, dict):
        errors.append("review: expected an object")
        review = {}
    for key in ("voice_evidence", "claims_evidence", "privacy_evidence"):
        if not nonblank_string(review.get(key)):
            errors.append("review: missing " + key)
    expected_inputs = {"script_sha256": script.get("sha256"), "narration_sha256": narration.get("sha256"), "captions_sha256": captions.get("sha256"), "asset_sha256": asset_hashes}
    if review.get("inputs") != expected_inputs:
        errors.append("review: evidence must bind to the current script, narration, captions and asset hashes")
    exports = doc.get("exports")
    if not isinstance(exports, list) or not exports:
        errors.append("exports: at least one reviewed export is required")
        exports = []
    seen = set()
    for export in exports:
        export = file_record(export, "export")
        export_id = export.get("export_id")
        if not isinstance(export_id, str) or not export_id or export_id in seen:
            errors.append("export: unique export_id required")
        else:
            seen.add(export_id)
        width, height = export.get("width"), export.get("height")
        ratio = RATIOS.get(export.get("aspect_ratio")) if isinstance(export.get("aspect_ratio"), str) else None
        if type(width) is not int or type(height) is not int or width <= 0 or height <= 0 or not ratio or width * ratio[1] != height * ratio[0]:
            errors.append("export: dimensions must match its supported aspect ratio")
        duration = export.get("duration_seconds")
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            errors.append("export: positive measured duration required")
        if export.get("inputs") != expected_inputs:
            errors.append("export: changed inputs invalidate the previous render review")
        for key in ("media_probe_evidence", "playback_evidence", "audio_evidence", "caption_safe_area_evidence", "disclosure_review_evidence"):
            evidence = export.get(key)
            if not isinstance(evidence, dict) or not nonblank_string(evidence.get("reference")) or evidence.get("reviewed_export") != export_fingerprint(export):
                errors.append("export: " + key + " must bind independently to the reviewed output hash and measured metadata")
    return {"errors": errors, "exports_checked": len(exports), "publication_authorised": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True, help="Explicit local media root; files must remain inside it")
    args = parser.parse_args()
    try:
        result = validate(json.loads(args.manifest.read_text(encoding="utf-8-sig")), args.root)
    except (OSError, ValueError) as ex:
        parser.error(str(ex))
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["errors"]))
