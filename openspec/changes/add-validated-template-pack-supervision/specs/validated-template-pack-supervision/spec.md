## ADDED Requirements

### Requirement: Current template manifest identity
SkillGuard SHALL accept only a target-published current template manifest with a stable template id, revision, canonical digest, native family and route identity, applicability rules, field ownership, builder, validators, fixtures, and claim boundary.

#### Scenario: Current manifest is accepted
- **WHEN** a target supplies a schema-valid manifest whose digest matches its canonical content and native bindings
- **THEN** SkillGuard records that exact manifest identity as an input to selection

#### Scenario: Stale or incomplete manifest is blocked
- **WHEN** the revision, digest, native route, builder, validator, or required claim boundary is missing or mismatched
- **THEN** SkillGuard blocks selection without using an older or inferred manifest

### Requirement: Target-native semantic ownership
SkillGuard MUST require the target-native route decision and target-owned applicability result before supervising a domain template, and MUST NOT infer template meaning from a skill name, family label, route id, or check id.

#### Scenario: Native route precedes template selection
- **WHEN** a non-trivial target task requests template-backed work
- **THEN** the target-native router selects the route before the target catalog is evaluated

#### Scenario: SkillGuard family inference is rejected
- **WHEN** a candidate is proposed only because its name resembles the target skill or check
- **THEN** SkillGuard rejects the proposal as missing target-owned applicability evidence

### Requirement: Deterministic zero one and many candidate decisions
The supervisor SHALL reconcile the complete eligible candidate set and produce exactly one of `base_no_match`, `single_selected`, `composed`, `strictly_dominated_selection`, or `ambiguous_template_selection`.

#### Scenario: Zero domain candidates uses an approved base
- **WHEN** no domain template satisfies the target predicates and the target declares one validated base template
- **THEN** the decision selects that base, records exact no-match evidence, and requires harvest review

#### Scenario: Zero candidates without an approved base blocks
- **WHEN** no domain candidate matches and the target forbids or omits a base template
- **THEN** the decision blocks instead of beginning from a blank contract

#### Scenario: One candidate is previewed
- **WHEN** exactly one candidate satisfies every hard predicate and forbidden condition
- **THEN** the decision selects it for read-only preview before instantiation

#### Scenario: Unresolved multiple candidates block
- **WHEN** several eligible candidates neither compose safely nor have a target-authored strict dominance relation
- **THEN** the decision is `ambiguous_template_selection` and no candidate is instantiated

### Requirement: Composition preserves one field owner
Template composition SHALL require declared compatibility, satisfied fragment dependencies, canonical composition order, and exactly one owner for every generated field or artifact surface.

#### Scenario: Disjoint compatible fragments compose
- **WHEN** all selected fragments are pairwise compatible, dependencies are present, and owned fields are disjoint
- **THEN** the supervisor emits one canonical composition and field-owner map

#### Scenario: Field collision blocks composition
- **WHEN** two selected fragments own the same field or artifact surface without one declared primary owner
- **THEN** composition fails with the conflicting templates and fields visible

### Requirement: Immutable selection receipt
Every non-trivial decision SHALL persist an immutable receipt containing the request fingerprint, native route receipt, catalog identity, complete candidates, rejection reasons, selected identities, composition order, applicability result, field-owner map, and decision disposition.

#### Scenario: Candidate accounting is complete
- **WHEN** a selection receipt is issued
- **THEN** every candidate considered by the frozen catalog appears exactly once as selected or rejected with a reason

#### Scenario: Changed request makes receipt stale
- **WHEN** the request, route, catalog, predicate input, template revision, or template digest changes
- **THEN** the prior selection receipt is stale and cannot authorize instantiation

### Requirement: Instance receipt binds native validation
Template instantiation SHALL produce a separate receipt that binds the selection receipt, exact parameters, builder identity, generated artifact fingerprints, unresolved-placeholder scan, and current target-native validator receipts.

#### Scenario: Validated instance may enter closure
- **WHEN** every generated artifact matches the frozen selection and all target-declared validators pass
- **THEN** the instance receipt may be consumed by the target's enforced closure

#### Scenario: Instantiation alone cannot close work
- **WHEN** files are generated but any native validator or declared target check is absent, stale, skipped, or failed
- **THEN** the task remains open regardless of successful rendering
