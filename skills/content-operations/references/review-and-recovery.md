# Weekly production, measurement and recovery

## Explicitly requested production planning

Review the existing week's release and action records first. List what is actually published, still scheduled, awaiting approval, blocked or unmade. Plan the coming week by topic, reader, format and audience problem. Separate a production target from an approved posting slot. Planning does not activate a recurring automation.

For each topic track source/script readiness, recording or avatar look, asset/export/version, caption set, guide/article/PDF, disclosure checks, approval, scheduler, publication verification, ManyChat binding/test and comment coverage. Use only the explicitly approved presenter and voice; record their rights and approval evidence. Use full-frame editing for real recordings. Keep the latest approved asset untouched. Paid generation and rerenders need specific permission and any required spending approval.

Update `operations/weekly-plan.md` with this week's remaining work, owner, target, blocker and next action. Carry forward unfinished items explicitly; do not count a template, scheduled post or AI promise as a finished release.

## Performance review

Read metrics live for a fixed platform/post/date range and record the extraction time and source definitions. Review comparable post ages such as first 24 hours and first seven days when data exists; do not compare a two-day post with a five-day post as though exposure were equal.

Prioritise retention/watch time, saves, shares, meaningful comments and guide clicks. Distinguish people from events, reach from views, sent DMs from delivered DMs and flow-button clicks from website PDF clicks. Document denominator and paid/organic scope for each rate. Null/unavailable is not zero. Do not silently replace deprecated metrics. Inspect comment text to classify meaningful discussion; a comment count is not that classification.

Use native analytics where Metricool lacks retention or a required definition. Website analytics need a verified source and approved link tags; do not install tracking or change a public link during a review. Separate CTA failure, insufficient audience exposure and a weak content hook. Propose one concrete change to test next week; don't promise virality or infer causes from a tiny sample.

## Recovery table

| Failure | Read-only diagnosis | Authorised recovery | Completion evidence |
| --- | --- | --- | --- |
| Expired access | Identify account, affected operation and last successful read; do not expose tokens | Ask the owner to reauthorise in provider UI; no password/OTP collection or silent account switching | Fresh successful account-scoped read, plus resumed task-specific check |
| Failed scheduled post | Read job/provider error, native feed and other queues; distinguish failure from unknown result | Fix only approved parameters; changed media/caption/time requires updated approval; retry once after diagnosis then escalate persistent failure | One intended post/job, native URL and verification; no duplicate |
| Unknown create/send result | Preserve idempotency key and request reference; search job/message/feed history | Reconcile first; no blind retry or scheduler switch | Definitive remote outcome or unresolved blocker retained |
| Broken article/PDF link | Anonymous GET, redirects, content type/signature, exact campaign/hash; inspect rendered download journey | Prepare corrected public route or replacement PDF for approval; do not edit site, caption or flow without scope | Correct public PDF and article click-through rechecked; approved consumers reconciled |
| Inactive/wrong/unverified ManyChat | Inspect exact reel, saved/live version, overlap, gate/button, destination, message and test logs | Preserve user edits; prepare minimal diff; activation/rebinding/test requires explicit finished-flow approval | Reopened saved configuration and fresh permitted end-to-end evidence |
| Missing public acknowledgement | Check first-comment restriction, actual reply history and trigger result | Fresh authorised test; never infer repaired from a successful DM | Public reply and correct private guide delivery both observed |
| Missed comment checks | Preserve failed/missed slots and last successful cursor; check remaining window | Catch up at next authorised execution, with duplicate checks; no auto-extension or invented historical successes | Coverage and actual catch-up time logged, unresolved requests listed |
| Private editable exposed | Record the public URL without spreading the file | Escalate immediately; prepare removal/replacement for owner approval | Public exposure check cleared by evidence; do not mark complete beforehand |

Preserve the previous status and log the failure; don't relabel a published post as failed solely because analytics or browser access expired. Use component status and next action. After any recovery, re-read the affected system and all downstream dependencies before clearing the incident. Failed/unknown outgoing actions cannot be turned into duplicate retries under the guise of maintenance.
