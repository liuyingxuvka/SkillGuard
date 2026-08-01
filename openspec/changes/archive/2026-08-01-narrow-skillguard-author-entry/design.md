## Context

See `proposal.md` for motivation. SkillGuard already has a current author/consumer separation, immutable evidence ownership, single-flight validation, clean installation transactions, global private registry, and a public route registry. The change contracts prompt loading and replaces keyword-scored admission without creating a second router.

## Goals / Non-Goals

**Goals:**

- Make author maintenance enter through a narrow, exact boundary.
- Make the existing route registry sufficiently complete to generate every compact route projection.
- Preserve maximum on-demand depth for supervision, diagnostics, TestMesh, Portfolio, installation, release, and self-host work.
- Keep validated-template-pack semantics target-owned while moving their long prompt text behind a conditional reference.
- Reduce the global managed block without weakening direct-current, no-fallback, or consumer-independence rules.

**Non-Goals:**

- Governing ordinary consumer runtime or official OpenSpec.
- Creating a universal Guard router, an AI understanding scale, a migration reader, or shared cross-unit evidence.
- Changing target-owned completion/depth criteria or interpreting target results.
- Treating prompt-shape validation as proof of target-domain behavior.

## Decisions

### Extend the existing registry instead of adding a new routing layer

`ROUTE_TASK_ROUTE_REGISTRY` remains the sole semantic authority. Each current row receives a current applicability schema: positive predicate clauses, forbidden clauses, required input fields, mutation class, first command, next reference, and claim boundary. A generator emits `references/skillguard-route-index.json` from its public projection.

Alternative considered: a separate prompt-only registry. Rejected because it would drift from command dispatch and produce two route authorities.

### Separate fact extraction from applicability evaluation

AI may convert a request into typed facts and preserve their source positions. The program evaluates declared route predicates. An explicit route id still requires compatibility checks. Keyword lists can remain only as non-authoritative extraction hints or be removed from current public decisions; score cannot break ties or license a route.

Alternative considered: improve weighting. Rejected because weighting cannot make ambiguous semantics exact.

### Prompt projections load by route

The public entry becomes a shell with the author gate and load algorithm. Existing detailed references remain the deep protocol owners. A generated load graph maps route ids to mandatory and conditional references. Fixtures assert both required inclusion and unrelated exclusion, plus a prompt budget with headroom.

### Validated-template-pack text moves to target reference

`template_prompts.py` emits the full current target-owned selection, instance, validation, installation, and claim-boundary guidance into `references/validated-template-pack.md` for applicable targets. It emits only a concise trigger and relative link in target `SKILL.md`. Selection still begins from the target-native route receipt; SkillGuard never selects a domain template.

Alternative considered: keep the complete lifecycle in every target entry. Rejected because it taxes unrelated requests and repeats target catalog details.

### Global prompt contains authority pointers, not catalogs

The global template keeps only the author-only trigger, explicit-root/no-scan rule, direct-current validation ownership, registry hash/path, compact route selection, consumer independence, and bounded claim. It drops the repeated current route index and validated-template lifecycle sections; those are read from the selected source when actually maintaining it.

### Self-host and model authority close after freeze

FlowGuard models cover route admission, prompt/load projections, template prompt generation, and global registry projection. The SkillGuard contract maps every changed component to exact checks. Affected checks run during development; one full supervised validation runs only after source, toolchain, and impact plan freeze.

## Risks / Trade-offs

- [Typed facts omit a discriminator] -> Exact-zero/many result exposes the missing fact; no score fallback exists.
- [Thin prompt omits a hard gate] -> Mandatory shared gates and route references are asserted before budget checks.
- [Generated route index differs from runtime] -> The registry fingerprint is embedded and parity is checked during self-check and compile.
- [Template prompt move produces a shallow target] -> Applicable targets must contain the complete generated reference and their native validator identities; missing reference blocks installation.
- [Global block becomes too vague] -> It retains the author boundary, explicit-root requirement, registry identity, and selected-source instruction, all covered by currentness tests.
- [Concurrent unit validation conflicts] -> Final full validation remains one frozen owner per unit; consumer activations remain serialized.

## Migration Plan

1. Add current fields to every route registry row and direct-replace score-based decision logic with exact predicates.
2. Generate route-index/load-graph projections and rewrite both SkillGuard entries and the global prompt template.
3. Update validated-template target generation and regenerate applicable fixtures/projections.
4. Update FlowGuard models, target-owned fixtures, self-host SkillGuard contracts, and patch version `0.7.2`.
5. Run affected checks, freeze, then run one full self-host validation.
6. Install the author runtime and consumer/global projections transactionally, refresh the private registry from explicit author roots, and verify currentness.
7. Commit, push, tag `v0.7.2`, create the GitHub Release, and verify exact identities.

Rollback restores the previous source/install/global block and model-authority identities. No compatibility reader or dual registry is retained.
