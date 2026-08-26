## ADDED Requirements

### Requirement: Canonical source ownership is explicit
SkillGuard SHALL accept an explicitly supplied private portfolio registry that maps each active skill id to one canonical local source root, source-relative skill path, installed path, repository identity, expected visibility, and lifecycle state.

#### Scenario: Active skill has one source owner
- **WHEN** a registry row names exactly one existing canonical source and matching skill id
- **THEN** SkillGuard accepts the source ownership mapping for sync checks

#### Scenario: Two candidate source owners remain
- **WHEN** the same active skill id maps to multiple canonical sources or no source exists
- **THEN** SkillGuard blocks source synchronization and reports `ambiguous-source-owner` or `missing-source-owner`

### Requirement: Installed synchronization cannot downgrade capability protection
SkillGuard SHALL compare source and installed entrypoint, work-contract, check-manifest, functional-closure, and evidence-strength fingerprints before installation or synchronization.

#### Scenario: Source is shallower than installed
- **WHEN** the source lacks a current deep contract or functional record that exists in the installed copy
- **THEN** SkillGuard reports `source-to-installed-downgrade` and blocks replacement

#### Scenario: Normalized text is semantically identical
- **WHEN** source and installed text differ only by approved line-ending normalization
- **THEN** SkillGuard reports byte drift separately and does not classify it as semantic downgrade

### Requirement: Retired skills are excluded without deletion
The portfolio registry SHALL support a retired lifecycle state with an explicit no-maintenance/no-publish policy while preserving repository and local history.

#### Scenario: Retired private repository
- **WHEN** FlowBot, Heartbeat, or Legacy Inspiration is marked retired and private
- **THEN** capability audit excludes it from active repair counts and reports the exclusion reason

### Requirement: Public records never expose private source roots
SkillGuard SHALL keep machine-specific canonical source and installed paths in the private registry and SHALL sanitize them from public reports and committed target records.

#### Scenario: Report contains a user home path
- **WHEN** a generated public report would include an absolute source or installed path
- **THEN** SkillGuard replaces it with a portable label or reports a public-boundary failure
