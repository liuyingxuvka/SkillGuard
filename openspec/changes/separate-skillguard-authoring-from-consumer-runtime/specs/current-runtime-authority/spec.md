## MODIFIED Requirements

### Requirement: Current-only consumer parity
The SkillGuard contract source, compiled contract, and check manifest SHALL be current authority only for author maintenance. Consumer installation and parity SHALL compare a target-owned consumer manifest and target-owned files and SHALL reject every SkillGuard control surface.

#### Scenario: Maintainer source is audited
- **WHEN** an explicitly adopted skill-authoring repository is checked
- **THEN** the current SkillGuard trio SHALL be required and internally consistent

#### Scenario: Consumer installation is audited
- **WHEN** an independently distributed target is checked
- **THEN** the absence of the SkillGuard trio SHALL be required and SHALL NOT block target domain use

### Requirement: Direct current replacement has no conversion route
An author target SHALL be repaired by writing the sole current maintainer source and regenerating author controls. A consumer target SHALL be rebuilt from the clean current consumer projection. No normal runtime converter, alias, old-shape reader, or fallback SHALL provide success.

#### Scenario: Old author target is incomplete
- **WHEN** the maintainer source lacks current unit identity or projection boundaries
- **THEN** author maintenance SHALL block until direct replacement is complete

#### Scenario: Old consumer carries controls
- **WHEN** a prior installed target still carries installer-owned unchanged SkillGuard files
- **THEN** the staged consumer upgrade MAY withdraw only those exact owned files and SHALL preserve/report modified conflicts

### Requirement: Maintenance has no refresh or upgrade route
Current author maintenance SHALL accept complete explicit current inputs and author roots. Maintainer-repository adoption MAY write the current author manifest and prompt; ordinary project adoption MUST NOT write SkillGuard state.

#### Scenario: Maintainer repository is adopted
- **WHEN** repository role, maintenance units, author evidence root, and consumer exclusion are explicit
- **THEN** adoption MAY write the sole current author record without reading an old shape

#### Scenario: Ordinary project is supplied
- **WHEN** those author declarations are absent
- **THEN** adoption SHALL block before creating `.skillguard` or changing `AGENTS.md`

### Requirement: Native tests keep one owner and are never copied by consumers
Each maintenance unit SHALL keep its target-native check ownership and unit-local receipts. Different units MUST NOT share proof. Consumer distributions MAY contain target-owned native validation needed for ordinary work but MUST NOT contain SkillGuard execution wrappers or receipts.

#### Scenario: Two units request the same native test
- **WHEN** the checks belong to different maintenance units
- **THEN** each unit SHALL keep a distinct execution key and receipt, or the semantic-overlap audit SHALL require split, merge, or retirement

#### Scenario: Consumer contains a target-native check
- **WHEN** the check is required for target domain work
- **THEN** it SHALL live under a target-owned path and invoke no SkillGuard runtime
