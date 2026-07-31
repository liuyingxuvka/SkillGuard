## Why

SkillGuard's post-release project record was upgraded to FlowGuard 0.66.0 while its branch CI still installed FlowGuard 0.65.1. The mismatch made every focused CI matrix job fail and would leave a locally refreshed SkillGuard installation with bytes that were not represented by the immutable v0.5.0 release.

## What Changes

- Align all SkillGuard branch-CI FlowGuard pins with the current immutable `v0.66.0` provider release.
- Keep the workflow-policy test, project adoption record, generated contract, model authority, and installed SkillGuard projection on the same provider identity.
- Publish the synchronized state as patch release `v0.5.1`; do not move or rewrite the existing `v0.5.0` tag.
- Preserve tag CI as receipt-only and preserve branch CI as the regression owner.

## Capabilities

### New Capabilities

- `provider-version-closure`: Require one exact provider version across project adoption, CI toolchain pins, generated maintenance authority, model evidence, local installation, Git tag, and publication closure.

### Modified Capabilities

None.

## Impact

This affects the SkillGuard GitHub Actions workflow, its workflow-policy regression, generated author-side contract files, FlowGuard model-authority records, local SkillGuard installation, global maintainer router currentness, and the patch-release identity. It does not change SkillGuard's consumer-facing domain behavior or the already published `v0.5.0` tag.
