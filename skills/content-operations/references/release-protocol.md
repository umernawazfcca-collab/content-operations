# Release protocol

Apply [Channel policy](channel-policy.md) before sending or scheduling. LinkedIn comments require human posting; routine-comment approval does not authorise automated submission. Other actions still require their own supported capability and existing approval.

## Prepare the finished output

Read the topic's handoff, source assets and latest explicit corrections. Preserve sources. Create an additive platform export, cover, subtitle file where useful and exact short caption/title. Record duration, dimensions, audio/playback check, subtitle safe area, typo check, disclosure setting and source/approved hashes. Watch the beginning, representative middle and ending, with audio when available; label sampling or silent review accurately. Use synthetic finance examples or cleared source material. Escalate unsupported tax/legal claims to the appropriate review; do not invent a client story.

LinkedIn: lead with the audience problem, useful consequence and precise approved resource CTA; native video/document constraints must be checked for the chosen format. Instagram: short reel caption, exact campaign keyword, guide route and appropriate disclosure. TikTok: short caption/cover/title adapted to mobile; do not inherit Instagram's DM promise. YouTube: an appropriate title and short description; check whether a Short or long-form format is intended. Do not promise DMs. Preserve the approved audio/script keyword even when changing platform caption wording. If the video contains an unfulfillable CTA, flag it before publication rather than silently changing only the caption.

For a guide, verify anonymous GET after redirects, PDF Content-Type and `%PDF-` signature, campaign content and SHA-256 against the approved PDF. Open the landing article and click through the real download journey. A JavaScript shell returning 200 is not an inspected article. Do not link to private OneDrive shares or signed private download URLs. Check that the public journey does not offer editable files. Public deployment or changing links still needs separate approval. Record exact link and any approved campaign tags; do not add identifying query parameters.

## Select one scheduler

Use the operator's explicitly configured scheduler for each platform. Resolve correct account/network identity live and verify media support, autopublish/reminder mode, timezone and disclosure controls. An unavailable route remains blocked until an alternative is approved; never create a competing queue silently.

For a provider such as Simplified, inspect current connected account type, auth health, format support and scheduling mode. Documentation or an API schedule option is not proof of successful publication. Verify timezone semantics before creating a real approved job, then read it back. Select a native fallback only after checking all queues and proving the old job cannot also publish. A reminder-only route needs a named human owner. Do not create a test post merely to discover capability. See [Host adapters](host-adapters.md).

## Prevent duplicates and partial failures

Before any create, update or retry, re-read the tracker, action log, all relevant scheduler queues, native scheduled list and actual feed. Match release ID, account, caption, asset fingerprint, destination and nearby posting slot. Provider job IDs may change while UUID remains stable; retain both. An empty list from one provider proves nothing about other queues. Paginate to cover the defined window and record query/filter coverage.

Reserve an intent with a stable idempotency key based on logical release and action, not a random retry ID. Re-check ownership. Execute only the approved operation, save the returned job ID and re-read it. Log the result before releasing the lease. On timeout, record `unknown_result`; reconcile using job ID, provider UUID and feed before retrying. Do not create again or switch schedulers while the first result is unresolved. A scheduler change requires proof the old queued job cannot publish and approval for any changed time or output. Do not cancel/delete existing posts without authorisation.

Use the configured publication timezone, not the machine default. The adapter normalises supported times to UTC; this does not set the publishing timezone. Persist ISO timestamps with offsets plus the IANA zone. Confirm the provider's display zone. Keep planned, scheduled and actual publication times separate; scheduled `publicationDate` is not automatically the actual native publish time. Ambiguous analytics timestamp zones stay raw until documented or reconciled with native evidence.

## Verify and hand off

After the scheduled time, query the saved job, open its actual public URL and inspect native content. Confirm the configured account, correct asset/version or visible fingerprint, caption/title/CTA, disclosure and availability. A scheduler `PUBLISHED` response supports `published`; it does not independently establish `verified` playback. Public/native access failures remain evidence gaps, not proof the post failed.

Save URLs, timestamps and small evidence excerpts/screenshots in the topic output folder. Maintain the shared action log and tracker pointers. Link the exact Instagram reel to its ManyChat record. Recheck resource links and automation status before reporting a guide campaign working. At the end of the explicitly approved service window, complete the final comment scan/review and log unresolved requests before marking the service completed.
