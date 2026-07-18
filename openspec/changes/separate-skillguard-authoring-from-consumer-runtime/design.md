## Context

SkillGuard was designed to make a maintained skill state what it promises, execute every target-declared check, and prevent shallow or prose-only closure. Later changes added multi-skill owner plans, receipt consumers, portable project adoption, global route projection, Portfolio reuse tickets, and installation of contract control files. Those mechanisms solved repeated execution inside the maintenance environment, but they also made graduated skills and ordinary projects carry SkillGuard.

The current repository already has executable FlowGuard owners for declared-check supervision, validation composition, current runtime authority, Portfolio lifecycle, template lifecycle, global routing, and development-process freshness. This change extends or contracts those owners; it does not introduce a parallel framework.

Current installed targets have mixed layouts. Most carry only SkillGuard metadata, while twenty Guard-family skills contain target-domain runtime beneath `.skillguard/runtime`. Consumer cleanup therefore cannot be a recursive delete. Target-domain files must move first and retain native behavior, imports, manifests, and hashes.

Official OpenSpec is an external specification provider. Its supported artifacts are proposal, design, specs, and tasks. FlowGuard may read those artifacts as development-process context, but OpenSpec does not own FlowGuard tests and must not consume SkillGuard or FlowGuard receipts.

## Goals / Non-Goals

**Goals:**

- Keep SkillGuard as an author-side skill cultivation, depth, audit, and release system.
- Make every graduated consumer skill independently installable and usable without SkillGuard.
- Prevent ordinary business projects from receiving SkillGuard state or prompt blocks.
- Give every maintained skill or inseparable release family an explicit maintenance-unit identity.
- Isolate checks, execution keys, receipts, dependencies, and evidence roots by maintenance unit.
- Detect duplicate semantic responsibility as a boundary defect rather than normalize it through shared evidence.
- Preserve target-native checks, exact inventory reconciliation, immutable receipts, timeout cleanup, and affected-only revalidation.
- Restore official OpenSpec skills and remove cross-tool receipt/session/cache bridges.
- Migrate existing installations safely and synchronize canonical source, installed projections, and Git state.

**Non-Goals:**

- SkillGuard does not judge the domain meaning or sufficiency of a target's native checks.
- This change does not guarantee future AI behavior or factual correctness.
- It does not rewrite archived OpenSpec history.
- It does not preserve old runtime schemas, aliases, converters, dual manifests, or compatibility readers.
- It does not remove target-domain runtime until an equivalent target-owned location is verified.

## Decisions

### 1. Author control and consumer distribution are different projections

The compiler SHALL produce two disjoint projections:

- `projection:maintainer-control` may contain contracts, models, tests, receipts, Portfolio state, router state, and author prompts.
- `projection:consumer-distribution` may contain only the target's domain entrypoint, prompts, references, assets, scripts, native runtime, and a target-owned release manifest.

The consumer projection SHALL reject `.skillguard/**`, SkillGuard managed prompt markers, SkillGuard imports or commands, receipts, Portfolio data, and router state.

Alternative considered: keep the contract trio in consumers as inert metadata. Rejected because inert control files still make consumer currentness depend on SkillGuard and recreate the original boundary error.

### 2. Maintenance unit is the outer evidence namespace

Every maintained target SHALL declare `maintenance_unit_id`. A release family may list `member_skill_ids`, but each check also names `member_skill_id` and `evidence_subject_id`. A unit-level check is legal only when it has one explicit package-level owner and is not duplicated under several members.

Execution identity includes:

```text
maintenance_unit_id
member_skill_id
evidence_subject_id
semantic_check_id
execution_owner_id
owner_input_projection_hash
dependency_receipt_ids
toolchain_identity
environment/evidence_domain identity
```

Same-unit, same-check, same-input requests may single-flight. A foreign-unit dependency or receipt is rejected even when its command and hashes match. Duplicate semantic ownership across units is a boundary-audit failure requiring split, merge, or retirement.

Alternative considered: keep one task-level multi-skill owner plan. Rejected because it makes receipt sharing an architectural default and hides duplicate responsibilities.

### 3. Author runtime state requires an explicit author root

Supervisor and run-store APIs SHALL require an author-maintenance context and an explicit author evidence root. They SHALL NOT default to `target_root` or an ordinary project root. Business-project eligibility checks run before any directory creation and fail with zero writes.

Project adoption is replaced by explicit maintainer-repository adoption. The manifest may exist in a canonical skill-authoring repository, but it is never part of the consumer projection.

### 4. TestMesh and Portfolio are narrowed, not discarded

TestMesh retains frozen plans, dependency ordering, same-unit single-flight, immutable aggregation, timeout cleanup, and affected-only revalidation. OpenSpec receipt projection and cross-unit parent proof are removed.

Portfolio becomes a private independent scorecard:

- inventories explicit managed units and external exclusions;
- audits semantic-owner overlap;
- records each unit's own source-maintenance and consumer-isolation evidence;
- aggregates statuses without transferring proof;
- keeps unaffected unit receipts current when their exact inputs did not change.

Reuse-ticket commands and schemas are retired. No ticket is needed when a unit's own evidence remains current.

### 5. Global router is an author maintenance registry

The router reads an explicit `managed_targets` registry and `external_exclusions`. It answers which target SkillGuard is maintaining, not which ordinary domain skill Codex should use. Missing contracts on unregistered skills are irrelevant to ordinary use.

The managed global prompt is installed only on the author machine and is excluded from consumer installation. Official OpenSpec entries are `external_excluded`, not blocked targets.

### 6. Consumer installation uses safe withdrawal

Consumer distribution is staged, validated, atomically activated, and rollbackable. During upgrade, the installer removes only files previously owned by its manifest and unchanged since installation. Modified files are preserved and reported as conflicts.

Before exclusion, the builder scans `.skillguard/runtime` and all declared references. If target-domain code or data would be lost, the build blocks until those assets move to a target-owned namespace and native parity is proven.

### 7. OpenSpec is external and FlowGuard context is read-only

Official OpenSpec skills are regenerated from the pinned official package and atomically replace locally modified copies. SkillGuard does not add contracts or prompts to those directories.

FlowGuard may retain a lightweight `SpecContext` containing provider, change, requirement, task, and status identifiers. It SHALL NOT carry test commands, execution ownership, sessions, caches, or receipt references. FlowGuard's native models and tests remain independently owned.

### 8. Existing FlowGuard owners are contracted in place

The existing declared-check and validation-composition models are updated with maintenance-unit isolation and consumer-projection boundaries. Runtime-authority, Portfolio, template-lifecycle, and router models are revised or reduced. Cross-skill/OpenSpec receipt behavior becomes known-bad evidence rather than a second current path.

Public CLI removals and renamed author-only commands require StructureMesh/public-surface parity evidence. Historical command names remain rejection fixtures only.

### 9. Direct current replacement

New schemas and commands become the sole current authority. Old schemas, receipts, project blocks, reuse tickets, OpenSpec projection commands, and consumer contract layouts have no normal-runtime reader or alias.

Historical OpenSpec changes and Git commits remain audit history, but no live code consumes them.

## Risks / Trade-offs

- **[Hidden target runtime is deleted]** → Classify every `.skillguard` descendant, freeze file hashes, move target-domain runtime first, and block consumer construction on unresolved references.
- **[Maintenance unit is defined too broadly]** → Require member and evidence-subject identity on every check and reject duplicate semantic ownership even inside a release family unless it is one explicit unit-level owner.
- **[Current dirty worktrees are overwritten]** → Use the clean current SkillGuard worktree, inspect FlowGuard peer changes before edits, and merge without reset or checkout-based discard.
- **[Official OpenSpec customization is accidentally restored]** → Generate candidates from the pinned official package, compare whole directories, atomically replace, and rerun official update as an idempotence check.
- **[Consumer cleanup removes user modifications]** → Withdraw only installer-owned, hash-unchanged files; preserve and report conflicts.
- **[Validation is duplicated in the background]** → Use safe parallel execution only for isolated focused owners. Freeze one final full owner after the source and toolchain reach a fixpoint.
- **[Large migration produces stale evidence]** → Validate each maintenance unit independently, record exact artifact versions, and run the final full gate only after all source and installation projections are frozen.

## Migration Plan

1. Freeze the clean SkillGuard source identity, active changes, installed-target inventory, dirty peer worktrees, and `.skillguard` file classifications.
2. Update existing FlowGuard models and requirements for author/consumer separation and maintenance-unit evidence isolation.
3. Replace current contract schemas and compiler projections.
4. Bind check execution, receipts, supervisor, run store, and TestMesh to the maintenance unit and explicit author roots.
5. Split maintainer deployment from consumer distribution.
6. Contract Project Adoption, Global Router, Portfolio, templates, prompts, and public CLI surfaces.
7. Run focused model and unit checks, then one SkillGuard self-host gate before modifying installed external targets.
8. Restore official OpenSpec skills and register them as external exclusions.
9. Migrate FlowGuard's 17 skills as the metadata-only pilot; update its installer, suite validators, project adoption, shadow sync, and specification context.
10. Migrate targets without hidden runtime.
11. Migrate SourceGuard, WorldGuard, TraceGuard, LogicGuard, and PhysicsGuard families after target-owned runtime relocation and parity checks.
12. Build and activate clean consumer projections, refresh author-only routing, synchronize local source repositories and installed copies, and commit the final Git state.
13. Freeze one final validation plan and run the complete model/test/install/consumer-isolation verification once.

Rollback uses the prior installed transaction and source commit. It never restores a compatibility reader. A failed unit rolls back its own installation while preserving the author source and failure evidence.

## Open Questions

None. The user has explicitly selected author-side SkillGuard maintenance, independent graduated skills, official unmanaged OpenSpec, no cross-unit evidence sharing, forward replacement, and complete local synchronization.
