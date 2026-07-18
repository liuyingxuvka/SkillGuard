## ADDED Requirements

### Requirement: Template supervision is author-side
Validated template selection, applicability, composition, selection receipts, instance receipts, and harvest review SHALL remain author-maintenance evidence and SHALL NOT become a consumer runtime prerequisite.

#### Scenario: Template-backed skill graduates
- **WHEN** author-side template selection and native validation pass
- **THEN** the consumer SHALL receive only the generated target-owned artifact and target-owned instructions

#### Scenario: Consumer lacks SkillGuard
- **WHEN** the graduated skill is used on another machine
- **THEN** missing template supervision receipts or SkillGuard runtime SHALL NOT block domain work

### Requirement: Template receipts are unit-local
Every template selection or instance receipt SHALL bind one maintenance unit, member skill, evidence subject, and target-native owner and SHALL reject foreign-unit consumption.

#### Scenario: Another unit offers a matching template receipt
- **WHEN** request and template hashes match but maintenance-unit identity differs
- **THEN** supervision SHALL reject the receipt and SHALL NOT use it for selection or closure
