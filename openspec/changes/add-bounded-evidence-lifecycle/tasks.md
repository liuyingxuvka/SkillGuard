## 1. Freeze authority and executable models

- [x] 1.1 Register the SkillGuard maintenance-plane commitments, fields, owner boundaries, and direct-replacement disposition for evidence lifecycle and explicit producer projections.
- [x] 1.2 Extend the existing validation-composition FlowGuard model with producer/projection, compressed evidence, reachability, quarantine, purge, and no-hidden-cleanup cases.
- [x] 1.3 Add TestMesh and StructureMesh rows for codec, replay, lifecycle CLI, installation projection, and public entrypoint ownership.

## 2. Explicit producer and semantic projection contract

- [x] 2.1 Replace implicit signature-based owner grouping with a unique producer per check unless the current source contract explicitly declares a shared execution owner.
- [x] 2.2 Validate that explicitly shared producer rows have identical producer behavior, inputs, target-input roles, toolchain, and environment while retaining distinct semantic projections, evidence domains, and dependency rows.
- [x] 2.3 Update source/compiled schemas, manifest generation, fixtures, and compiler tests for explicit producer-to-projection identity and fail-closed mismatches.
- [x] 2.4 Update SkillGuard's self contract so repeated FlowGuard model assertions explicitly share only the producer executions declared by the target.

## 3. Compressed immutable evidence objects

- [x] 3.1 Add deterministic streaming gzip persistence with separate logical-content and storage-content identities and atomic publication.
- [x] 3.2 Directly replace stdout/stderr receipt references with the current compressed stream schema while leaving small JSON result/termination references bounded.
- [x] 3.3 Update replay to verify path containment, stored hash/length, encoding, bounded decompression, logical hash/length, and execution-result binding.
- [x] 3.4 Update runner and receipt tests for empty, large, identical, corrupt, path-escaping, and decompression-budget cases.

## 4. Reachability and lifecycle commands

- [x] 4.1 Implement canonical evidence-store discovery and a reference graph rooted in exact per-owner current-head authorities, active attempts, closure/aggregation receipts, installation/release pins, retained failures, and explicit historical pins.
- [x] 4.2 Implement lifecycle classification and fail-closed findings for multiple or missing current authorities, missing/corrupt references, path escape, unsupported cycles, and active writers, with one short barrier coordinating writer registration and collection mutation.
- [x] 4.3 Implement read-only `evidence-audit` and `evidence-gc-plan` commands with canonical JSON, inventory snapshots, exact candidates, reasons, byte totals, and plan hashes.
- [x] 4.4 Implement stale-plan-safe `evidence-gc-apply` with atomic quarantine, journaled recovery, immutable apply receipt, and idempotent replay.
- [x] 4.5 Implement quarantine-only `evidence-gc-purge` with exact apply/plan identity, grace and fresh-audit gates, active-root rejection, and immutable deletion receipt.
- [x] 4.6 Add lifecycle schemas and tests proving read-only audit/plan, shared-blob retention, pin safety, zero-mutation stale plans, recoverable partial apply, and quarantine-only purge.

## 5. Installation and temporary-output hygiene

- [x] 5.1 Restrict installed currentness identity to exact `projection:installation` content without source-only contract/check/workflow fingerprints.
- [x] 5.2 Run installed smoke with Python bytecode disabled and reject `.pyc` or `__pycache__` residue in stage/installed projection tests.
- [x] 5.3 Ensure normal validation removes only its own unpublished temporary captures and never invokes persistent evidence collection.

## 6. Contracts, documentation, and generated authority

- [x] 6.1 Update SkillGuard `SKILL.md`, execution-records, TestMesh, supervisor, installation, and operator references with the target-sovereignty and lifecycle boundaries.
- [x] 6.2 Update the canonical schema inventory, public-export/privacy expectations, version records, changelog/release notes, and README cross-computer workflow.
- [x] 6.3 Recompile the complete self-maintenance inventory and generated contract/check manifest after all source/toolchain identities are frozen.

## 7. Verification, cleanup, installation, and release

- [x] 7.1 Run focused codec, compiler, runner, lifecycle, TestMesh, installation, privacy, and model checks; fix all failures before broad validation.
- [x] 7.2 Freeze one final SkillGuard TestMesh execution plan and run exactly one final full validation owner, reusing only exact current receipts.
- [x] 7.3 Install the new consumer projection transactionally, run installed currentness and smoke checks, and prove source/install parity with no bytecode residue.
- [x] 7.4 Run lifecycle audit and plan on the legacy working evidence, quarantine only proven unreachable objects, replay current/release pins, and purge only after the explicit safety gates pass.
- [ ] 7.5 Commit and push the exact validated SkillGuard source, tag the new version, verify tag/version/commit identity, and publish the source-only GitHub Release without rerunning the regression suite.
- [ ] 7.6 Complete OpenSpec verification/archive readiness, SkillGuard closure, and predictive-KB postflight records with bounded claim language.
