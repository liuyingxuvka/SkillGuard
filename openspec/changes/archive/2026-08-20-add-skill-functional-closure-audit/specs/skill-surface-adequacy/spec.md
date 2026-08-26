## ADDED Requirements

### Requirement: Target-owned surface inventory is explicit
SkillGuard SHALL accept a target-owned surface inventory only when every observed surface row has an explicit kind, name, disposition, intent, owner, route or explicit retirement/non-applicability reason, required checks, adequacy checks, evidence subjects, and a current inventory fingerprint.

#### Scenario: Complete target inventory
- **WHEN** a target supplies a non-empty inventory whose observed denominator matches its rows and every row has the required owner, route, check, and evidence bindings
- **THEN** SkillGuard accepts the inventory as structurally ready for target-native adequacy evidence

#### Scenario: Empty or under-mapped surface
- **WHEN** an inventory omits a route, intent, owner, required check, adequacy check, evidence subject, or observed row
- **THEN** SkillGuard emits a stable surface gap and does not synthesize a fallback route or check


### Requirement: Adequacy and model deepening are graduation gates
SkillGuard SHALL require a target's depth profile to bind a target-owned surface inventory, at least one native adequacy check, and the same target-native model-deepening check before portfolio graduation can mutate the registry.

#### Scenario: Graduation without adequacy evidence
- **WHEN** a target has a structurally current contract but no declared surface inventory, no adequacy check, or no current model-deepening binding
- **THEN** portfolio graduation blocks with a visible surface-graduation finding and performs no registry mutation

#### Scenario: Surface evidence is stale or malformed
- **WHEN** the declared inventory is missing, unreadable, fingerprint-mismatched, or contains an unmapped row
- **THEN** graduation remains blocked even if all unrelated structural and representative-job evidence passes

### Requirement: SkillGuard self-audits its complete public command surface
SkillGuard SHALL compare its target-owned inventory with the complete current public command dispatch table and route registry, and SHALL block false green when a public command has no route disposition or no required checks. Each current command row SHALL bind the exact public name, command kind, dispatch function, governed/delegated disposition, route id, and required-check list declared by the target-native command table.

#### Scenario: Public command is not in the route registry
- **WHEN** a current public command has no current route entry and is not explicitly retired or not applicable
- **THEN** the self surface check reports the command-specific route gap

#### Scenario: Public command declares no required checks
- **WHEN** a current public command has an empty required-check list
- **THEN** the self surface check reports the command-specific adequacy gap instead of treating dispatch reachability as coverage

#### Scenario: Command row metadata or checks are under-declared
- **WHEN** a target re-seals its inventory after changing a command row's name, kind, dispatch function, disposition, or required-check list
- **THEN** the self surface check reports the exact command binding mismatch and does not accept the re-sealed inventory as current

### Requirement: Consumer release identity is canonical and author-independent
SkillGuard SHALL verify consumer-release manifests using compact canonical JSON plus one LF newline, lowercase `sha256:` wire identities, and release/manifest hash derivation over the same fields as the FlowGuard distribution synchronizer; consumer files SHALL reject author identity fields including underscore forms. The manifest file inventory SHALL be a sorted, unique, traversal-free list of rows containing only a relative POSIX path and a lowercase wire content hash; re-sealing malformed rows SHALL not make the release current.

#### Scenario: Cross-implementation release manifest matches
- **WHEN** SkillGuard builds a consumer distribution from a fixed file fixture
- **THEN** its `release_id`, `manifest_hash`, file hashes, and manifest bytes match the FlowGuard-compatible canonical fixture exactly

#### Scenario: Non-canonical or author-leaking consumer tree
- **WHEN** a manifest uses uppercase/unprefixed hashes, pretty JSON, a missing final newline, or a consumer file contains an author identity such as `maintenance_unit_id`
- **THEN** consumer verification blocks and reports the precise wire or author-boundary finding

#### Scenario: Re-sealed malformed member inventory
- **WHEN** a producer re-computes both manifest hashes after adding duplicate, unsafe, unsorted, or malformed file rows
- **THEN** consumer verification blocks on the member-inventory finding before treating the hashes as authority

### Requirement: Installation and registry currentness bind declared authorities
Installation currentness SHALL bind the exact generated contract authorities that are copied into the installed member, and the private global registry SHALL retain a diagnostic hash for a declared target surface inventory without changing route identity. A declared but missing or unsafe surface inventory SHALL block that registry entry.

#### Scenario: Generated installation authority changes
- **WHEN** an installed generated contract authority differs from the frozen installation projection
- **THEN** active-installation currentness is blocked even when the ordinary source component hashes are unchanged

#### Scenario: Surface inventory diagnostic changes
- **WHEN** a target's declared surface inventory changes while its route behavior remains unchanged
- **THEN** the registry route hash remains stable but the diagnostic inventory hash changes
