## 1. Diagnose And Align Provider Identity

- [x] 1.1 Reproduce the post-release CI failure and prove the 0.66.0 project record versus 0.65.1 CI pin mismatch.
- [x] 1.2 Pin all branch-CI jobs and their policy test to immutable FlowGuard `v0.66.0`.

## 2. Refresh Governed Authority

- [x] 2.1 Run affected workflow/compiler/installation/diagnostics tests, the three-model full regression, and activate the current model snapshot.
- [x] 2.2 Bump SkillGuard to `v0.5.1`, update release documentation, and regenerate deterministic contract/manifest authority.
- [ ] 2.3 Transactionally install the stable `v0.5.1` projection and refresh the exact 39-root private router with ExperimentGuard present and ConstraintGuard absent.

## 3. Validate And Publish

- [ ] 3.1 Freeze and complete one final SkillGuard self-host validation, then require exact branch CI success.
- [ ] 3.2 Create an annotated `v0.5.1` tag, require tag identity success, and publish a zero-asset GitHub Release at the exact commit.
- [ ] 3.3 Verify OpenSpec, FlowGuard project/model authority, installation, router, Git, tag, and publication closure without moving `v0.5.0`.
