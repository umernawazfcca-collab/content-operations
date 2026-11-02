# Host adapters and scheduled guide releases

## API-first scheduling
Choose one configured scheduler per platform using current authenticated capability and approved routing. Simplified and Metricool are supported workflow examples, not preconfigured accounts. Do not infer direct publication or reminder-only mode from the provider name. Verify account, media format, permissions and saved-job behaviour.

Discover tools by capability on every host. Installing a skill does not transfer OAuth or establish connectors. Do not invent tool names.

Simplified preflight:
1. Read accounts, workspace info, existing posts and drafts (paginate). Inspect native scheduled posts where an older native job may exist. An empty Simplified history is not an empty LinkedIn queue.
2. Read workspace timezone. Do not change this setting implicitly.
3. If a create call accepts YYYY-MM-DD HH:MM without an explicit timezone field, do not assume its interpretation. Confirm which zone the current endpoint interprets using current documentation/provider confirmation or an existing saved-job comparison. If confirmed to use the workspace zone, convert the approved instant using IANA timezone rules, including DST; do not subtract a fixed number of hours. Persist approved instant, provider local date, interpreted zone and verification evidence. A read-query tz parameter does not set the create timezone.
4. Confirm the selected media format and audience. Use the exact approved media, message, LinkedIn audience and converted date in one create operation. Do not include auto-comments without their own finished approval.
5. Save returned ID; read it back using the configured reporting timezone. Compare account, media, caption, instant, mode and state. A mismatch needs immediate reconciliation and authorised correction before the due time. Do not create a second job. If timezone semantics cannot be established, do not guess or silently publish at the wrong time: resolve that configuration first or select the approved native fallback after checking both queues.

A provider's auto-comments parameter may post prewritten comments after publication; verify its current semantics. It is not an inbox reader or reactive comment-response engine. Discover real comment/history capabilities separately; use an authorised browser when API coverage is missing.

## ManyChat solution with scheduled reels
Verify the current supported provider API surface before binding a reel-comment trigger. A flow-listing or message-sending API is not automatically a trigger-editing API. Do not call undocumented internal endpoints or treat sendFlow as a reel-binding API. A generic automation bridge or API key alone does not solve this missing control.

Use this operational sequence, with one approved host responsible throughout:
1. Before scheduling: prepare the exact flow specification and public PDF destination, inspect the existing saved flow, preserve its edits and obtain finished-output approval. Confirm the host can actually open the authenticated ManyChat account and inspect a saved flow. Check that an eligible test account and approval for the concrete test are available.
2. Schedule the approved Instagram reel in the configured scheduler. Persist the job ID, approved time and expected visible fingerprint. Confirm whether the provider performs server-side publication or needs an approved human step.
3. Arrange an explicitly approved, release-specific publication follow-up on the same host. This is separate from configured comment checks. After the due time, read the saved scheduler job; only a confirmed published URL/ID and matching native reel allow binding.
4. The agent uses the host's authorised browser to open the existing ManyChat flow, select that exact reel, apply only the approved changes, save and reopen. It records the flow ID, saved version and reel association. No all-posts/next-post shortcuts, and no resetting approved gates or edited copy.
5. With the separate concrete test approval, run the fresh-account trigger test described in delivery-and-comments.md. Record public acknowledgement, required button/gate, correct private link delivery and destination. Only then mark delivery working.
6. Once active, ManyChat handles qualifying incoming comments continuously on its servers. The explicitly approved comment service checks health, missed requests, replies and evidence. It need not stay open to perform every guide send.
7. On publication or binding failure, leave the unresolved state explicit and alert the owner. Use only an already approved fallback; never post a blanket 'check DM' message. Preserve existing live flows.

A scheduled reel has no selectable exact public reel before publication. This introduces a potential gap before binding. Before approving a guide CTA, agree one of: an operator/agent present at release with approved manual coverage, or an explicitly approved temporary public-link route until the exact flow passes. If neither is available, hold scheduling of the guide-CTA output. Changing a caption already approved needs renewed approval. Never silently use 'next reel' to remove the gap.

Any publication follow-up needs explicit scope, timing, observation window and stopping conditions. Do not infer a background runner from these instructions. Prefer a supported provider event only when the integration and event verification are separately approved. No webhook installation is bundled.

## Portability and readiness gate
A host is operationally ready only when all are evidenced: authenticated correct accounts; queue/read/create capability; timezone semantics; native post inspection; authenticated ManyChat browser; saved-flow inspection; eligible test route; comment and DM-history access; persistent shared folder; one approved service runner.

Recheck every required capability on the selected host. Failure of one provider's browser login does not establish failure of independent authorised API/native access. Preserve denials and coverage gaps rather than bypassing them. Owner login/consent occurs in the provider UI, never by sharing passwords or one-time codes.

Use the shared tracker and release IDs across hosts. A handoff transfers operating context, not approval or authentication. Stop the previous runner before an approved host transfer. Never run simultaneous comment services on different hosts. See [portable host preflight](portable-hosts.md) for Codex, ChatGPT, Claude and Gemini runtime and tool boundaries.

