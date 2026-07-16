## ADDED Requirements

### Requirement: Skill planning reports template candidates
`plan-skill` SHALL inventory target-native template capabilities and return candidate profiles, applicability evidence, rejected candidates, ambiguity, expected generated artifacts, and affected current-authority components.

#### Scenario: Planning has one eligible profile
- **WHEN** exactly one target-owned profile satisfies the request
- **THEN** planning reports that profile and a deterministic preview action without writing files

#### Scenario: Planning exposes ambiguity
- **WHEN** several incompatible profiles remain eligible
- **THEN** planning reports the conflicting candidates and blocks generation

### Requirement: Generation previews before direct replacement
`generate-skill` SHALL render a read-only materialized preview and validate template identities, parameters, placeholders, native bindings, and projected authority before writing a direct-current replacement.

#### Scenario: Valid preview is applied
- **WHEN** the preview is current, unambiguous, placeholder-free, and preserves native declarations
- **THEN** generation writes the sole current source/compiled/manifest authority atomically

#### Scenario: Stale preview is rejected
- **WHEN** any source, template, parameter, compiler, or target-native binding changes after preview
- **THEN** generation requires a new preview and does not partially update the target

### Requirement: Managed prompt guidance is generated
The global router prompt and target skill template-routing sections SHALL be generated from canonical fragments while preserving target-specific domain instructions.

#### Scenario: Global prompt remains target-neutral
- **WHEN** the managed global prompt is rendered
- **THEN** it describes the universal template lifecycle and hands domain selection to the selected target skill

#### Scenario: Target skill declares native template behavior
- **WHEN** a target skill is generated or maintained
- **THEN** its projected guidance names catalog routing, inputs, forbidden conditions, composition, preview, native validation, no-match/harvest, and claim boundary from target-authored data

### Requirement: Harvest review closes every new or deepened model
Every target task that creates or materially deepens a model SHALL record whether the result reused, updated, duplicated, created, or intentionally did not create a reusable template.

#### Scenario: Reusable new pattern is proposed
- **WHEN** a successful task exposes a stable repeated structure not covered by current templates
- **THEN** the target emits a bounded template candidate with provenance and required native fixtures

#### Scenario: One-off result is not harvested
- **WHEN** the result depends on task-specific facts that are unsafe to generalize
- **THEN** the target records a not-harvestable reason without weakening task closure

### Requirement: Installation and router refresh are transactional
A maintained target SHALL be staged and content-verified before activation, natively revalidated after activation, and included in global router refresh only when its route projection changed.

#### Scenario: Installed projection matches current source
- **WHEN** a target installation activates
- **THEN** its receipt binds the compiler-owned installation projection and active installed runtime identity

#### Scenario: Post-activation check fails
- **WHEN** required installed currentness or native validation fails
- **THEN** the target transaction restores the prior active copy and reports the new installation as failed
