## MODIFIED Requirements

### Requirement: Every real task claims a contract run
Every supervised author-maintenance task SHALL claim one run under an explicit author evidence root and exactly one maintenance unit before creating a directory, lock, event, or receipt. Ordinary consumer use SHALL claim no SkillGuard run.

#### Scenario: Author claim is complete
- **WHEN** repository role, maintenance unit, member, request, author run root, and author owner-evidence root are explicit
- **THEN** SkillGuard SHALL create or resolve the unit-namespaced run without writing into the target consumer root

#### Scenario: Author root is omitted
- **WHEN** a maintenance request lacks an explicit author run or evidence root
- **THEN** the request SHALL block with zero filesystem writes

#### Scenario: Consumer performs domain work
- **WHEN** an independently distributed skill is used ordinarily
- **THEN** no SkillGuard run, lock, event, or receipt SHALL be claimed

### Requirement: Runs resume from durable events
SkillGuard SHALL reconstruct an author run only from durable events and receipts beneath the same maintenance-unit evidence namespace. Events or receipts from another unit MUST NOT be read as resumable state.

#### Scenario: Context is lost mid-run
- **WHEN** the same unit, request, and explicit author evidence root are reopened
- **THEN** the run MAY resume from its own current durable events

#### Scenario: Foreign unit has an identical request
- **WHEN** another unit uses the same request fingerprint
- **THEN** it SHALL receive a distinct run identity and SHALL NOT resume the first unit
