# target-model-deepening-closure Specification

## ADDED Requirements

### Requirement: Target owns model-deepening meaning

SkillGuard SHALL require each maintained target to declare its own native iterative closure check and SHALL not invent or evaluate domain depth itself.

#### Scenario: Missing target-native check
- **GIVEN** a target contract has a depth profile but no target-owned deepening closure check
- **WHEN** the maintenance unit is compiled
- **THEN** the unit is blocked

### Requirement: Target receipts must prove current iterative closure

The declared target check SHALL produce a current terminal receipt bound to the exact target inputs, model candidate, native checks, and closure profile.

#### Scenario: Stale target receipt
- **GIVEN** the target model or prompt changed after a receipt was produced
- **WHEN** SkillGuard evaluates currentness
- **THEN** the receipt is stale and graduation remains blocked

### Requirement: Domain semantics remain opaque

SkillGuard SHALL consume target-native model-deepening receipts as opaque evidence and SHALL never replace a target's action, judgment, or native checker.

#### Scenario: Self-report only
- **GIVEN** a target reports that the AI understood the task but provides no current native receipt
- **WHEN** closure is evaluated
- **THEN** SkillGuard does not treat the statement as evidence

### Requirement: Consumer projections stay independent

The clean consumer distribution SHALL contain target runtime material only and no SkillGuard contracts, receipts, router state, or author-side paths.

#### Scenario: Author artifacts are excluded
- **GIVEN** a maintained target is staged for consumer installation
- **WHEN** the projection is audited
- **THEN** `.skillguard`, author paths, receipts, router state, and SkillGuard imports are absent
