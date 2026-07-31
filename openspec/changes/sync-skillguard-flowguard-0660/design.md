## Context

See `proposal.md` for motivation. SkillGuard records FlowGuard through four distinct mechanisms: the root project-adoption record, immutable GitHub Actions pins, policy tests that guard those pins, and generated author-side contract/model authority. The generated contract is part of the installed maintainer projection, so updating only CI would create a same-version byte drift.

## Goals / Non-Goals

**Goals:**

- Bind all current maintenance surfaces to FlowGuard `v0.66.0`.
- Preserve source, installed projection, Git tag, GitHub Release, model evidence, and CI results as separate identities.
- Publish changed installed bytes as SkillGuard `v0.5.1`.

**Non-Goals:**

- Change SkillGuard consumer behavior or assurance-diagnostics semantics.
- Move, overwrite, or reinterpret the existing `v0.5.0` tag.
- Add compatibility readers, dependency fallbacks, floating provider pins, or background validation owners.

## Decisions

1. **Use an immutable FlowGuard tag in all three branch-CI jobs.** A floating branch would make validation irreproducible. Keeping three explicit pins also makes each job's toolchain visible.
2. **Keep a policy test for the exact pin and long-path ordering.** This turns future provider drift into a local/CI failure rather than a silent environment difference.
3. **Regenerate SkillGuard authority after the workflow and policy test change.** The compiler owns `compiled-contract.json` and `check-manifest.json`; model authority is refreshed only after the exact three-model regression passes.
4. **Install transactionally before final self-host aggregation.** Installation, router, model, test, Git, and publication evidence remain independent and are reconciled only at closure.
5. **Use `v0.5.1` instead of moving `v0.5.0`.** The existing tag and release remain immutable historical authority.

## Risks / Trade-offs

- **[Risk] A provider-only maintenance change triggers a broad validation chain.** → Use frozen affected-owner planning and exact receipt reuse, while still running the required final release gate.
- **[Risk] Generated contract refresh changes installed bytes.** → Bump the patch version and transactionally reinstall rather than retaining the same version label.
- **[Risk] Router currentness drifts after generated authority changes.** → Rebuild the private router from the same explicit 39 roots and verify ExperimentGuard is present while ConstraintGuard remains absent.

## Migration Plan

1. Align project records, CI pins, and policy tests to FlowGuard `v0.66.0`.
2. Run affected tests and full three-model regression; refresh generated contract and model authority.
3. Bump SkillGuard to `v0.5.1`, regenerate authority again if version-bound inputs change, and run frozen SkillGuard supervision.
4. Transactionally install the exact stable projection and refresh the explicit global router.
5. Push the stable commit, require branch CI success, create an annotated `v0.5.1` tag, require tag identity success, and publish a zero-asset GitHub Release.
6. Verify remote peeled tag, release target, installation parity, router currentness, and OpenSpec completion.
