## Why

SkillGuard currently supervises target-declared routes, checks, receipts, freshness, and closure, but repeated skill creation and maintenance still begins from a fixed minimal scaffold or hand-copied contract blocks. Guard-family skills need a reusable, validated template-pack lifecycle that reduces repeat errors without transferring domain semantics from the target skill to SkillGuard.

## What Changes

- Add a target-neutral template-pack protocol covering manifest identity, applicability evidence, composition, field ownership, conflicts, parameters, generated artifacts, native builders, native validators, and claim boundaries.
- Require deterministic zero/one/many-candidate handling: an approved target-owned base template or explicit no-match disposition for zero candidates, automatic preview for one candidate, and composition-or-block behavior for multiple candidates.
- Add immutable template-selection and template-instance receipts bound to request, candidate set, rejected candidates, template digests, parameters, generated artifacts, and target-native validation.
- Extend SkillGuard source compilation so reusable supervision fragments can be referenced once in contract source and deterministically expanded into the existing compiled contract and exact check manifest; no fourth authority is introduced.
- Extend skill planning and generation so the target skill publishes its own template catalog and native applicability/validation bindings, while SkillGuard renders a read-only preview and rejects ambiguity, unresolved placeholders, stale templates, or lost native checks.
- Add a centralized portable command launch plan for declared checks so platform shims and process-tree cleanup are runtime concerns rather than copied contract text.
- Generate the managed global prompt and target-skill template-routing sections from one canonical prompt fragment instead of manually copying the rules across skills.
- Keep OpenSpec as an external specification provider. This change does not modify, fork, wrap, or install OpenSpec.
- Depend on completion and handoff of `build-executable-skill-contract-runtime`; overlapping compiler, schema, runner, supervisor, and TestMesh files must have one integration owner.

## Capabilities

### New Capabilities

- `validated-template-pack-supervision`: Target-neutral manifest, applicability, selection, composition, identity, receipt, freshness, and closure supervision for target-owned templates.
- `template-profile-compilation`: Reusable contract-source fragments and deterministic expansion into the sole current compiled-contract/check-manifest authority.
- `template-first-skill-maintenance`: Plan, preview, generate, direct-current replacement, prompt projection, and harvest-review behavior for maintained skills.
- `portable-declared-check-launch`: Canonical platform-aware launch planning and process-tree cleanup evidence for target-declared commands.

### Modified Capabilities

None. The repository currently has no promoted root specs; this change depends on, but does not rewrite, the active executable-runtime change.

## Impact

- Affected areas after the active runtime owner hands off: SkillGuard contract schemas/compiler, route and check runtime, check launcher, receipts, generated templates, global router prompt projection, target installation projection, fixtures, tests, and self-host evidence.
- Target Guard repositories remain the sole owners of domain template catalogs, applicability predicates, builders, validators, fixtures, and semantic claim boundaries.
- Existing installed skills require direct current replacement and affected-only revalidation after their source projections change.
- OpenSpec source, installed OpenSpec skills, package installation, and Git history are outside this change.
