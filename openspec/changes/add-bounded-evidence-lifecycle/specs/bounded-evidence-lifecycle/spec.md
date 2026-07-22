## ADDED Requirements

### Requirement: Canonical maintenance-unit evidence store
Every maintained unit MUST declare exactly one canonical owner-evidence root for current heads, immutable receipts, stream objects, lifecycle pins, and lifecycle receipts. A second writable authority or an unresolved root MUST block execution and lifecycle mutation.

#### Scenario: One current store is resolved
- **WHEN** the frozen maintenance-unit plan resolves one contained owner-evidence root
- **THEN** every current owner receipt and sidecar SHALL be published beneath that root

#### Scenario: Multiple writable stores are discovered
- **WHEN** current heads or receipts resolve to more than one writable evidence authority
- **THEN** planning SHALL block and no owner process, quarantine move, or purge SHALL start

### Requirement: Compressed streams retain logical evidence identity
Complete stdout and stderr MUST be stored as deterministic compressed objects whose references bind both the original logical bytes and the physical stored bytes. Replay MUST verify containment, storage encoding, stored length/hash, decompressed length/hash, and execution-result logical hash before accepting the receipt.

#### Scenario: Identical output is persisted twice
- **WHEN** two executions in one maintenance unit produce identical stream bytes
- **THEN** both references SHALL bind the same logical identity and the same single deterministic physical object

#### Scenario: Stored or logical bytes are corrupted
- **WHEN** the compressed bytes, storage metadata, decompressed length, or logical hash differs
- **THEN** replay SHALL reject the receipt and SHALL NOT fall back to an uncompressed or alternate object

#### Scenario: Decompressed output exceeds its bound
- **WHEN** a compressed object would exceed its declared logical length or configured safety ceiling
- **THEN** replay SHALL stop safely and report the object as invalid

### Requirement: Bounded diagnostics and complete sidecars remain distinct
An execution receipt MUST expose bounded diagnostic head/tail text for routine inspection and MUST retain complete stdout/stderr only through verified sidecar references. Diagnostic excerpts MUST NOT substitute for complete evidence.

#### Scenario: A large successful output is recorded
- **WHEN** a declared check emits output larger than the diagnostic budget
- **THEN** the receipt SHALL contain bounded head/tail diagnostics and one verified complete compressed sidecar reference

### Requirement: Evidence lifecycle is reachability-based
Lifecycle classification MUST derive transitive reachability from one exact current-head authority per producer, one exact current-aggregation authority per maintenance-unit member/profile, active attempts, closure receipts, installation/release pins, retained failed diagnostics, and explicit historical pins. Historical head or aggregation files MUST NOT remain current merely because they still exist in content-addressed directories. Exact TestMesh installation/global-prompt bindings MUST remain external-domain identities verified by aggregation replay and MUST NOT become a second owner-evidence authority. Reachable evidence MUST NOT be classified as collectible because of age, size, name, or command similarity.

#### Scenario: A blob is shared by current and old receipts
- **WHEN** any current or pinned receipt still references the blob
- **THEN** the blob SHALL remain reachable and SHALL NOT enter a collection plan

#### Scenario: A newer aggregation replaces current authority
- **WHEN** a passing TestMesh aggregation is published for the same maintenance-unit member and profile
- **THEN** its current-aggregation authority SHALL atomically select the new immutable aggregation, the prior aggregation SHALL cease to be a root unless separately pinned, and exact typed installation/global-prompt bindings SHALL remain outside the internal evidence graph

#### Scenario: An object has no path from any declared root
- **WHEN** a complete store audit proves the object is unreachable and unowned by an active writer
- **THEN** it MAY be classified as `orphan` with its exact reason, hash, and byte count

#### Scenario: Reachability is ambiguous or corrupt
- **WHEN** a referenced object is missing, corrupt, path-escaping, cyclic outside the allowed schema, or bound to multiple authorities
- **THEN** mutation SHALL block and the finding SHALL remain visible

#### Scenario: Writer and collection would race
- **WHEN** a producer is reading or publishing evidence while apply or purge requests the same store
- **THEN** writer registration and lifecycle mutation SHALL coordinate through one short barrier, the active marker SHALL block collection, and neither side SHALL observe a partially published current authority

### Requirement: Audit and planning are read-only
`evidence-audit` and `evidence-gc-plan` MUST perform zero filesystem writes and MUST emit canonical results to stdout. A GC plan MUST bind the evidence-root identity, policy identity, complete inventory snapshot hash, candidate inventory, reasons, byte counts, and plan hash.

#### Scenario: Audit and plan complete
- **WHEN** the evidence tree is snapshotted before and after either command
- **THEN** the snapshots SHALL be identical

#### Scenario: Store changes after planning
- **WHEN** any root, head, receipt, pin, object, or lifecycle policy changes after the plan snapshot
- **THEN** the old plan SHALL be stale and apply SHALL make zero changes

### Requirement: Collection quarantines before purge
`evidence-gc-apply` MUST move only exact plan candidates into an explicit quarantine root after revalidating the frozen snapshot. `evidence-gc-purge` MUST delete only exact quarantined objects bound to a complete apply receipt, matching plan hash, satisfied grace policy, and fresh reachability audit.

#### Scenario: Current plan is applied
- **WHEN** the plan, root, inventory, and candidates still match exactly
- **THEN** apply SHALL atomically quarantine only the named objects and publish a durable recovery journal plus an immutable receipt without permanently deleting them

#### Scenario: Apply is repeated
- **WHEN** the exact completed apply request is repeated
- **THEN** it SHALL be idempotent and SHALL NOT move or duplicate additional objects

#### Scenario: Windows temporarily blocks a journal replacement
- **WHEN** a mutable lifecycle journal cannot be atomically replaced because of a transient permission or sharing hold
- **THEN** the same operation owner SHALL retry only that publish step within a bounded budget and SHALL fail visibly without starting another cleanup owner if the budget is exhausted

#### Scenario: Purge stops after deletion but before journal completion
- **WHEN** an item is recorded as prepared, its quarantine file is absent, and no terminal purge receipt exists
- **THEN** a repeated exact request SHALL resume the same deterministic purge identity, record the item as deleted, and continue without treating the intended deletion as an unrelated missing object

#### Scenario: Purge targets an active store
- **WHEN** a purge request names an active evidence object or scans the active evidence root directly
- **THEN** purge SHALL reject the request with zero deletions

#### Scenario: Pinned replay fails before purge
- **WHEN** any current or release-pinned receipt cannot be replayed after quarantine
- **THEN** purge SHALL block and the quarantined objects SHALL remain recoverable

### Requirement: Validation cleans only unpublished temporary evidence
Ordinary validation MAY remove only temporary capture/staging files created by the same attempt and not yet published into immutable evidence authority. It MUST NOT invoke persistent collection or purge as a hidden side effect.

#### Scenario: Atomic publication succeeds or fails
- **WHEN** a run finishes publishing or aborts before publication
- **THEN** its unpublished temporary capture files SHALL be removed without changing current, pinned, historical, failed-diagnostic, or quarantined evidence
