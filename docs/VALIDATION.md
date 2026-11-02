# Validation and release boundaries

This MIT preview is for offline evaluation. Local validation and bounded host tests do not establish production readiness or the truth of recorded evidence.

## Current evidence

- **130 local checks passed:** 16 structural self-checks and 114 regressions.
- Independent review covered evidence types, approval and asset binding, timestamp/URL validation, tracker adaptation, output-path safety and package identities. No blocking code findings remained in the reviewed candidate. This is bounded review, not a blanket security clearance.
- A separate chronological enumeration agreed with 6,480 synthetic slot cases across timezone offsets, publication/anchor boundaries, service starts and expiries.
- All four target archives rebuild identically. Release documentation does not change their bytes. Exact hashes and actual host results are in [host support](HOST_SUPPORT.md).
- Claude Code and Claude web passed bounded synthetic acceptance. ChatGPT Work passed bounded conversation-reported acceptance: 14 expected outcomes, eight reported core hashes matching the reviewed ZIP and eleven input hashes reproduced locally. The raw ChatGPT tool transcript was unavailable.
- Claude Desktop skill acceptance is NOT RUN separately. Codex CLI and Gemini Apps execution remain blocked/unverified. Gemini CLI and the OpenAI plugin route are NOT RUN.

## Validator behavior

Valid records return exit 0. Malformed record content returns structured errors with exit 1. Unreadable input returns exit 2.

Evidence fields require nonblank strings; approval hashes must be valid SHA-256 values and bind the approved version. Approved or scheduled rows need recorded approval. Required timestamps must be valid offset-bearing ISO strings. Supplied malformed optional timestamps, URLs and nested enum types produce validation errors rather than tracebacks.

Deep JSON decoder recursion is handled at the JSON input boundary, not by a general catch-all. The 200,000-level tracker and action-log controls return input error 2 without tracebacks. Slot arithmetic outside the supported timestamp range also returns input error 2. Valid final-year slots and empty windows do not construct an unnecessary overflowing next instant.

Missing or null optional fields remain unknown where the contract allows them. Supplied `writer`, `service.cadence` and `performance` sections must be objects, not null; nullable optional fields inside those objects remain valid. See the [record contract](../skills/content-operations/references/current-records.md).

Regression controls include malformed and valid inputs, equivalent timezone offsets, duplicate identities, safe read-only ingestion, unchanged input bytes and deterministic CLI outcomes. An imported tracker remains a blocked review snapshot; the adapter does not invent missing approvals, publication or delivery evidence.

## Presentation verification

The [walkthrough](walkthrough/README.md) is a synthetic simulation, excluded from every host archive. Source checks pass. A reviewer reported scoped browser checks in a Chromium preview at 1024, 375 and 320 px, including exception-gate clicks and keyboard behavior; raw browser receipts were unavailable for independent inspection. Reduced-motion runtime, screen-reader and non-Chromium/physical-device checks are **NOT RUN**. See [verification.json](walkthrough/verification.json). The PNG/GIF are conceptual artwork, not a browser recording.

## Before live actions

1. Verify the actual host's reference access, execution and connector capabilities using synthetic inputs.
2. Resolve the authorised canonical tracker, account identities, final asset versions, approval scope, service owner and current evidence.
3. Test each separately authorised route and inspect native results, preserving uncertain outcomes and duplicate safeguards.

This package does not install a scheduler or approve publishing, replies, guide sends or recurring service. No live integration was tested during preview acceptance. Keep operational records, private receipts and credentials outside the repository and host archives.
