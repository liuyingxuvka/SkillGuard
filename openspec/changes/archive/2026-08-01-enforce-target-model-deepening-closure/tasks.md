## 1. Contract source and current schema

- [x] 1.1 Reopen the previously overclaimed change and specify the missing explicit receipt boundary.
- [x] 1.2 Add `model_deepening_check_id` to the current depth-profile schema and compiler validation.
- [x] 1.3 Add a typed `model_deepening_result` to the current target-execution receipt schema.
- [x] 1.4 Update affected target contract sources to designate a real target-owned check.
- [x] 1.5 Update maintainer guidance to reject self-report, generic-check substitution, stale evidence, and addressable-gap closure.

## 2. Fixtures and validation

- [x] 2.1 Add compiler tests for missing, unknown, and non-native designated check ids.
- [x] 2.2 Add runtime tests for current pass, not-run, failed, skipped, stale, wrong-request, wrong-owner, and self-report-only cases.
- [x] 2.3 Replace the abstract-Boolean-only native check with the real runtime test owner.
- [x] 2.4 Run contract compiler, execution-depth, assurance diagnostics, model alignment, and consumer-distribution tests.

## 3. Local installation and closure

- [x] 3.1 Compile the authoritative contract and check-manifest after source freeze.
- [x] 3.2 Run one current target-owned producer execution and consume its immutable terminal receipt.
- [x] 3.3 Stage and verify the clean target-owned consumer projection.
- [x] 3.4 Activate local SkillGuard installation transactionally and check currentness.
- [x] 3.5 Run one frozen author-side final validation and verify closure identity.
- [x] 3.6 Update version/changelog, commit, tag, push, and create the GitHub release after all gates pass.
