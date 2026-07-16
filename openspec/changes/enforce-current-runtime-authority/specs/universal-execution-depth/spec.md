## MODIFIED Requirements

### Requirement: Canonical source and installed parity
The Git repository SHALL be the canonical SkillGuard source. Installation SHALL consume the frozen content-impact plan, stage only declared current installation components, validate them, activate atomically, retain a backup, and roll back on failure. A current target SHALL contain no former runtime-authority, retirement, or conversion residual.

#### Scenario: Source-only rejection fixture changes
- **WHEN** only former-shape rejection fixtures change
- **THEN** installation and functional smoke SHALL remain not required

#### Scenario: Partial installed sync
- **WHEN** an affected current installable component is missing or only partly staged
- **THEN** component parity SHALL block activation and identify the exact incomplete component

#### Scenario: Former runtime artifact returns
- **WHEN** a former work contract, legacy manifest, flat old run record, retirement receipt, or conversion tool appears in a current source, stage, or active tree
- **THEN** parity and closure SHALL fail with `former_runtime_residual` and SHALL NOT accept compatibility fallback

## ADDED Requirements

### Requirement: Execution depth has no former-path input
A current execution-depth decision MUST derive only from the current contract trio, exact impact plan, target-native evidence, immutable current receipts, and closure replay. Former retirement, conversion, authority, and run artifacts MUST NOT be required or consumed.

#### Scenario: Current deep run
- **WHEN** current target-native evidence satisfies the declared profile and no residual exists
- **THEN** SkillGuard SHALL issue and replay the current depth decision without reading a former retirement, conversion, authority, or run artifact

#### Scenario: Old pass record is introduced
- **WHEN** an old pass record appears beside shallow or missing current evidence
- **THEN** SkillGuard SHALL block on the residual and SHALL NOT raise the current execution-depth status
