---
name: content-operations
description: >-
  Coordinate approved content releases across LinkedIn, Instagram, TikTok and YouTube. Prepare assets and captions, review trackers, select one scheduler, verify publication, manage approved guide delivery and replies, and recover failures. Use for content operations and campaign follow-through. External actions require explicit scoped approval; loading this skill never starts a service.
---

# Content Operations

A portable, offline-first workflow for finished content and follow-through. Substantive writing, brand voice, accounts and service authority are supplied by the operator, not inherited from this package. No account connection, publication permission or standing reply authority is bundled.

## Start here on every run

1. Read the current request, scope and approvals. Setup and review-only requests permit no scheduling, publication, uploads, messages, test comments or changes to live flows. A scheduler draft is an external write.
2. Resolve the configured canonical tracker and action log using [Current records](references/current-records.md). Re-read relevant queue, native platform, link and flow state before reporting current status or retrying. Saved plans and this skill are not live evidence.
3. Read [Portable hosts](references/portable-hosts.md), select the actual run mode and verify exact account identity and release IDs. Hosts do not share credentials, paths or tool names. Missing capabilities remain untested/unavailable. Continue only independent review when access is missing.
4. Read [Host adapters](references/host-adapters.md), [Release protocol](references/release-protocol.md), [Delivery and comments](references/delivery-and-comments.md) and [Review and recovery](references/review-and-recovery.md) as applicable.

## Configuration and shared state

Resolve an existing operator-authorised workspace, canonical tracker, action log, handoff, content folder and evidence folder from explicit local configuration. Keep populated configuration outside this repository. Do not infer a filesystem location from a host name or create a second canonical tracker. A host without canonical writer access can review authorised snapshots only.

Use [release](templates/release-tracker.template.json), [action-log](templates/action-log.template.json) and [host-check](templates/host-check.template.json) templates as incomplete contracts, never live records or migration instructions. Record publishing timezone, scheduler per platform, permitted resource types, voice preferences, guide policy, approval scope and service cadence explicitly. Do not infer any of them from examples.

Preserve sources and approved exports. Keep new revisions additive, with clear version/hash and evidence references. Use the operator's authorised folder convention rather than a bundled personal layout. Save the current tracker revision before updating its projection and append an action event; never overwrite historical evidence. Store no secrets or unnecessary private-message content in the records.

Only one operator may mutate a release's records or external state at a time. Reserve ownership before an authorised action; re-read the lease and file revision immediately before writing. A JSON lease is not an atomic distributed lock. Across hosts, use an explicit single writer and an appropriate exclusive lock, or stop writes until ownership is resolved. Do not steal a stale lease while an external result is uncertain. Reconcile synced versions before writing.

Use one stable `release_id` per campaign/platform/account/intended edition. An asset revision is not a new release. Record approved asset and caption hashes, exact account, offset-bearing publication time, scheduler/job ID, actual URL, status, guide destination/hash, flow/test state, latest successful comment check, missed slots, next action and evidence references.

## Status and evidence contract

- `planned`: proposed output.
- `approved`: exact finished output approved.
- `scheduled`: saved job re-read with correct account, media, caption and time.
- `published`: fresh provider/platform evidence plus an actual URL.
- `verified`: native post inspected for account, asset, caption, accessibility and disclosure.
- `failed`: documented failed attempt with error and recovery owner.

Keep `last_known_status`, `observed_status`, evidence level and timestamp separate. Unknown access is not failure/deletion; a missing queue item is not publication. Stale verification does not establish present availability.

Publication, guide delivery and service completion are separate. `configured` requires saved configuration evidence; `working` additionally requires authorised end-to-end evidence for the exact guide and configuration. `complete=true` requires all applicable release/delivery/service obligations, no unresolved failure and a final handoff. Run `scripts/check_records.py` on a supported schema before reporting completion. Unsupported or empty input blocks the check; it is never a zero-row pass. Structural validation does not establish that evidence is true.

For legacy `scheduled` input, use [Tracker ingestion](references/tracker-ingestion.md) and `scripts/adapt_tracker.py` read-only. Imported snapshots are review material, never actionable queues or certificates. Resolve identities and current evidence through the canonical writer. Never fabricate missing verification or alter provenance to obtain a pass.

## Approval and execution

Approval binds the exact asset version, caption/title, platform/account, time, destination and action. A batch approval must enumerate its outputs or exact template text, substitutions, recipients/releases and expiry. Style approval, draft permission and historical approval do not authorise new external actions. Material changes invalidate affected approval. Sensitive questions require escalation to the owner.

Select one scheduler per post using current account/format capability and explicit configuration. Never switch providers or republish because status is unclear. Reconcile every unknown result before retrying. Preserve existing jobs and flows unless a separately authorised change applies.

Only share resource types explicitly approved for public distribution. Verify the actual public download journey; HTTP 200 is insufficient. Editable source files and private assets remain private without separate permission. Use rights-cleared media, approved narration and reviewed claims. [Draft production](references/draft-production.md) provides an optional QA handoff, not a renderer or publisher.

Respect the selected host's permission rules. Do not bypass denial with a different host, hidden reminder, alternative scheduler or new connection. Installing this skill creates no service. Any recurring work needs explicit scope, owner, cadence, anchor, expiry and supported runner. One runner owns each scope; retain missed/partial coverage, avoid duplicate replies and never extend a window automatically. The current schema's supported service model is documented in [Current records](references/current-records.md); it grants no standing authority.

## Reply quality and reporting

For reply wording and exact targets read [Conversation replies](references/conversation-replies.md). Verify both public history and private delivery history. Do not invent the owner's experience, biography, commercial position or voice preferences. Private delivery evidence is not public reply evidence, and an accepted send is not a delivery receipt.

Report what changed, fresh evidence, blockers, next action and owner. If no live inspection occurred, say so and give the last observation time where known. Never promise virality, guaranteed delivery, unattended service or host compatibility from installation or a local test.
