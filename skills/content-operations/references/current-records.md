# Resolve the current records

This package contains incomplete templates, not campaign state. Resolve the operator's explicitly configured canonical tracker, current handoff and action log. Reconcile conflicting pointers before writing. Do not select a file merely because it is newest, recreate a retired tracker or upload private state to another AI provider to make it accessible.

Record the resolved path, handoff reference, scope and observed schema in private evidence. Read only relevant records. Preserve the append-only log and single-writer/lease controls. Never copy populated trackers, approvals, messages or private media into source control or packages.

## Schema boundary

`scripts/check_records.py` accepts version 1 or 2 of the explicit `releases` schema with at least one row. The read-only adapter handles supported version-1 `scheduled` input; the native checker rejects that layout. Unsupported, unversioned, empty or malformed input fails closed. An imported snapshot cannot be certified even if flags are edited. A checker failure is not evidence that publication failed. Do not rename keys, strip provenance or invent evidence to pass.

Platform identifiers are exactly `instagram`, `linkedin`, `tiktok` or `youtube`. Supplied PDF fingerprints must be lowercase SHA-256 values. Comment timestamps require offsets and are compared as instants.

When supplied, `writer`, `service` and `service.cadence` must be JSON objects. The same rule applies to each release's `asset`, `approval`, `scheduler`, `native_verification`, `guide`, `automation`, `comments`, `completion`, `production` and `performance` sections. Explicit `null` is not an object and is rejected; omission or `{}` may represent an unknown optional section when no claimed state requires its fields. Nullable fields inside an object remain valid where their own contract permits them: for example, `{"writer":{"lease_expires_at":null}}`, an inactive service's `{"cadence":{"anchor_at":null}}`, or a release's `{"performance":{"observed_at":null}}`. An active service still requires a valid anchor and positive cadence; `null` never supplies evidence.

Recorded timestamps are ISO strings with an explicit UTC offset (including `Z`). Missing or `null` optional timestamps mean unknown; blank strings, booleans, numbers, arrays and objects are invalid substitutes. This applies to tracker updates, writer leases, service start/expiry/anchor, release check/planned/scheduled/publication instants, approval/native/guide/flow/performance observations, comment check/attempt/due/window instants, and action-log `timestamp`/`slot_due_at`.

The claimed state determines which instants are mandatory: `scheduled` needs `scheduled_at`; `verified` needs `native_verification.checked_at`; a configured/working flow needs `configuration_verified_at` and `guide.public_pdf_verified_at`; working delivery also needs `verified_at`. A completed non-Instagram guide route needs the PDF verification instant. An active service needs its cadence anchor. Other optional instants may remain unknown, including in historical/manual review records; the validator does not invent them or infer freshness from a parseable value. Delivery testing cannot predate configuration verification, and partial comment scans cannot advance the successful-scan instant.

Supplied post, asset, guide and flow URL fields must be syntactically valid HTTP(S) URLs without embedded credentials; `null` remains unknown when the field is optional. This is a syntax check only, not a network request, public-access check or delivery receipt. Malformed record fields produce structured validation errors (exit 1); unreadable JSON/files, including JSON nesting beyond the runtime parser's limit, produce CLI input errors (exit 2, no traceback). The parser limit is not raised automatically. Neither path modifies the input.

```text
python "<skill-folder>/scripts/check_records.py" "<canonical-tracker>" --log "<private-action-log.jsonl>"
```

## Service model, not standing permission

Configure `service.cadence.interval_hours` and `service.window_hours` as positive integer hours, with an offset-bearing cadence anchor and explicit service start/expiry where applicable. No cadence, window or standing authority is bundled. Ask for explicit approval of service owner, scope, cadence and expiry; do not create or alter a runner during installation.

The `--slots` helper computes expected slots only. It neither inspects a runner nor proves execution. Slots fall strictly after publication, at/after a supplied service start, and no later than the original window end or earlier expiry. Late start never renews the window. No anchor means no slots. Inputs whose calculation exceeds the supported timestamp range produce a CLI input error (exit 2, no traceback); valid final slots do not require constructing an out-of-range next instant.

```text
python "<skill-folder>/scripts/check_records.py" --slots "2030-01-01T10:00:00+00:00" --anchor "2030-01-01T09:00:00+00:00" --expires-at "2030-01-03T09:00:00+00:00" --interval-hours 4 --window-hours 48
```

These synthetic instants are not a schedule to install. Keep failed attempts, partial coverage, last successful cursor and missed slots separate. Never backfill success or extend authority automatically.
