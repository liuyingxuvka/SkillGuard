## Why

> Superseded on 2026-07-10 by `build-executable-skill-contract-runtime`. This earlier change remains as design history only and MUST NOT be implemented in parallel. Its post-hoc `functional-closure.json` approach did not satisfy the requirement that every real task claim and execute a FlowGuard-compiled contract.

SkillGuard can currently prove that a skill has a target-specific deep contract, but it still cannot prove that the skill can deliver its promised user outcome from trigger through execution, validation, recovery, and final handoff. This gap allowed structurally deep skills to look healthy even when their public commands, end-to-end route, semantic correctness, or user-visible result was incomplete.

## What Changes

- Add an explicit functional-closure contract for each maintained skill: promised outcomes, representative user jobs, route chains, required inputs, produced artifacts, quality floors, failure/recovery paths, stop conditions, and non-goals.
- Add a capability-evidence ladder that distinguishes prose, static structure, fixture, simulated end-to-end, real end-to-end, cross-environment, and human-quality evidence.
- Add deterministic SkillGuard commands that validate functional-closure declarations, bind them to native routes/checks and current evidence, and report exact closure gaps and next actions.
- Make `audit-installed-skills` and portfolio reports expose structural depth and functional closure as separate dimensions; `deep-pass` must never be presented as proof of functional completion.
- Add source/installed/GitHub provenance and non-downgrade checks so functional repairs originate in the canonical local source and cannot be replaced by a shallower copy.
- Add positive, negative, stale, false-closure, missing-recovery, missing-quality, and provenance-drift fixtures plus current self-audit evidence.
- Preserve existing native route owners and the existing `check-contract`/`check-depth` interface. Functional closure is an additional hard gate for functional, done, release, or capability-completeness claims.

## Capabilities

### New Capabilities

- `skill-functional-closure-contract`: Declare the complete user-outcome path, including input, execution, output, validation, recovery, stop, and non-goal boundaries.
- `skill-capability-evidence`: Classify and bind current evidence to each functional obligation without treating prose or structural fields as runtime proof.
- `skill-functional-closure-audit`: Validate one skill or a portfolio, produce closure status and gap codes, and derive actionable repair requirements.
- `skill-source-provenance`: Bind canonical local source, installed copy, repository, and release identities while rejecting source-to-installed downgrade paths.

### Modified Capabilities

None. The repository has no existing OpenSpec capability specifications; current SkillGuard commands remain compatible and receive additional result fields rather than replacement semantics.

## Impact

- SkillGuard checker engine and CLI command surface.
- Work-contract schema, templates, check manifests, suite/report schemas, fixtures, and self-contract.
- Installed-skill portfolio audit output, global-router freshness triggers, README, agent entrypoint, and version metadata.
- New FlowGuard capability-closure child model plus behavior, field, contract-exhaustion, and model-test alignment evidence.
- Downstream maintained skill repositories will need target-specific functional-closure records before SkillGuard can support broad capability or release claims.
