## Context

Current contract compilation already understands a canonical repository root and a repository-relative `member_root_path`. The public `check-contract` command discards that distinction for ordinary external targets by recompiling from the member directory, and `check-skill` resolves project references against SkillGuard's own repository. The repair extends the existing executable-contract owner rather than adding another validation route.

## Goals / Non-Goals

**Goals:**

- Bind both commands to one canonical repository root and one exact member target.
- Keep every repository-relative contract, model, check, and reference path anchored to the canonical root.
- Emit a portable binding projection with no absolute path disclosure and `fallback_used=false`.
- Preserve standalone `--target .` where repository and member roots are identical.
- Fail visibly when the root is missing, the member escapes it, or the removed `--target-root` spelling is used.

**Non-Goals:**

- Change portfolio replacement, frozen validation execution, target-domain semantics, installation, router state, publication, or release.
- Add compatibility aliases, root inference for external targets, or retry against another directory.

## Decisions

### One shared binding resolver

Both commands use one resolver that returns the canonical root, exact member root, portable `member_root_path`, and binding mode. An explicit `--repository-root` resolves `--target` only inside that root. Without it, the existing SkillGuard self target remains deterministic and `--target .` binds the current directory as a standalone repository/member. No failed binding triggers a second attempt.

### Direct replacement of `--target-root`

`check-contract --target-root` is removed rather than aliased. The old name described the member as if it were repository authority and caused the defect. A compatibility alias would preserve two authorities and make failures ambiguous.

### Portable schema projection

Each report carries `target_binding` conforming to `skillguard.external_target_binding.v1`. It records roles, mode, portable member path, verified containment, and absence of fallback, but never persists an absolute local path.

### Extend the existing FlowGuard owner

The portable executable-contract model gains the repository/member binding branch and known-bad cases. A model-miss record backpropagates the observed Logic Writing external-root failure. FieldLifecycleMesh accounts the new binding fields and marks the old `target_root` CLI field blocked.

## Risks / Trade-offs

- **Existing callers use `--target-root`.** → Update repository-owned examples/tests now; reject the old spelling visibly instead of silently accepting it.
- **Implicit local fixture checks could change labels.** → Preserve their existing report root while making the contract compiler consume only the resolved canonical binding.
- **Public reports could leak machine paths.** → Project only role tokens and repository-relative `member_root_path` through a strict schema.
- **Parallel repository edits may overlap.** → Patch narrow current sections, reread before each edit, and run affected tests only.

## Migration Plan

Repository-owned external callers replace `--target-root ROOT --target MEMBER` with `--repository-root ROOT --target MEMBER`. Standalone callers may continue `--target .`. Rollback restores the prior parser and binding resolver together; no dual-reader period exists.

## Open Questions

None for this scoped repair.
