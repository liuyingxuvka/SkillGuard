## 1. Contract and schema hardening

- [x] 1.1 Extend the depth-profile schema and semantic validator with non-empty obligation denominators, target-owned coverage-universe definitions, floor origins, strata, per-object depth, requested claim scope, and provider/runtime enrollment requirements.
- [x] 1.2 Extend target execution and calibration record schemas with coverage results, immutable contribution identity, exact calibration bindings, and provider/runtime audit evidence.
- [x] 1.3 Update compiler cross-validation to bind universe ids, native checks, calibration fixtures/hashes, portable exact command/input fingerprints, provider readiness checks, and native-route preservation.
- [x] 1.4 Add complete calibration input manifests, content-addressed native observation artifacts, class-aware per-object policies, native-critical scope, and portable repository/target root-role bindings to schemas and compiler semantics.
- [x] 1.5 Add discovered/declared/excluded object-scope attestations, child-universe identities, and native dynamic-floor policy/receipt schema semantics.

## 2. Runtime enforcement

- [x] 2.1 Refactor execution-depth evaluation to reject empty denominators and evaluate eligible/selected/validated counts, floors, strata, per-object depth, critical uncovered ids, and requested-versus-covered scope.
- [x] 2.2 Replace contribution-id uniqueness with native receipt hash, immutable evidence-payload hash, and normalized contribution-range uniqueness while preserving explicit shared-evidence rules.
- [x] 2.3 Resolve calibration from current immutable native check records and require exact fixture, command, input, expected non-pass status, and expected blocker bindings.
- [x] 2.4 Add provider/runtime readiness and enrollment audit using the actual active runtime identity/capabilities and current readiness receipts; remove caller-authored readiness authority.
- [x] 2.5 Extend supervisor packet validation, target receipt issuance, receipt replay, and closure consumption for the new evidence surfaces.
- [x] 2.6 Require issue/close/replay to carry independent `repository_root` and `target_root` authorities; block missing/collapsed/wrong roots and persist only portable content bindings.
- [x] 2.7 Add supervisor-only native observation derivation with content-addressed source receipt/check/range/input evidence while preserving direct empty-packet `NOT_RUN`.
- [x] 2.8 Enforce anti-shrink reconciliation and field-wise stricter compiled/native dynamic floors without a universal fixed-ratio override.

## 3. Self-host migration and documentation

- [x] 3.1 Add content-addressed representative-positive and shallow-negative calibration fixtures/check metadata and migrate SkillGuard's own enforced profile.
- [x] 3.2 Replace SkillGuard self-host's one-receipt/three-label observations with distinct current target-owned native receipts and explicit contribution ranges.
- [x] 3.3 Update the SkillGuard entrypoint, execution-depth reference, supervisor/closure guidance, README, and schema/reference indexes with the new generic protocol and claim boundary.
- [x] 3.4 Document that a green process exit, fixture-authored expectation, aggregate-only coverage, or one-point-per-object sample cannot prove deep use.
- [x] 3.5 Document object-scope exclusions, nested child universes, precommit binding, and the target-owned dynamic-floor claim boundary.

## 4. FlowGuard alignment

- [x] 4.1 Update the existing-model preflight field ownership and reuse decision for coverage universes, calibration bindings, and provider/runtime enrollment.
- [x] 4.2 Extend execution-depth and executable-contract FlowGuard models with non-empty denominator, coverage adequacy, immutable uniqueness, calibration binding, and prompt-new/runtime-old invariants plus known-bad cases.
- [x] 4.3 Update DevelopmentProcessFlow/TestMesh evidence records and adoption logs so changed model, test, schema, and generated-contract evidence is revalidated rather than reused.
- [x] 4.4 Record and close the observed `evidence_overclaimed` calibration miss and `code_boundary_mismatch` dual-root closure miss with owner-bound model/test evidence.

## 5. Tests and current verification

- [x] 5.1 Add focused positive and shallow-negative unit tests for empty dimensions, sparse time series, strata/per-object gaps, critical uncovered items, claim-scope gaps, renamed duplicate contributions, fixture/command/input drift, and prompt-new/runtime-old.
- [x] 5.2 Add class-aware/static-versus-time-varying, high-aggregate/one-shallow-object, missing/unknown/changing class, noncritical-visible, critical-shallow, no-op calibration, missing/random native artifact, referenced-model drift, separate-root, wrong-root, and fixture-stale cases.
- [x] 5.3 Update existing execution-depth, calibration, self-host, compiler, supervisor, receipt, and closure tests for the migrated contract.
- [x] 5.4 Regenerate deterministic compiled contract/check manifest and run the verification contract's focused runtime, compiler, FlowGuard, executable-contract, and project-audit commands.
- [x] 5.5 Run `openspec verify enforce-target-owned-coverage-universes --json`, fix all failures, and leave the completed change active and unarchived.
- [x] 5.6 Add and run omitted-object, low-importance exclusion, child-fingerprint drift, threshold-gaming, and compiled/native floor mismatch regressions.
