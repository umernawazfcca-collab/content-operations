# Optional draft-production handoff

Use this when assembling drafts or comparing export variants. The substantive writer remains separate. Use the approved script, rights-cleared recording and explicitly approved voice/presenter identity. Never invent experience, disclose client information or substitute an unapproved person/voice.

Set manifest `policy.context`, `policy.expected_speaker`, `policy.expected_presenter` and `policy.approval_evidence` from current explicit instructions. Blank values require review; no identity, context or approval is supplied by this package.

Copy the blank [production manifest](../templates/production-manifest.template.json) into the configured private working folder. It is intentionally incomplete and cannot pass QA as a draft. Keep all populated manifests and media outside this repository.

Record:

- The exact script, narration and caption files, their SHA-256 hashes and approval/review evidence. Script approval does not approve the finished public output.
- Every input asset, including presenter footage, graphics and any music, with an ID, hash, role and ownership/licence/clearance evidence. No bundled stock music or assumption that online availability permits reuse.
- Voice, factual-claim and privacy review tied to all current input hashes. Preserve source files and save new export filenames.
- Each export's ID/hash, measured width, height, duration and aspect ratio. Supported ratio records are 9:16, 16:9, 1:1 and 4:5. A ratio alone does not establish current platform support.
- Evidence from media inspection, playback, listening, caption safe-area review and disclosure review for each export. State any sampled review honestly. Null evidence cannot be treated as a pass.

Each export evidence field is an object with `reference` and an independently recorded `reviewed_export` containing `sha256`, `width`, `height`, `aspect_ratio` and `duration_seconds`. Record those values when that specific review happens. Every review must match the current output as well as its inputs. Replacing bytes, refreshing the export hash or changing measured metadata invalidates old reviews. Do not refresh evidence bindings merely to make a check pass; review the new export first.

When review evidence is recorded, set `status` to `ready_for_review` and run:

```powershell
python "<skill-folder>/scripts/check_production.py" "<local-manifest.json>" --root "<local-content-working-folder>"
```

The checker reads only explicitly referenced local files beneath the given root, verifies hashes and checks evidence fields. It does not render, transcribe, probe media, judge licences, listen, inspect factual accuracy or prove that the operator's recorded evidence is true. It does not fetch URLs, call providers or grant publication permission. A changed file/hash invalidates its previous review bindings.

Select one reviewed export and carry its SHA-256 into the release's existing `asset.sha256`. If recording the optional `production` handoff on that release, include `manifest_sha256`, `export_id`, `export_sha256` and `qa_evidence`; the export hash must match the release asset. Obtain the normal finished-output approval for that exact export/caption/platform/time/guide. Each platform keeps its existing scheduler and no variant is automatically published.

Optional experiments need only a hypothesis, one changed element and a comparable observation window. Measure retention, shares and qualified guide requests after an authorised release; volume and automation do not promise virality.

ManyChat replacement remains exploratory and is not implemented.
