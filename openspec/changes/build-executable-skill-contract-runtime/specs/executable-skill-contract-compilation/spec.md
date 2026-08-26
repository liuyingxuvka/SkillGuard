## ADDED Requirements

### Requirement: FlowGuard model is the behavior authority
SkillGuard SHALL compile function, state, transition, terminal, invariant, owner, and loop semantics from a supported real FlowGuard model export and SHALL reject missing or unsupported FlowGuard toolchains.

#### Scenario: Supported model compiles
- **WHEN** a valid FlowGuard export and matching target binding source are supplied
- **THEN** SkillGuard deterministically generates a compiled contract and exact check manifest

#### Scenario: Markdown is the only behavior source
- **WHEN** a target has prompt prose but no supported FlowGuard behavior model
- **THEN** SkillGuard refuses release compilation and emits a visible
  direct-current rewrite blocker; no provisional artifact, alternate reader,
  or unconfirmed artifact is accepted as current authority

### Requirement: Compilation has one direct-current authority
SkillGuard SHALL compile and validate only the current FlowGuard model,
contract source, check manifest, and declared target bindings owned by this
change. Former contract, closure, receipt, or installation identities SHALL be
rejection-only direct-current rewrite inputs. The runtime SHALL NOT introduce a
compatibility reader, fallback path, migration command, converter, alias, dual
manifest, or alternate successful compilation authority.

#### Scenario: Former generated authority is supplied
- **WHEN** a former compiled contract, closure record, manifest, or receipt is
  supplied after the current source/schema identity has changed
- **THEN** compilation blocks with the exact identity mismatch and requires a
  manual direct-current rewrite followed by fresh validation

### Requirement: Published generation is minimal and deterministic
SkillGuard SHALL publish only the compiled contract and check manifest as generated contract artifacts, SHALL produce byte-stable output for identical inputs, and SHALL detect stale or missing outputs in read-only check mode.

#### Scenario: Input changes
- **WHEN** the model, binding, or covered entrypoint boundary changes
- **THEN** check mode reports the affected generated artifact stale without modifying it

#### Scenario: Same text checkout uses platform line endings
- **WHEN** identical committed text source is checked out with LF or CRLF line endings while binary assets are unchanged
- **THEN** SkillGuard generates the same contract source fingerprint, while a real binary-byte change still makes the contract stale

#### Scenario: Clean Windows checkout preserves generated contract bytes
- **WHEN** Git checks out the committed compiled contract and check manifest on Windows with automatic text conversion enabled
- **THEN** repository attributes preserve canonical LF bytes so read-only compiler parity remains current

### Requirement: Compilation rejects incomplete topology and coverage
SkillGuard SHALL reject dangling or mistyped handoffs, duplicate or missing owners, uncovered success terminals, unbounded cycles, orphan checks, orphan artifacts, and obligation mappings that indiscriminately bind unrelated checks.

#### Scenario: One unrelated test is bound to every obligation
- **WHEN** a binding maps a native check to obligations outside its declared scope
- **THEN** compilation fails with stable affected obligation and check identifiers
