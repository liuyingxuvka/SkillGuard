## 1. CLI Binding

- [x] 1.1 Implement one shared canonical repository/member binding resolver for `check-contract` and `check-skill`.
- [x] 1.2 Add `--repository-root`, remove the `check-contract --target-root` success surface, and make every mismatch block without retry.
- [x] 1.3 Compile and resolve references from the canonical repository root while preserving standalone `--target .`.

## 2. Schema And Tests

- [x] 2.1 Add the privacy-safe `skillguard.external_target_binding.v1` schema and emit it in both command reports.
- [x] 2.2 Add focused explicit nested, standalone dot, escape, removed-option, schema, no-absolute-path, and canonical-reference-with-member-copy regressions.

## 3. FlowGuard And Documentation

- [x] 3.1 Extend the existing executable-contract model and tests with explicit repository/member binding and no-fallback cases.
- [x] 3.2 Add the observed external-target model-miss record and FieldLifecycleMesh rows with old `target_root` disposition blocked.
- [x] 3.3 Update English/Chinese README command examples and the practical workflow reference.

## 4. Focused Verification

- [x] 4.1 Run `check.external-binding.cli` and fix every failure.
- [x] 4.2 Run `check.external-binding.model` and the affected executable-contract model tests.
- [x] 4.3 Regenerate/check the current SkillGuard contract trio and run affected SkillGuard contract/static checks only.
- [x] 4.4 Run `check.external-binding.openspec`, privacy, and scoped diff checks; keep installation, router refresh, final full validation, release, and archive not run. The repository-wide diff check retains an unrelated pre-existing `AGENTS.md` end-of-file whitespace finding.
