## Why

SkillGuard currently hard-codes one target's update branch names (`no-update`, `waiting-for-user`, `ui-running`, and `prepared-update`) into its universal contract compiler and native-terminal runtime. This prevents a current target from declaring a different, stricter route—such as an explicit manual update with no prepared or waiting state—and makes retired target behavior an accidental part of SkillGuard authority.

## What Changes

- **BREAKING**: Remove all target-specific branch identifiers and prepared-update semantics from SkillGuard's universal compiler and native-terminal runtime.
- Validate conditional route branches only from the exact target-owned `route_branch_requirements` inventory.
- Derive no-op versus completing branches from verifier-owned applicability rules instead of branch-name allowlists.
- Preserve terminal receipt closure strength while using neutral terminal classifications and the exact evidence domain already established by the current depth receipt.
- Add regression fixtures proving arbitrary branch identifiers compile and close, while omitted, overlapping, or unverifiable conditional obligations still fail closed.
- Repair the installer forward-recovery deadlock exposed during self-hosting: a fully verified replacement may snapshot and replace a non-empty drifted active tree when the historical transaction's own backup is no longer restorable, without treating that drift as current evidence.
- Directly replace the current implementation; do not add aliases, compatibility readers, migration commands, or fallback branch names.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `universal-execution-depth`: Conditional route branches and native terminal closure become target-owned and target-neutral, without weakening enforced closure.

## Impact

- Affects the SkillGuard v2 contract schema validator, native-terminal receipt builder/resolver, conditional closure tests, documentation, and installed SkillGuard projection.
- Existing target contracts remain valid only when their branch semantics are fully declared by their own current contract; no SkillGuard-internal branch-name authority remains.
- Enables Khaos Brain's current manual-only update skill to use `no-update` and `explicit-manual-update` without restoring retired prepared/waiting/UI branches.
