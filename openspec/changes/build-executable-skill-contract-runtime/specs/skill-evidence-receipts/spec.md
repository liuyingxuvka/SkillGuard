## ADDED Requirements

### Requirement: Evidence classes remain distinct
SkillGuard SHALL classify evidence as hard, witnessed, or judged and SHALL preserve the class and claim boundary through parent closure.

#### Scenario: AI review is submitted
- **WHEN** a versioned rubric review is recorded
- **THEN** SkillGuard stores it as judged evidence with evaluator, input hash, conclusion, and limitations and does not promote it to hard proof

### Requirement: Receipts are immutable and freshness is derived
SkillGuard SHALL create immutable receipts and derive currentness from declared input, implementation, contract, artifact, environment-policy, and consumed-child fingerprints rather than accepting caller-authored current flags.

#### Scenario: Source changes after a passing test
- **WHEN** a covered source fingerprint changes
- **THEN** the dependent test and closure receipts become stale until re-executed or validly narrowed

### Requirement: Artifacts are first-class evidence
SkillGuard SHALL validate each declared artifact's identity, location, type, structural constraints, freshness, and producing step before allowing it to satisfy an obligation.

#### Scenario: Screenshot points to the wrong surface
- **WHEN** an image exists but its target-state or surface witness does not match the contract
- **THEN** SkillGuard rejects it for that artifact obligation

### Requirement: Parent closure consumes exact child receipts
SkillGuard SHALL record the exact child receipt ids consumed by a parent and SHALL invalidate the parent when a required newer child supersedes a consumed receipt.

#### Scenario: Child is rerun
- **WHEN** a required child produces a new receipt after parent closure
- **THEN** the parent is stale until it consumes and validates the new child receipt
