# Read-only tracker ingestion

`scripts/adapt_tracker.py` supports the observed canonical `schema_version: 1` / `scheduled` layout. It creates a review view, never changes the source, and never schedules, replies, sends or calls a provider. Normal ingestion prints only aggregate requirements. The existing `check_records.py` still validates the native `releases` contract and explicitly blocks imported snapshots from being certified as complete.

```text
python -B scripts/adapt_tracker.py "<current-canonical-tracker.json>" --namespace "example-workflow"
```

Resolve the source from current handoffs before each run. The namespace is a stable logical workflow key, not a path, secret, date or arbitrary session ID. Reuse it across hosts. Ingestion exit `0` means rows were read; `live_ready` and `external_actions_permitted` remain false. Exit `1` means invalid/unsupported input or unavailable/unsafe output. Neither result is live publication evidence.

If a persistent review view is needed, add `--out "<new-private-snapshot.json>"` with an existing private parent directory. Output must be a new ordinary local file. Windows stream syntax (`file:stream`), device/reserved names, network/device namespaces, dot segments, trailing-dot/space names, existing files and linked/reparse parents are refused before creation. Output creation stays exclusive. Source bytes are checked before and after. A changing source invalidates the view; coordinate with its writer and retry only after reconciliation. No source or output file is ever replaced. A converted snapshot contains the **complete original private document** for provenance: keep it outside Git, packages, public docs and AI uploads. It is not a second canonical tracker.

The shared guard uses no-follow stat metadata, Windows reparse attributes/tags and regular-file link counts, including on Python 3.10/3.11 where `Path.is_junction()` does not exist. Package/install sources also reject hardlinked files. Use an operator-controlled directory without concurrent file/link changes: these checks are preflight guards, not an atomic defence against hostile path swaps. Real link/race operations and older-interpreter execution have not been exercised; supplied metadata covers those detector branches without creating links.

See Python's [stat metadata](https://docs.python.org/3.10/library/os.html#os.stat_result) and Microsoft's [file/path naming rules](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file). Stream/device input names are also rejected before reading a tracker.

## Supported mapping

| Source | Review projection |
| --- | --- |
| Non-empty `scheduled`, version exactly integer `1` | Version `2` / `releases`, plus a read-only `adapter` envelope |
| Canonical platform or observed `LinkedIn` label | Canonical platform; unknown/case/space variants explicitly unresolved |
| `Metricool`, `Simplified`, `LinkedIn native` scheduler strings | `scheduler.name` object; a candidate job ID, never fabricated verification evidence |
| Existing valid `release_id` | Preserved verbatim; duplicates are retained and flagged |
| Missing ID with provider `id`, then `uuid`, then supported native-post URL | Proposed `import-` plus full SHA-256 of domain, namespace, platform, provider (or `native` for post identity), identity kind and value |
| No stable identity | Diagnostic row-fingerprint ID and an explicit non-actionable identity blocker |
| Explicit `scheduled_at` in the legacy variant | Parsed offset-bearing instant; missing does not fall back to an ambiguous old publication date |
| Compact `date` as aware ISO, `{date,time,timezone}` or `{dateTime,timezone}` | Verified parsing into UTC; ambiguous/nonexistent/unknown local zones block scheduling |
| Historical status, approval, service, guide, gate and delivery fields | Preserved in the original document; projected current status/evidence remains unknown until reconciled |

All rows remain present. Source bytes have a fingerprint; the parsed complete document and each row have canonical JSON fingerprints, with source-index pointers. Byte fingerprints are provenance checks, not signatures or proof that the historical evidence is true. Duplicate JSON keys and non-finite numbers are rejected. Archived/current provider, job or identity conflicts become explicit blockers.

Integer provider job IDs and their string equivalents share identity. The account is deliberately excluded from generated-ID material until resolved, so filling a missing account cannot silently change the proposed ID or hide a duplicate job. This can conservatively flag equal job IDs across accounts; reconcile such collisions with an operator. Native URL identity uses the Instagram shortcode across `/p/` and `/reel/`, LinkedIn activity ID across supported post/URN URLs, TikTok video ID independent of handle, and YouTube video ID across supported URL forms. Unknown/malformed URLs stay unresolved; arbitrary paths are not treated as stable native IDs. This does not resolve every possible redirect or platform URL through a live API.

Adapter version **2** introduces the stricter native identity and path rules. Version-1 candidate snapshots are explicitly rejected; re-ingest the unchanged canonical source and review proposed-ID differences instead of silently upgrading a snapshot. No live ID is rewritten. Within version 2, repeated unchanged ingestion and an unchanged converted snapshot are idempotent; row order and mutable status/topic changes do not change anchored IDs. Edits to a converted projection are rejected on re-ingestion. A namespace, provider-job identity or stable-anchor change requires explicit review; never use it to create a new job.

## Reconciliation before any live action

The summary returns actionable requirements by code and affected row count. The separate private view records them per row. Resolve current handoff/revision/writer access and review every proposed identity. Confirm account, exact output approval and current queue/native observations. Determine guide applicability explicitly; guide campaigns require exact approved keyword/PDF/version/hash and route evidence. Instagram additionally requires the explicitly approved source template, exact-post trigger, follower gate and recheck loop; actual end-to-end evidence remains distinct from saved configuration. Resolve any explicitly approved runner's anchor/scope/expiry and full comment/private-delivery duplicate history.

The adapter never synthesises approval, `guide.required`, follower verification, end-to-end evidence, delivery receipts, active jobs or a live service. A historical assertion can inform a fresh check but cannot be promoted automatically. Unknown does not mean broken or absent. Reconcile through the authorised canonical writer and append-only log; only a separately reviewed canonical update can record newly verified facts. Do not remove `adapter`, rename fields, or set flags merely to obtain a passing checker result. No writer migration or live install is included in this tool.
