## ADDED Requirements

### Requirement: FlowGuard model is the behavior authority
SkillGuard SHALL compile function, state, transition, terminal, invariant, owner, and loop semantics from a supported real FlowGuard model export and SHALL reject missing or unsupported FlowGuard toolchains.

#### Scenario: Supported model compiles
- **WHEN** a valid FlowGuard export and matching target binding source are supplied
- **THEN** SkillGuard deterministically generates a compiled contract and exact check manifest

#### Scenario: Markdown is the only behavior source
- **WHEN** a target has prompt prose but no supported FlowGuard behavior model
- **THEN** SkillGuard refuses release compilation and may emit only an explicitly unconfirmed migration candidate

### Requirement: Published generation is minimal and deterministic
SkillGuard SHALL publish only the compiled contract and check manifest as generated contract artifacts, SHALL produce byte-stable output for identical inputs, and SHALL detect stale or missing outputs in read-only check mode.

#### Scenario: Input changes
- **WHEN** the model, binding, or covered entrypoint boundary changes
- **THEN** check mode reports the affected generated artifact stale without modifying it

### Requirement: Compilation rejects incomplete topology and coverage
SkillGuard SHALL reject dangling or mistyped handoffs, duplicate or missing owners, uncovered success terminals, unbounded cycles, orphan checks, orphan artifacts, and obligation mappings that indiscriminately bind unrelated checks.

#### Scenario: One unrelated test is bound to every obligation
- **WHEN** a binding maps a native check to obligations outside its declared scope
- **THEN** compilation fails with stable affected obligation and check identifiers
