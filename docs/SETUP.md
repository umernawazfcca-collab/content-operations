# Setup

1. Review the skill and local scripts before running. Use a disposable workspace first.
2. Keep populated operating records outside this source tree. Choose a canonical records location explicitly; never infer a personal folder or create a replacement tracker silently.
3. Configure the authorized account identity, scheduler, timezone, service owner, approval scope and delivery route in private operating records. No account, flow, resource identifier or recurring authorization is preconfigured.
4. Start read-only with synthetic templates. Unknown/missing approval, publish, delivery or coverage evidence must remain blocked.
5. Run `python scripts/validate_repository.py` from the repository root. This tests local behavior only.

## Optional local install
`python scripts/install.py --host both --check` previews the Codex/Claude Code destinations. A subsequent command without `--check` writes to those local skill directories; do that only after approving those exact destinations. The installer must refuse different existing copies. A repository download or package creation does not install a skill.

For isolated evaluation, use `python scripts/install.py --host both --home /path/to/disposable-home --check`, inspect destinations, then repeat without `--check` only inside that disposable location. Never replace a production skill as part of candidate review.

## Portable packages
Build with `scripts/package.py --target claude|codex|openai|gemini --out PATH` (choose one target). Claude/Codex packages contain a top-level `content-operations` folder; OpenAI packaging contains `skills/content-operations` plus plugin metadata; Gemini uses the conservative Markdown/Python/text layout. These are candidate layouts, not universal importer guarantees. Host interfaces and policy may differ. A host lacking local scripts, current canonical records or required connector access is review-only.

Run the included smoke check with synthetic inputs on the intended host before claiming runtime compatibility. Independently verify every live integration and obtain action-specific authorization. Nothing here activates accounts, flows, schedules or replies.
