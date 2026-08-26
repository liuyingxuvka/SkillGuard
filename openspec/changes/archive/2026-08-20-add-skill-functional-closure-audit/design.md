> **Authority status:** historical-only. This design records the superseded
> functional-closure proposal and is retained for provenance. Do not implement,
> compile, validate, or derive current commands/receipts from this directory.
> The sole current authority is
> `../build-executable-skill-contract-runtime`; stale artifacts from this change
> are direct-current rewrite inputs or blockers only.

## Context

SkillGuard currently owns two modeled responsibilities: the global router selects a target skill, and the runtime-contract executor checks target-specific routes, stages, checks, evidence references, and closure blockers. Neither responsibility proves that a representative user job can travel from activation to a useful validated result. The current deep contract is therefore necessary but not sufficient: it can reject generic target-lock records while still accepting evidence that never exercises the user-visible path.

The change must remain standard-library-only, preserve native route ownership, work in source and installed layouts, keep public records portable, and remain read-only unless an explicit generator or installation command is invoked. It must also support very different skill families: deterministic CLIs, agent workflows, UI workflows, source-dependent research, document/artifact generation, and policy-oriented skills.

Existing-model preflight found no owner for functional outcome closure. The new model is a child of the runtime-contract executor, not a replacement for the global router or a parallel execution route.

## Goals / Non-Goals

**Goals:**

- Represent each required user outcome as an explicit, testable closure path.
- Separate structural depth from execution, quality, environment, and freshness evidence.
- Reject false closure caused by missing path stages, prose-only evidence, stale evidence, no failure disposition, no terminal condition, or insufficient claim-scope evidence.
- Produce precise gap codes and repair actions that can drive the remaining skill upgrades.
- Keep canonical local source, installed copy, and publication identity traceable without committing private absolute paths.
- Make SkillGuard self-host this functional audit before it is used on the portfolio.

**Non-Goals:**

- SkillGuard will not execute every target skill, decide domain truth, or replace native validators and human/domain review.
- The global router will not become a mandatory pre-execution gate for ordinary skill use.
- A single scalar score will not hide which path stage or evidence axis failed.
- Public target records will not store the user's machine-specific canonical source root.
- Existing `check-contract` and `check-depth` semantics will not be silently redefined.

## Decisions

### 1. Add a separate functional-closure record

Each target uses `.skillguard/functional-closure.json`, validated by `skillguard_functional_closure.schema.json`. The record contains:

- `outcomes`: required user jobs, success artifacts/results, quality requirements, non-goals, and path ids;
- `closure_paths`: ordered stages with roles `trigger`, `intake`, `route`, `execute`, `produce`, `validate`, optional `recover`, and `terminal`;
- `failure_modes`: detection, disposition (`recover`, `block`, `escalate`, or `scope_out`), recovery path, and evidence;
- `quality_requirements`: measurable or explicitly judgment-based acceptance floors;
- `evidence`: current proof items bound to outcomes, stages, failures, and quality requirements;
- `claim_boundary`: what the record and its evidence do not prove.

Keeping this separate avoids turning the already-large work contract into a second capability model. The work contract remains the route/stage owner and the functional record references its route, stage, check, obligation, and evidence ids.

### 2. Use evidence axes, not one maturity number

Each evidence item records:

- execution depth: `declaration`, `static`, `fixture`, `simulated_e2e`, `real_e2e`, `production_observed`;
- environment scope: `single`, `matrix`, `field`;
- quality level: `none`, `deterministic`, `human`, `domain_expert`;
- result and freshness: `pass`, `fail`, `blocked`, `skipped`, `not_run`, plus current fingerprints or a stale reason;
- assertion categories: activation, input, route, execution, output, validation, recovery, terminal, non-goal rejection, or quality.

This prevents a human prose review from masquerading as execution evidence and prevents a passing CLI fixture from masquerading as user-visible quality evidence.

### 3. Apply claim-scope floors

`check-capability` accepts `--claim-scope routine|functional|release|highest-quality`.

- `routine`: schema, bindings, and at least fixture-level evidence for required path and failure categories.
- `functional`: every required outcome has simulated end-to-end or stronger positive-path evidence plus fixture-or-stronger failure, recovery, non-goal, and terminal evidence.
- `release`: every required outcome has real end-to-end or stronger positive-path evidence; negative/recovery evidence may remain fixture-level when it exercises the same native boundary.
- `highest-quality`: release closure plus the declared human or domain-expert quality evidence.

The report exposes each unmet floor rather than collapsing it into an average.

### 4. Add three read-only command surfaces

- `check-capability`: validate one target record and return per-outcome/per-stage closure rows, evidence axes, gap codes, repair actions, skipped checks, residual risk, and claim boundary.
- `audit-capabilities`: recursively find skills, run the same checker, and report aggregate status without hiding child failures or missing records.
- `check-source-sync`: read an explicitly supplied private portfolio registry, bind canonical source/installed/repository identities, compare content and contract/closure strength, and block downgrade candidates.

`audit-installed-skills` gains optional capability fields, but keeps its
existing structural decision. It must say explicitly that deep-pass is not
functional closure.

### 5. Keep evidence production native-first

SkillGuard validates evidence references and scope; it does not invent or independently execute a second route. Deterministic tools produce native command/test receipts, UI skills produce real interaction and visual evidence, document skills produce rendered artifacts, research skills produce source/replay evidence, and agent workflows produce minimally contaminated forward-test artifacts. SkillGuard checks that those receipts cover the declared outcome path.

### 6. Keep private source roots outside public skill records

A user-level portfolio registry contains absolute `canonical_source_root` and `installed_path` values. Committed target records contain only portable ids, relative skill paths, remote repository ids, expected visibility, and release policy. Reports sanitize machine paths by default.

### 7. Self-host before portfolio use

SkillGuard receives its own functional-closure record, positive and negative fixtures, a FlowGuard child model, Behavior Commitment Ledger rows, field-lifecycle rows, ContractExhaustion cases, and Model-Test Alignment bindings. The installed SkillGuard is updated only after source tests and source self-audit pass.

### 8. Add a target-owned surface adequacy layer

Functional-closure records describe user outcomes, while the depth profile
describes declared checks.  Neither record alone proves that every public
command, route, UI control, API, configuration entry, or fault boundary was
actually accounted for.  Targets therefore may bind a separate
`.skillguard/surface-inventory.json` through `depth_profile.surface_inventory`.
The inventory carries its own observed denominator, row dispositions, intent
and owner ids, route/check/evidence bindings, adequacy checks, model-deepening
identity, and canonical fingerprint.  SkillGuard validates the shape and
freshness of that target-owned declaration but does not invent missing domain
rows or decide whether the target's intent is correct.

The inventory is a mandatory portfolio-graduation gate.  Existing
`check-depth` remains a declared-contract check and exposes a visible
surface-readiness result; graduation itself is fail-closed when the
declaration is absent, malformed, stale, or under-mapped.  SkillGuard's own
self check compares all current public dispatch commands with its route
registry and required-check declarations, so command reachability cannot
masquerade as functional coverage.

### 9. Keep consumer-release identity canonical

Consumer distributions are independent target projections.  Their
`consumer-release.json` identity uses the same compact canonical JSON bytes,
one LF newline, lowercase `sha256:` wire hashes, release-id input fields, and
manifest-hash input fields as FlowGuard's `distribution_sync` implementation.
The verifier checks raw bytes and both hash derivations, not merely an
internally self-consistent JSON object.  The consumer scanner also rejects
author-maintenance identity fields, including underscore spellings, without
adding SkillGuard runtime files, imports, receipts, or router state to the
consumer projection.

## Risks / Trade-offs

- **Targets can write shallow but valid functional records** → enforce claim-scope floors, required path roles, evidence categories, native bindings, and known-bad fixtures; keep judgment evidence explicit.
- **The record becomes too verbose** → keep reusable schema detail in references/templates and use target-specific rows only; do not duplicate full native test catalogs.
- **One evidence hierarchy does not fit every skill** → use independent execution, environment, and quality axes plus target-declared quality requirements.
- **Portfolio source paths leak publicly** → require the registry as an explicit private input and sanitize all report paths.
- **Stricter gates make most current skills fail initially** → report `missing-functional-contract` or exact closure gaps without changing existing deep-pass; migrate one repository at a time from canonical source.
- **Evidence goes stale after target edits** → bind evidence to source/result fingerprints and propagate stale status into functional/release decisions.
- **The new checker duplicates native execution** → make all target execution evidence native-owned and reject SkillGuard-owned parallel route claims.

## Historical rollout record (not a current execution plan)

The sequence below documents the superseded proposal only. It is not an active
execution plan. Current work must follow the direct-current tasks under
`build-executable-skill-contract-runtime`; no old command, record, or installed
projection is read as a second authority.

1. Add schemas, templates, checker commands, fixtures, tests, and the SkillGuard self record on the isolated local source branch.
2. Run source self-check, contract/depth checks, capability checks at all scopes, fixture suites, unit tests, FlowGuard models, and OpenSpec verification.
3. Install through a staged source-first copy that rejects downgrade, then refresh and verify the global registry/prompt.
4. Publish the SkillGuard change only after post-install and post-publication verification.
5. Create the private portfolio registry and run `audit-capabilities` across the remaining active skills.
6. Add target-specific closure records and native evidence while implementing each functional repair; never copy installed records back as source truth.

Rollback keeps the existing `check-contract`/`check-depth` commands untouched, removes only the new command dispatch and optional capability fields, and restores the previously installed SkillGuard directory from the staged backup.

## Open Questions

None block implementation. Profile-specific evidence requirements will be expressed by each target's quality requirements and native bindings rather than hard-coded repository names in SkillGuard.
