# Synthetic planning example

These four documents describe a fictional offline demonstration. They contain synthetic evidence and account references, not permission to publish or proof of source/approval authenticity. Do not use the historical clock to pass stale real inputs.

From the repository root:

```text
python skills/content-operations/scripts/check_planning.py --brand docs/examples/planning/brand.json --claims docs/examples/planning/claims.json --brief docs/examples/planning/brief.json --policies docs/examples/planning/policies.json --as-of 2026-11-03T10:00:00+04:00
```

Expected: `ready_for_drafting: true`, `release_authorized: false`, `live_state_verified: false`. Changing a brand ID/revision, revoking the selected claim or expiring a source returns errors and exit code 1. The four blank templates intentionally fail until completed. This example is not copied into the uploadable skill as populated operator state.

See [planning guidance](../../../skills/content-operations/references/content-planning.md) and [channel rules](../../../skills/content-operations/references/channel-policy.md).
