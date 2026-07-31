## Purpose

Keep a maintained Guard's provider dependency, validation environment, generated authority, installed projection, and published patch identity mutually consistent after a provider release.

## ADDED Requirements

### Requirement: Provider identity is exact across closure surfaces
The maintenance repository SHALL use one immutable provider release identity across its project adoption record, branch-CI dependency pins, workflow-policy checks, generated maintenance contract, and current model evidence.

#### Scenario: Provider release advances
- **WHEN** the installed provider is newer than the maintenance repository's recorded or CI-pinned provider
- **THEN** closure remains blocked until every governed provider reference is updated and affected validation passes

#### Scenario: Provider references disagree
- **WHEN** project adoption, CI installation, policy tests, or generated authority name different provider versions
- **THEN** the system reports visible version drift and SHALL NOT claim current maintenance closure

### Requirement: Post-release synchronization uses a new patch identity
If provider synchronization changes the installed maintained-skill projection after a release is already published, the repository SHALL preserve the existing tag and publish the synchronized bytes under a new patch version.

#### Scenario: Existing tag is immutable
- **WHEN** the provider synchronization is discovered after `v0.5.0` publication
- **THEN** `v0.5.0` remains unchanged and the synchronized source, installation, tag, and GitHub Release use `v0.5.1`

### Requirement: Validation ownership remains separated
Branch CI SHALL own regression execution, tag CI SHALL remain receipt-only, and a generated or installation receipt SHALL NOT substitute for the other evidence domains.

#### Scenario: Patch tag is pushed
- **WHEN** the synchronized patch tag is pushed
- **THEN** tag CI verifies exact version/tag/commit identity without rerunning the branch regression owners

#### Scenario: Local installation is refreshed
- **WHEN** the synchronized patch is installed locally
- **THEN** installation currentness is verified separately from model, regression, Git, and publication evidence
