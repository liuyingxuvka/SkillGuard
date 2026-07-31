## Why

The v0.4.2 source/tag/installed identities agree, but the authoritative branch CI is red because README model evidence still names v0.4.1 and CHANGELOG lacks v0.4.2. The repository also records older FlowGuard CI pins while the current released toolchain is 0.65.1. Those defects must be repaired inside the same frozen v0.5.0 release candidate before new diagnostics can close.

## What Changes

- Correct README model-evidence wording and add the missing v0.4.2 changelog record.
- Reconcile FlowGuard adoption records, managed policy, model authority, and CI toolchain pins to 0.65.1.
- Preserve the current contract-source, compiled-contract, check-manifest, receipt, and closure owners.
- Run current branch CI-equivalent validation as part of the single v0.5.0 candidate; do not create an intermediate patch tag whose source identity would immediately be superseded.

## Capabilities

### New Capabilities

- `skillguard-release-baseline`: Defines version/readme/changelog/toolchain parity required before feature validation.

### Modified Capabilities

- None.

## Impact

Affected surfaces: README, CHANGELOG, FlowGuard adoption/model authority, CI configuration, release metadata, version files, and baseline validation receipts.
