## MODIFIED Requirements

### Requirement: Managed prompt guidance is generated
SkillGuard SHALL generate template-selection and harvest guidance only into author-maintenance records. A graduated consumer prompt SHALL contain only the target's own activation, workflow, validation, output, and claim boundaries and SHALL contain no SkillGuard marker, contract, receipt, router, or runtime instruction.

#### Scenario: Author template record is generated
- **WHEN** a managed target uses a validated template pack
- **THEN** template identities, selection, harvest, and author receipts MAY be recorded under author control

#### Scenario: Consumer prompt is generated
- **WHEN** the target is graduated for ordinary use
- **THEN** its prompt SHALL be independent and SHALL NOT require SkillGuard

### Requirement: Installation and router refresh are transactional
Maintainer deployment and consumer distribution SHALL use separate transactions. Author template records and router state MAY enter maintainer deployment only. Consumer activation SHALL contain only target-owned files and a target-owned release manifest.

#### Scenario: Consumer projection matches current target
- **WHEN** a graduated target installation activates
- **THEN** its receipt SHALL bind the target-owned consumer projection and contain no SkillGuard control paths

#### Scenario: Consumer validation fails
- **WHEN** a SkillGuard marker, command, import, receipt, or `.skillguard` path appears
- **THEN** activation SHALL roll back and the author registry SHALL remain unchanged
