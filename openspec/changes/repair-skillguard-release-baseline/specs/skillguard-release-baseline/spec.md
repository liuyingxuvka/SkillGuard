## ADDED Requirements

### Requirement: Public release evidence matches the exact version

SkillGuard SHALL require README model evidence, CHANGELOG, version files, source/tag commit, and release metadata to identify the same release.

#### Scenario: README names an older model release

- **WHEN** the current source version is newer than the README evidence label
- **THEN** the release baseline SHALL fail before feature validation

#### Scenario: Changelog entry is absent

- **WHEN** the current release version has no changelog record
- **THEN** release readiness SHALL remain blocked

### Requirement: FlowGuard toolchain identity is current

SkillGuard SHALL use one frozen FlowGuard version across project adoption records, managed policy, local validation, and CI.

#### Scenario: CI pins a retired FlowGuard version

- **WHEN** repository adoption requires a newer current toolchain
- **THEN** the baseline SHALL fail until project records and CI use the same frozen version

### Requirement: Baseline repair is behavior-neutral

The patch baseline SHALL change release evidence and toolchain currentness without adding or removing target-facing SkillGuard behavior.

#### Scenario: Patch baseline is validated

- **WHEN** documentation, adoption, and toolchain identities are repaired
- **THEN** the patch release SHALL preserve the v0.4.2 contract behavior and record separate validation evidence
