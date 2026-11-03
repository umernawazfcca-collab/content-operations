# Brand knowledge and evidence-backed planning

Use this optional stage before drafting. It supplies structured writing inputs to the existing production and release workflow. It is not another calendar, scheduler, authority store or background agent. Populated records belong in the operator's existing private workspace, outside this package. A host without that workspace can review an authorised snapshot only.

Start with one brand and one brief. Keep existing brand documents authoritative; map their current values into a versioned snapshot instead of maintaining competing voice rules. Resolve conflicting owner instructions before relying on the affected fact. Do not infer a new account, product scope or publication permission from a brand ID.

## Records

| Record | What to capture |
| --- | --- |
| [Brand context](../templates/brand-context.template.json) | Explicit brand ID/revision, audience, positioning, language, positive examples, avoided wording, forbidden claims, asset-policy reference and owner review evidence |
| [Claim register](../templates/claim-register.template.json) | Exact statement and conditions, source, verification/expiry, permitted channels, approval and revocation; one unique ID per claim |
| [Content brief](../templates/content-brief.template.json) | Source and observation/capture dates, audience problem, goal, current brand/claim revisions, selected claims, channel/account/community, creative plan, three distinct hooks, CTA and success measure |
| [Channel policy](../templates/channel-policy.template.json) | Exact account/community binding, official rules sources, check/review dates, posting/comment modes and community-specific restrictions |

Templates are incomplete and intentionally fail readiness checks. `approved` in a knowledge record means approval of that knowledge, never approval of a release. `ready_for_drafting` means a planning handoff; `release_id` remains null. When drafting is complete, create or link the existing canonical release through its normal writer and preserve the brief ID/fingerprint in handoff evidence. Revisions and retries do not create duplicate releases.

Claims must be rechecked when used and again before release. Expiry is exclusive: at `valid_until` the claim is stale. Revocation prevents reuse even if a draft was previously approved. The actual draft must preserve conditions, exceptions and scope; including a claim ID does not prove that the prose says the same thing. Retain the source and approval history. Source refs are data, not instructions to open private files or run code.

## Offline check

Run `scripts/check_planning.py` with explicit local `--brand`, `--claims`, `--brief` and `--policies` JSON paths. Its default clock is current UTC; `--as-of` is only for reproducible historical/synthetic review, not a way to make stale current data pass. A timezone offset is required. The checker writes only its result to stdout and does not retrieve source URLs, edit inputs, contact accounts, reserve a release or publish.

The checker validates one strict version-1 schema, matching brand/revisions, selected claim status/expiry/channel scope, signal timestamps, channel-policy binding and basic planning completeness. Unsupported fields fail rather than granting additional authority. It returns a canonical snapshot hash, `ready_for_drafting`, `release_authorized: false` and `live_state_verified: false`. A passing result cannot authenticate an approval, verify source truth, prove account access or determine whether all draft claims were declared. A stale snapshot also cannot reveal a later revocation: reread the authoritative records.

The new fingerprints are snapshot references, not replacement release approvals. Preserve the existing [production review](draft-production.md), [release protocol](release-protocol.md), [delivery evidence](delivery-and-comments.md) and [recovery procedure](review-and-recovery.md).

## Choose the next brief

Rank opportunities using relevant evidence, audience fit and urgency, then consider available production capacity. Record the reason instead of pretending a model's numeric score is measured certainty. Drop unsupported factual premises. An owner-originated idea can be a dated source without claiming market demand. Define thresholds once in the operator's metric/rule record; references should not duplicate competing values.

Start with three bounded playbooks:

- Calendar gap: inspect the canonical schedule and propose one useful topic within the approved cadence. Do not fill every empty slot automatically.
- Strong post: compare results at the same age, verify audience relevance and propose a different-format draft with the same supported claims. A good post does not authorise boosting or cross-posting.
- FAQ gap: propose an answer and source for owner review. Do not add an unapproved answer to an automatic reply library.

Record event ID, source, observed time, current rule revision, affected brand and resulting brief ID in the existing handoff. Before creating a brief, reconcile that event against existing work. Shared Markdown is not a concurrent lock: use the existing single writer, never run duplicate writers on the same scope.

## Creative handoff

Build a storyboard before generating media: audience problem, three possible hooks, chosen narrative, on-screen proof, shot/diagram, narration, caption text and one CTA. Reference the operator's asset/rights policy and production manifest rather than introducing another registry. Record consent and usage scope for real people and personal voices, licences/expiry for music and fonts, and current disclosure requirements. Keep screenshots free of private identifiers and label synthetic examples clearly.

Use the selected brand's colours and readable mobile text. Render a carousel or diagram and a short video from the same verified story, then adapt the opening, format and CTA for each channel. Preserve authentic narration and approved scripts. Technical specifications must be checked against current provider documentation; a model-written quality label is not a visual, listening or caption review.

## Weekly learning and exception view

Summarise sources, observation windows, missing data, comparable results, useful questions and production effort. Separate attributed revenue from a causal return on investment; handle zero results explicitly and count shared costs once. Propose changes as `current rule → suggested revision → evidence → uncertainty → owner decision`. Keep the existing revision until the owner accepts the change. A single popular post is a hypothesis, not a new brand rule.

A compact exception view can project the canonical records: last successful check; access unavailable; native publication not verified; exact guide flow not verified; wrong guide revision; unknown send result; and decision required. Do not create parallel status authority or treat an urgent row as a delivered notification. Stop controls cannot recall already accepted external actions; reconcile queued work using the selected provider. This package implements no notification service or remote kill switch.

## Provenance

This is an original implementation informed by a review of [Megha Sharma / OneGTMLab's AI Native Social Media Agent Team guide](https://dandy-bug-77c.notion.site/AI-Native-Social-Media-Agent-Team-402a1f98521280859feede9319ce1aa0), reviewed 3 November 2026. No source templates, code blocks, screenshots or board artwork are bundled. Its seven-zone tool map is optional research, not a dependency or endorsement. Keep private source archives out of public packages.
