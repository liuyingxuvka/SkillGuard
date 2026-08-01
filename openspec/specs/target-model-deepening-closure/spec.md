# target-model-deepening-closure Specification

## Purpose
TBD - created by archiving change enforce-target-model-deepening-closure. Update Purpose after archive.
## Requirements
### Requirement: Target owns model-deepening meaning

SkillGuard SHALL let an affected maintained target designate exactly one of its own declared checks as `model_deepening_check_id` and SHALL not invent or evaluate domain depth itself.

#### Scenario: Missing target-native check
- **GIVEN** an affected target contract designates no target-owned deepening closure check, or designates an id outside its declared native inventory
- **WHEN** the maintenance unit is compiled
- **THEN** the unit is blocked

### Requirement: Target receipts must prove current iterative closure

The declared target check SHALL produce a current terminal producer receipt bound to the exact request, target inputs, declared check, execution owner, and closure profile. SkillGuard SHALL project that evidence in a typed `model_deepening_result` rather than infer it from a caller assertion.

#### Scenario: Stale target receipt
- **GIVEN** the target model or prompt changed after a receipt was produced
- **WHEN** SkillGuard evaluates currentness
- **THEN** the receipt is stale and graduation remains blocked

#### Scenario: Wrong execution owner
- **GIVEN** a passing receipt names the deepening check but was produced by a different execution owner
- **WHEN** SkillGuard reconciles current model-deepening evidence
- **THEN** closure is blocked and the foreign receipt is not reused

### Requirement: Domain semantics remain opaque

SkillGuard SHALL consume target-native model-deepening receipts as opaque evidence and SHALL never replace a target's action, judgment, or native checker.

#### Scenario: Self-report only
- **GIVEN** a target reports that the AI understood the task but provides no current native receipt
- **WHEN** closure is evaluated
- **THEN** SkillGuard does not treat the statement as evidence

#### Scenario: Generic checks pass but deepening is not current
- **GIVEN** unrelated declared checks pass but the designated deepening check is missing, failed, skipped, or stale
- **WHEN** execution-depth closure is derived
- **THEN** the typed model-deepening result is blocked and the parent receipt cannot allow closure

### Requirement: Consumer projections stay independent

The clean consumer distribution SHALL contain target runtime material only and no SkillGuard contracts, receipts, router state, or author-side paths.

#### Scenario: Author artifacts are excluded
- **GIVEN** a maintained target is staged for consumer installation
- **WHEN** the projection is audited
- **THEN** `.skillguard`, author paths, receipts, router state, and SkillGuard imports are absent
