## ADDED Requirements

### Requirement: Source fragment references compile deterministically
SkillGuard SHALL allow contract source to reference reviewed target-neutral supervision fragments and SHALL deterministically expand them into the existing compiled contract and exact check manifest.

#### Scenario: Same source and fragment identities reproduce outputs
- **WHEN** contract source, compiler, referenced fragment content, and target bindings are unchanged
- **THEN** compilation produces byte-identical compiled-contract and check-manifest projections

#### Scenario: Changed fragment stales only consumers
- **WHEN** one fragment identity changes
- **THEN** only contracts and projections that consume that fragment become stale

### Requirement: No fourth contract authority
Fragment catalogs and expansion metadata MUST remain compiler inputs and MUST NOT become a parallel runtime contract, manifest, fallback, or alternate closure source.

#### Scenario: Runtime consumes only the current trio
- **WHEN** a supervised run begins
- **THEN** runtime authority resolves only from current contract source, compiled contract, and exact check manifest

#### Scenario: Standalone fragment authority is rejected
- **WHEN** a caller attempts to execute or close directly from a fragment file
- **THEN** SkillGuard rejects the request as a parallel authority

### Requirement: Compilation preserves target declarations exactly
Compilation SHALL preserve the target's native owner, routes, checks, dependencies, evidence domains, artifacts, conditional branches, and claim boundary, and SHALL reject any fragment expansion that invents, removes, duplicates, or reinterprets them.

#### Scenario: Target inventory is preserved
- **WHEN** a profile expands successfully
- **THEN** the compiled target-declared inventory equals the source inventory by exact id and owner

#### Scenario: Fragment-added domain check is rejected
- **WHEN** a generic fragment attempts to add a target-domain check not declared by the target
- **THEN** compilation fails before generating current outputs

### Requirement: Schema and runtime acceptance are identical
The published JSON schema, compiler validation, and runtime validation SHALL agree on required fields, allowed fields, defaults, and unknown-field rejection for template profiles and receipts.

#### Scenario: Schema-valid payload is runtime-valid
- **WHEN** a payload passes the current published schema and all referenced identities resolve
- **THEN** compiler/runtime structural validation accepts the same payload

#### Scenario: Runtime-required field is schema-required
- **WHEN** runtime closure depends on a template field
- **THEN** the current schema requires or deterministically derives that field from one declared authority

### Requirement: Content impact maps template components
The compiler SHALL map manifests, template bodies, fragments, builders, validators, prompts, and launch plans to exact functional components and SHALL leave reports, receipts, task checkmarks, progress, and installation bookkeeping outside producer freshness.

#### Scenario: Template body change invalidates its consumers
- **WHEN** a template body digest changes
- **THEN** the selector, instance builder, validators, and installation projections that explicitly consume it become stale

#### Scenario: Task checkmark does not rerun source owner
- **WHEN** only an implementation-ledger checkbox or runtime report changes
- **THEN** the source validation owner remains current unless the semantic task content also changed
