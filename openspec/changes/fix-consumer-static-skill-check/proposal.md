## Why

`check-skill` currently requires every maintained target entrypoint to contain
an author-only `SkillGuard Maintenance` section. The same entrypoint is copied
into the clean consumer distribution, so this static rule contradicts the
current consumer-independence contract and blocks valid graduated skills.

## What Changes

- **BREAKING** Remove the author-only maintenance heading from the target
  consumer `SKILL.md` required-section set.
- Keep author maintenance authority in `.skillguard/**`, the author repository
  policy, and private evidence roots.
- Add a regression fixture proving a clean consumer-style target passes
  `check-skill` without mentioning SkillGuard.
- Extend the existing current-authority FlowGuard model so any consumer
  entrypoint that carries an author-maintenance prompt is explicitly blocked.

## Capabilities

### New Capabilities

- `consumer-skill-static-check`: Static target checks distinguish target-owned
  consumer instructions from author-only SkillGuard control.

### Modified Capabilities

None.

## Impact

The change affects the `check-skill` required-section policy, its focused
tests/fixtures, the current-runtime-authority FlowGuard model, SkillGuard's
compiled self-contract, installed maintainer projection, and downstream
maintained targets that were previously blocked by the false requirement.
