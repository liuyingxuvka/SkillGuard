## Context

SkillGuard already has one current source/compiled/manifest authority, exact target-declared check supervision, immutable receipts, affected-only invalidation, target installation projection, self-hosting, and a generated global router prompt. The remaining repeat-error surface is earlier in the lifecycle: skill creation and maintenance often begins from a fixed minimal scaffold or copied contract blocks, while each Guard family has different domain templates, builders, oracles, and validators.

The design must preserve two planes:

- the target Guard owns route meaning, applicability predicates, domain fields, builders, validators, fixtures, and safe claims;
- SkillGuard owns target-neutral template identity, candidate accounting, composition integrity, current-authority compilation, receipt freshness, installation projection, and closure consumption.

`build-executable-skill-contract-runtime` is the prerequisite runtime owner. A separate registered worktree currently changes compiler, schema, runner, supervisor, receipts, TestMesh, templates, and self-host surfaces. This change may define the dependent contract and add isolated files, but integration into those shared files waits for one explicit owner handoff.

OpenSpec remains an external specification provider. Its source, installation, generated skills, and Git history are not implementation targets.

## Goals / Non-Goals

**Goals:**

- Make reusable structure the default entry for non-trivial skill maintenance without turning templates into semantic proof.
- Make template selection deterministic, explainable, hash-bound, stale-aware, and fail-closed for ambiguity or conflict.
- Let target-owned template packs compose from small fragments only when ownership and compatibility are explicit.
- Reuse the existing SkillGuard authority trio and declared-check workflow instead of introducing a parallel template authority or executor.
- Centralize portable command launch behavior and descendant-cleanup evidence.
- Generate target and global prompt guidance from canonical fragments.
- Support direct-current replacement and affected-only revalidation for installed skills.

**Non-Goals:**

- SkillGuard will not infer Guard-family semantics from skill names, route labels, or check identifiers.
- Templates will not choose a task's physical equations, logical warrants, evidence roles, causal edges, world-model guards, state invariants, or acceptance criteria.
- Template instantiation will not count as native validation or completion evidence.
- This change will not add compatibility readers, aliases, dual manifests, fallback contracts, or a fourth runtime authority.
- This change will not modify or install OpenSpec.

## Decisions

### 1. Federated catalogs with a target-neutral supervision envelope

Each target skill publishes its catalog beside its native route/check system. SkillGuard consumes a bounded catalog projection and never maintains a central copy of domain templates.

Every manifest records a stable template id and revision, canonical digest, family and route ids, hard applicability predicates, forbidden conditions, required inputs, provided and required fragments, field ownership, compatibility/conflict declarations, parameter schema, generated artifacts, native builder id, native validator ids, fixtures, and claim boundary.

This is preferred over a single global template library because global ownership would duplicate family semantics. It is preferred over prose-only instructions because prose cannot prove candidate equality, version identity, or composition safety.

### 2. Selection is a finite decision, not lexical ranking

The target-native router first chooses the family and route. The target catalog then filters candidates by hard predicates and forbidden conditions. Lexical scores may order diagnostics but never establish applicability.

- Zero domain candidates: select one target-declared validated base template and record exact no-match evidence, or block when the target forbids a generic base.
- One candidate: render a read-only preview, run applicability checks, then instantiate.
- Several candidates: compose only when every dependency is present, all pairs are declared compatible, and every owned field has one owner. A strict target-authored dominance rule may select one candidate. Otherwise block with `ambiguous_template_selection`.

No result may be chosen by template-id order or silent blank-page fallback.

### 3. Selection and instance receipts are separate

The selection receipt binds request fingerprint, native route decision, catalog identity, complete candidate set, rejected candidates and reasons, selected template/fragment identities, composition order, field-owner map, applicability result, and decision status.

The instance receipt binds the selection receipt, exact parameters, generated artifact identities, unresolved-placeholder scan, native builder identity, target-native validator receipts, and instance fingerprint. A valid instance receipt is required by closure but cannot replace the target's declared checks.

### 4. Reusable fragments expand through the existing compiler

Contract source may reference reviewed SkillGuard-owned supervision fragments. The current compiler resolves those references and emits their full deterministic content into the existing compiled contract and exact check manifest. The fragment registry and its digests are compiler inputs, not a fourth runtime authority.

Target route ids, native owner, checks, dependencies, evidence domains, artifacts, and claim boundary remain explicit target declarations. Expansion that adds or removes a native check, changes target semantics, leaves placeholders, or creates overlapping field ownership fails closed.

### 5. Prompt projection is generated

The managed global prompt states only the universal lifecycle: target route first, target catalog resolution, zero/one/many behavior, preview, native validation, receipts, and harvest review. The global router selects a skill but never a domain template.

Each target `SKILL.md` receives generated headings for catalog routing, selection inputs, applicability/forbidden conditions, composition, preview/instantiation, native validation, no-match/harvest, and claim boundary. Target-specific content is supplied by the target repository.

### 6. Portable launch is a structured runtime plan

The check runner resolves a canonical launch plan before execution. The plan records requested command, resolved executable/shim, interpreter when required, argv, working directory, environment fingerprint, and platform. Windows command shims use their required interpreter; directly executable commands run directly. The resolved plan, not only the requested token, contributes to toolchain identity.

Timeout or cancellation must terminate the full descendant tree. A cleanup-unconfirmed result is terminal failure evidence and is never reusable. Contracts do not embed platform-specific shell strings.

### 7. Freshness follows exact component edges

Catalog, manifest, template content, fragment, builder, validator, prompt projection, launch resolver, and contract compiler are distinct functional components. A changed component invalidates only consuming owners/projections. Reports, receipts, task checkmarks, progress, timestamps, and installation bookkeeping remain outputs and cannot retrigger their producer.

### 8. Direct-current rollout

There is no normal dual runtime. Work is rehearsed in isolated previews and fixtures; when accepted, each maintained target is directly rewritten to the current trio, installed through its target installation transaction, natively revalidated, and refreshed in the global router only when its route projection changes.

## Risks / Trade-offs

- **[Risk] A template becomes a second domain router** → Require a prior target-native route and verifier-owned applicability receipt; SkillGuard rejects family inference.
- **[Risk] Many small fragments become hard to reason about** → Require explicit dependencies, one field owner, canonical order, conflict fixtures, and a materialized preview.
- **[Risk] A base template hides a real no-match** → Bind no-match evidence and harvest disposition; targets may forbid generic bases for high-risk routes.
- **[Risk] Template success is mistaken for task success** → Keep selection, instance, native checks, and enforced closure as distinct receipts.
- **[Risk] Shared runtime edits collide with active peer work** → Make `build-executable-skill-contract-runtime` an explicit prerequisite and use one later integration owner.
- **[Risk] Platform launch behavior drifts from toolchain identity** → Hash the resolved launch plan and include platform fixtures plus descendant cleanup evidence.
- **[Risk] Updating prompts invalidates every target** → Compile exact prompt components and revalidate only targets that consume changed projections.

## Migration Plan

1. Finish or explicitly hand off the active executable-runtime worktree; freeze its current source, toolchain, and declared-check identities.
2. Add template manifest, selection receipt, and instance receipt schemas plus positive/negative/ambiguity/stale/platform fixtures as isolated components.
3. Add target-neutral selection/composition validation and contract-source fragment resolution without changing target semantics.
4. Extend plan/generate preview behavior and canonical prompt projection.
5. Add portable launch resolution and focused platform/process cleanup tests under one runner owner.
6. Pilot direct-current replacement on one Guard skill with a current native catalog and validator.
7. Mark exact portfolio impact, install affected targets through staged transactions, run target-native checks, and refresh the global router only for changed projections.
8. Freeze one final owner plan and run one full self-host/portfolio integration snapshot. No background resume, scheduled task, or unattended retry may own that full gate.

Rollback is transaction-based: before activation, discard the isolated stage; after activation, use the current installation transaction rollback. Source rollback never uses destructive Git commands and must preserve peer writes. A failed new runtime does not reactivate a former authority.

## Open Questions

- Which Guard family will be the first fully installed pilot after its current native work is frozen?
- Which existing contract-source repetitions qualify as SkillGuard-owned fragments after compiler component analysis, rather than merely looking similar?

## Resolved Integration Baseline

- The 142-path peer runtime was preserved as commit `ea19d73ad6cb0e9c58916b22d53277e52e5ef50f` on `codex/validated-template-pack-integration`; the official OpenSpec planning change was then merged as `6128d84bacf7615639c2c66c6d820cebdcdb1b21`. This branch is the sole shared-runtime integration baseline for the template-pack program.
