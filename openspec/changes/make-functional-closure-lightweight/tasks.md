## 1. Contract and identity

- [x] 1.1 Add the functional-closure spec and trace each requirement to one native owner.
- [x] 1.2 Define the functional component set and remove timeout/output/report/pointer metadata from functional leaf identity.
- [x] 1.3 Keep installation/release/provenance identities separate and add regression coverage for pointer-only and timeout-only changes.

## 2. Finite receipt and closure execution

- [x] 2.1 Implement one invocation-local immutable ReceiptIndex and pass it through freshness evaluation.
- [x] 2.2 Make exact-current check hits read-only and prevent new attempt/receipt/run-directory writes.
- [x] 2.3 Allow zero-execution terminal parent closure after verifying every real leaf and reject foreign/tampered/aggregate-only evidence.
- [x] 2.4 Perform one post-producer functional source check and one child-identity reconciliation; never auto-retry drift or timeout.
- [x] 2.5 Add focused mixed reused/executed, all-reused, stale, timeout, and source-drift tests.

## 3. Owner and profile reduction

- [x] 3.1 Merge only exact duplicate native owners while retaining distinct semantic check ids and required projections.
- [x] 3.2 Make fast/focused/full owner sets distinct and remove unconditional installation/global-router gates from local functional closure.
- [x] 3.3 Gate Agent Workflow Rehearsal on explicit complexity/risk triggers and add ordinary-small-work negative coverage.
- [x] 3.4 Keep seven UI content-visibility child mappings and their negative mutation gates intact.

## 4. Documentation, projections, and temporary evidence

- [x] 4.1 Update router and workflow documentation with the complexity gate and local-versus-release boundary.
- [x] 4.2 Refresh generated contract/check manifests once after source freeze; consumer projections contain no SkillGuard receipt authority.
- [x] 4.3 Verify controlled temporary work roots are retained during work, excluded from authority/publication, and cleaned only by explicit bounded operation.

## 5. Verification and closure

- [x] 5.1 Run targeted native tests for identity, ReceiptIndex, reuse, closure, profile, and routing changes.
- [x] 5.2 Run OpenSpec validation and generated-contract `--check` without starting a producer.
- [x] 5.3 Execute one bounded functional closure for the frozen unit and one zero-execution terminal readback; record counts and evidence paths.
- [x] 5.4 Mark this change complete only after all required leaves are current and no producer is running.
