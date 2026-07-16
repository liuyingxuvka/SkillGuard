## Context

SkillGuard currently validates one maintenance change through several independently useful layers: cheap contract and manifest checks, executable TestMesh suites, OpenSpec verification, staged installation, active-installation parity, external target synchronization, and global prompt projection. The layers are fail-closed, but they do not yet share one validation-composition contract. As a result, the same pytest command can be executed repeatedly, a directory fingerprint can ignore non-Python inputs, and each subsystem can make a different decision about whether a path such as `.sg-runtime` is portable.

The current OpenSpec runner also permits a verification report to be included in its own freshness input set. Rewriting that report then makes the just-completed verification stale. This is an ordering defect, not useful revalidation.

This change crosses the TestMesh runtime, installation and provenance paths, generated-contract checks, OpenSpec verification contracts, schemas, CLI entrypoints, and the FlowGuard model mesh. It must preserve the existing target-owned route rule: SkillGuard supervises execution depth and evidence quality but does not replace a maintained skill's native semantic executor.

## Goals / Non-Goals

**Goals:**

- Make cheap structural and authority blockers run before expensive suites.
- Give every expensive child execution a complete content-addressed identity and immutable result.
- Permit a current passing child result to be reattached to another current parent profile only through an exact, auditable reuse decision.
- Invalidate reuse for any relevant command, input, environment, manifest, ownership, coverage, verifier, result, or domain change.
- Use one artifact-classification policy for source inventories, installation, parity, provenance, privacy, fixtures, and synchronized target trees.
- Reject source or installed trees containing runtime workspaces and generated test outputs.
- Reject OpenSpec verification contracts whose report watches itself.
- Preserve separate evidence domains for canonical source, staged install, active install, synchronized targets, and global prompt projection.

**Non-Goals:**

- Replacing target-owned semantic checks with generic SkillGuard checks.
- Treating a focused parent profile as proof of a full parent profile.
- Reusing failed, skipped, timed-out, cancelled, partial, progress-only, foreign, stale, or mutable evidence.
- Skipping stage, active-installation, external-target, or global-prompt checks because source tests passed.
- Creating a general remote build cache or accepting evidence from an untrusted machine.
- Making runtime artifacts portable merely because a fixture uses a similarly named nested path as static test data.

## Decisions

### 1. Model validation as an ordered ownership graph

The canonical order is:

1. runtime authority, generated-contract, manifest, artifact-boundary, and source-inventory preflight;
2. model and contract consistency checks;
3. affected TestMesh child execution or exact child reuse resolution;
4. parent-profile coverage and closure reattachment;
5. staged-install parity and staged smoke checks;
6. active-install parity and active smoke checks;
7. synchronized-target and global-prompt checks.

Each node declares one evidence domain and one validation owner. A downstream node may consume an immutable current receipt from an earlier node, but it may not silently rerun the same command under another label or use a source-domain receipt to satisfy an installation-domain obligation.

Alternative considered: keep every layer fully independent and rerun all commands. This is simpler but preserves the observed duplication and makes validation duration grow with the number of wrappers rather than with affected behavior.

### 2. Freeze a complete source inventory before executing a child

Each declared source path expands to all regular files recursively, not only `*.py`. The inventory records normalized relative path, file kind, size, and SHA-256. Missing paths, path escapes, symlinks with unsafe targets, duplicate normalized paths, unreadable files, and unclassified runtime paths are blockers. The inventory hash, policy version, and inventory rows are stored with the child result.

The portable-artifact policy supplies the only exclusions. An exclusion is therefore reviewable and versioned instead of being an implicit suffix filter. Schemas, JSON fixtures, Markdown contracts, FlowGuard models, configuration, and other non-Python inputs participate whenever they are under a declared source path.

Alternative considered: add a longer hard-coded extension allowlist. It would still miss future input types and would diverge from installation policy.

### 3. Centralize portable-versus-runtime classification

A shared path-policy module returns a typed classification plus reason and policy version. At minimum it distinguishes:

- `portable_source`: maintained code, prompts, schemas, static fixtures, models, contracts, documentation, and generated authorities intentionally shipped by the skill;
- `runtime_ephemeral`: `.sg-runtime`, `.sg-fixtures`, `.sgf`, `.runtime_workspaces`, caches, transient locks/runs/bootstrap outputs, test result roots, and temporary generation workspaces;
- `unsafe_or_unknown`: escaped paths, unsafe links, malformed paths, and contextually ambiguous runtime-looking content.

Classification is context-aware: a static fixture may intentionally contain a nested `.skillguard/runs` sample beneath the fixture member root, while a live `.skillguard/runs` directory at a maintained skill root remains runtime-only. The installer, installed parity, provenance, privacy audit, source inventory, compiler/runtime fingerprint, fixture cleanup, and synchronization checks consume the same classifier or an explicitly named projection of it.

Alternative considered: duplicate ignore sets in each subsystem. This is the present failure mode and cannot prove consistent boundaries.

### 4. Reuse only direct, immutable TestMesh child proof

Reuse is resolved per child, never per whole parent profile. A reusable source child must have:

- `passed` status, a real process start and zero skipped checks;
- direct terminal proof (`final_exit_and_captured_output`), not a previous reuse chain;
- current immutable result bytes matching its recorded result hash and locator;
- the same manifest hash and suite semantic declaration;
- the same normalized command fingerprint;
- the same complete source-inventory hash and artifact-policy version;
- the same environment and verifier/runtime fingerprints;
- the same owned coverage partitions and compatible target-profile requirements;
- no truncation, timeout, cancellation, partial status, or not-run child.

The reuse resolver creates an immutable ticket binding the source child, source profile declaration, target profile declaration, current manifest, current suite execution identity, required partitions, and target result root. The target parent receives a new child projection with `proof_kind: reused_current_child`, the ticket hash, and the direct source-result reference. The parent still performs its own current required-partition and closure checks. A focused parent therefore cannot become a full parent receipt; only a qualifying child execution can be reattached inside a newly evaluated full parent.

If any equality or compatibility check fails, the affected child executes normally. Invalid supplied evidence is visible as a reuse rejection; it is never treated as a pass. Reuse does not cross source, stage, active-installation, synchronized-target, or global-prompt evidence domains.

Alternative considered: reuse an entire focused parent when the full command text looks similar. That would erase full-profile ownership and claim boundaries.

### 5. Make failure and non-execution visible

Fail-fast stops later expensive children after a cheap or earlier hard blocker, but the result still materializes explicit `not_run` children and skipped obligations. A stopped graph is not reported as complete. Parent closure requires every selected child to be either directly passed or accepted by an exact current reuse ticket and every required partition to be owned.

### 6. Block verification outputs from source freshness before execution

Verification-contract lint resolves the report path, declared result/receipt roots, and every freshness file/glob relative to the declared root. If the report is included directly, through a glob, through normalization, or through a symlinked equivalent, verification blocks before any check runs with `verification_report_in_freshness_watch`. If a receipt, result, progress log, runtime workspace, ambiguous `.skillguard` control glob, or declared evidence root is watched as source, it blocks with `verification_evidence_output_in_freshness_watch`. Evidence currentness is recomputed by the read-only consumer check; writing evidence never refreshes its producer's source identity.

SkillGuard adds this rule to maintained-contract review and applies the durable runner change in the native OpenSpec source repository when a maintainable checkout is available. Patching only an installed package is not considered source closure. Existing SkillGuard contracts are migrated to explicit non-overlapping input sets and unique check ownership.

### 7. Extend the existing FlowGuard mesh

A new validation-composition child model owns artifact classification, inventory freezing, reuse resolution, affected-child execution, parent reattachment, and domain handoff. It uses `Input x State -> Set(Output x State)` function blocks. The existing SkillGuard contract model remains the portable semantic parent; DevelopmentProcessFlow owns lifecycle ordering; TestMesh owns test hierarchy; FieldLifecycleMesh records new fields; ModelMesh proves child reattachment and affected-sibling review.

### 8. Single-flight exact checks and read-only parent consumers

Supervisor and self-host requests share one content-addressed execution authority. `semantic_check_id` names what the check means, `execution_id` names one concrete attempt, and `execution_key` binds the exact source/contract/manifest/step/target/environment inputs. Only a complete terminal-success receipt updates the reusable success head. Failed attempts remain append-only diagnostics and cannot satisfy later requests; source changes stale the key, while generated runtime output is excluded from source authority.

The full-parent consumer is a verifier only. Missing, partial, stale, foreign, tampered, or identity-incomplete receipts fail closed. The consumer has no execute, resume, repair, backfill, or owner-fallback branch, so OpenSpec cannot become a second TestMesh executor.

The canonical managed-prompt policy `skillguard.validation_execution_ownership.v2` closes the surrounding execution boundary. Before multi-skill validation, the existing verification contract or TestMesh freezes the exact checks, obligations, evidence domains, dependency order, persistent receipt roots, and one primary execution owner per check. Every consumer resolves the exact current owner receipt and cannot carry or rerun the owner command. Maintained inputs invalidate only affected receipts, while reports, receipts, progress logs, and other runtime outputs cannot refresh source authority or trigger their own validation. `--resume` is always treated as an executor; a full parent begins only after source and toolchain fixpoint under one explicit owner; timeout, cancellation, or interruption requires a confirmed zero descendant process count before any evidence or next owner; and Windows Scheduled Tasks, background resume, or unattended retry cannot run full validation or resume a mutable worktree. These process rules remain distinct from the parent receipt itself, so prompt projection cannot substitute for source, installation, or TestMesh evidence.

### 9. Compile one content-impact graph from the existing authorities

`implementation_paths` remains the complete maintenance inventory boundary, but its combined hash no longer becomes every check's freshness input. The existing compiler expands those paths, applies the shared portable-content policy, assigns a semantic role and installation disposition, resolves exact check and projection consumers, and groups files that share `(role, install_disposition, consumer_ids)` into stable components.

The binding source adds only the information that cannot be inferred safely:

- each check declares `input_selectors`, `depends_on_check_ids`, and `evidence_domain_id`;
- `projection_consumers` declares non-check consumers such as installation, installed parity, Portfolio impact, contract generation, static review, managed prompt, and global router;
- `content_role_overrides` resolves exceptional ambiguous paths without becoming a second classifier. A reviewed path may name one maintained file or one maintained directory subtree; a directory applies to every inventoried descendant, including future descendants, and overlapping selectors block instead of using precedence;
- `persistent_receipt_root` declares a portable path token and relative owner-evidence root.

The compiler writes `content_impact_plan` into the existing compiled contract and check manifest; it does not create a fourth authority file. Each component records `component_id`, `role`, `install_disposition`, sorted member paths, `component_hash`, and exact consumer ids. Each execution owner records `execution_owner_id`, exact input component ids, dependency owner ids, full normalized owner declaration hash, and owner input-projection hash. Health rows expose `unmapped_paths`, `ambiguous_role_paths`, `duplicate_owner_ids`, and `owner_cycles`; any non-empty row blocks compilation and execution.

### 10. Separate semantic execution identity from attempts and aggregations

An owner's semantic execution key binds only its execution owner id, complete normalized behavior declaration, exact input-component projection, dependency receipt hashes, target inputs, command/toolchain, environment/verifier, evidence domain, and impact-policy version. Unknown behavior-bearing declaration fields fail closed.

`run_id`, `step_id`, timestamps, nonce, display/generated text, parent profile, parent manifest hash, full contract hash, and aggregation identity are excluded from the semantic key. They remain in an `attempt_id` or audit envelope. This permits an exact terminal-success receipt to be reused across runs while ensuring any real owner declaration, input, dependency, toolchain, or environment change becomes stale.

Owner success is published beneath the declared persistent evidence root as immutable content-addressed receipt, record, stdout, stderr, result, and termination sidecars. Run-local records are projections of that owner receipt. A missing/tampered sidecar, changed owner input, or unknown receipt shape is stale; failed attempts never create a reusable head.

### 11. Derive TestMesh work before execution

TestMesh first performs a side-effect-free `plan-only` phase against a frozen source snapshot and emits:

- `changed_component_ids`;
- `will_reuse_owner_ids`;
- `will_execute_owner_ids`;
- `will_aggregate_only`;
- `required_install_component_ids`;
- `required_router_refresh`;
- `required_portfolio_target_ids`;
- `full_required_reason_codes`;
- `plan_hash`.

Execution must present the same plan hash. Parent profile or aggregation-only changes create a new parent identity without changing child semantic execution keys. A child owner executes only when its exact receipt is absent or stale. Full is admitted only for an explicit final/release gate, a change to the impact compiler/policy itself, a shared verifier/runtime core that genuinely reaches all owners, or an explicitly modeled shared component that all owners consume. Uncertainty, installation, fixture changes, parent-manifest changes, or insurance are not full-admission reasons.

### 12. Project the same graph into installation, Portfolio, and routing

The installer remains one atomic staged transaction with rollback, but stages only `copy` and `generate` components. `source_only` and `exclude` components are not installed. Whole-tree byte parity remains a cheap integrity check; executable smoke validation is limited to affected install-owner projections.

Portfolio impact no longer trusts a caller-authored `broad_semantic_change`. It derives changed components, affected capabilities, target/member edges, and the impact graph hash. A change reaches all targets only through an explicit shared component edge. Global-router refresh is required only for skill add/remove/rename, route-entrypoint or native-binding changes, global routing policy, or managed prompt components.

The validation policy text has one canonical source. Project adoption, checker rendering, installed SkillGuard, and the global managed prompt consume that projection. The prompt states that ordinary skill use does not run SkillGuard; skill maintenance, installation, migration, or release enters SkillGuard, loads the frozen impact plan, and executes only `will_execute_owner_ids`.

### 13. Keep one current daily protocol

The V1 migration suite and alternate runtime authority leave the daily TestMesh and router path. Old shapes remain bounded negative fixtures that must be rejected by the current parser; they are never converted, auto-aliased, or accepted as fallback success. Protocol-version changes naturally stale old receipts, but runtime code has one accepted current shape.

## Risks / Trade-offs

- **[Risk] An overly broad runtime rule removes legitimate fixture evidence.** → Use context-bearing classifications and positive static-fixture regression cases, including nested control-shaped sample paths.
- **[Risk] Reuse accepts evidence after a hidden input changes.** → Inventory every regular file under declared inputs, bind the policy/verifier/environment/manifest/command/coverage identities, and test non-Python mutations.
- **[Risk] Reuse logic becomes another unverified validator.** → Give it schemas, executable FlowGuard scenarios, positive and adversarial fixtures, replay, and tamper tests.
- **[Risk] More metadata makes receipts larger.** → Store the deterministic inventory once per child and retain hashes in parent projections; correctness takes precedence over a small receipt-size increase.
- **[Risk] Native OpenSpec source is unavailable.** → Keep SkillGuard's maintained-contract blocker, record the native runner task as blocked rather than patching only installed bytes, and do not claim ecosystem-wide closure.
- **[Risk] Parallel repository work changes touched files.** → Re-read before every patch, keep edits narrow, and rerun affected checks after peer writes.
- **[Risk] Empty cross-domain sentinel is mistaken for a scheduled-production identity.** → Gate installation identity loading by the exact `scheduled_production` evidence domain, accept only absent/empty sentinels elsewhere, and keep non-empty cross-domain identities blocked.
- **[Risk] A valid nested skill repository path is replayed relative to the skill root twice.** → Compile and hash one repository-relative `member_root_path`, strip exactly that declared root during replay, and block every path outside it before copy or activation without layout inference.
- **[Risk] Target installation corrupts SkillGuard's own recovery chain or executes untrusted repository commands.** → Use a separate per-target transaction/HEAD namespace under the same global filesystem lock, copy only the exact installation projection, and make native target execution a separate receipt-owned step.

## Migration Plan

1. Add the FlowGuard child model, ModelMesh relationships, behavior commitments, and field-lifecycle rows; run executable scenarios before runtime edits.
2. Add the shared artifact policy and adopt it first in inventory and installation paths, then in parity, provenance, privacy, fingerprint, fixture, and synchronization consumers.
3. Add complete source inventories, child reuse tickets, replay validation, CLI inputs, schemas, and adversarial fixtures.
4. Reorder validation so cheap blockers precede child execution and update TestMesh profiles to use non-overlapping ownership.
5. Add the SkillGuard OpenSpec collision check and, if a native OpenSpec checkout is found, implement and test the same pre-execution blocker there.
6. Remove runtime workspace residue from canonical and installed trees through scoped verified cleanup; add ignore protection.
7. Reach one source/contract/model/task fixpoint, run the fixed-input affected regression, then install transactionally and prove source/stage/active parity with one current installation receipt.
8. Extend the existing validation-composition model with component impact compilation, affected-plan derivation, exact owner receipt resolution, stale-owner execution, aggregation-only behavior, and full-admission reasons; update FieldLifecycleMesh, TestMesh, ModelMesh, and DevelopmentProcessFlow evidence.
9. Add the content-impact compiler and health gate to the existing generated contract/manifest authorities, then migrate current SkillGuard checks and projections to exact selectors and dependencies.
10. Move check success receipts to the persistent content-addressed root, remove run/step/parent-wide identity from semantic execution keys, and add cross-run exact-reuse plus tamper/staleness regressions.
11. Make TestMesh, installation/parity, Portfolio, and global router consume the same frozen impact plan; retire the V1 daily suite and keep old shapes as rejection fixtures only.
12. Run only component-level affected model/unit regressions and a real FlowGuard-to-SkillGuard-to-OpenSpec receipt-consumption pilot; repair exact owners and refreeze without broad retry.
13. Freeze the installed identity, execute one installation-bound full TestMesh parent, let OpenSpec consume only its read-only receipt, refresh global routing, and resume Guard-family revalidation with the upgraded runtime.

Rollback is component-scoped inside one atomic installation transaction: the SkillGuard installer retains the previous active tree and restores it if post-activation checks fail. When an exact current receipt is absent, only the affected owner executes; there is no broaden-to-full compatibility branch. The shared artifact policy and complete inventory are not downgraded during rollback.

## Resolved integration decisions

- The durable OpenSpec collision and execution-lifecycle changes are maintained in the canonical OpenSpec source repository; SkillGuard consumes their frozen contract rather than patching an installed package.
- TestMesh retains distinct child ownership but allows exact focused-to-full child reuse only through immutable source-parent proof; OpenSpec never becomes a second full executor.
