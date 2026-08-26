## ADDED Requirements

### Requirement: One-target capability audit is deterministic and read-only
`check-capability` SHALL load the target skill, work contract, check manifest, functional-closure record, and referenced local evidence without executing or mutating the target workflow.

#### Scenario: Complete target audit
- **WHEN** the command receives a valid target and claim scope
- **THEN** it emits parseable JSON with per-outcome, per-path, per-stage, failure, quality, and evidence decisions

#### Scenario: Target record is missing
- **WHEN** a functional target has no functional-closure record
- **THEN** the command reports `missing-functional-contract` rather than inferring a pass from SKILL.md or deep-pass

### Requirement: Audit output drives repairs
The audit SHALL report status, evidence, failures, blockers, skipped checks, residual risk, claim boundary, stable gap codes, and concrete repair actions tied to affected ids.

#### Scenario: Path has several independent gaps
- **WHEN** execution evidence, recovery evidence, and human quality evidence are each missing
- **THEN** the report preserves all three gaps and emits separate repair actions

### Requirement: Portfolio audit preserves child truth
`audit-capabilities` SHALL discover functional skill entrypoints, evaluate each child independently, and aggregate counts without allowing passing children to hide missing, failed, blocked, skipped, or stale children.

#### Scenario: Mixed portfolio
- **WHEN** one target is release-closed, one is fixture-only, and one has no functional record
- **THEN** the portfolio report returns three distinct rows and an overall non-pass decision for a release claim

### Requirement: Structural and functional status remain separate
SkillGuard SHALL expose structural depth and functional closure as separate fields in single-target and installed-skill reports.

#### Scenario: Deep but functionally open skill
- **WHEN** `check-depth` passes and `check-capability` fails
- **THEN** reports retain `deep-pass` for structural depth and a failing functional status without claiming the skill is fully covered
