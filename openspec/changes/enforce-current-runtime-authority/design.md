## Context

The repository has already implemented exact content components, owner receipts, plan-only TestMesh selection, and read-only downstream consumption. One old lifecycle boundary still contradicts that design: former authority states, retirement receipts, and conversion tooling remain beside the current path.

That makes retired history and conversion behavior look like upstream functional inputs. They are not. The current trio alone answers what is executable now. Keeping any live conversion or renewal surface creates broad invalidation and an unnecessary alternate route.

## Goals / Non-Goals

**Goals:**

- Expose one daily `current` authority and one `blocked` failure state.
- Make the complete current trio plus exact residual scan sufficient for daily authority.
- Remove live retirement evidence and conversion tooling from maintained and installed surfaces; version-control history remains sufficient for historical inspection.
- Remove legacy command handlers and old success fixtures from daily execution.
- Make all current consumers share the same decision and fail closed.
- Replace affected maintained sources directly with the current shape through the ordinary current generator/compiler path.
- Remove refresh/upgrade paths that derive current authority from former or stale records.
- Keep runtime evidence outputs outside functional input identity and maintained fixture source.
- Make direct current replacement the default for every covered skill while leaving explicitly required ordinary-software historical readers to a bounded FlowGuard model.
- Install the affected SkillGuard suite members, then use one frozen parent receipt for final verification.

**Non-Goals:**

- Renaming every stable current schema whose historical identifier ends in `.v1`.
- Treating removal of old authority as target-domain test proof.
- Adding a second router, test runner, ledger, receipt family, or compatibility adapter.
- Automatically converting an old target into passing current authority.

## Decisions

### 1. One current daily authority

The current authority consists of exactly:

- `.skillguard/contract-source.json`;
- `.skillguard/compiled-contract.json`;
- `.skillguard/check-manifest.json`.

The resolver validates the trio, canonical hashes, skill/model binding, content-impact plan, and former-runtime residual absence. It returns `current` only when all checks pass; every other shape returns `blocked`. There is no daily V1 or migration success branch.

### 2. No live retirement or migration surface

Eligibility, completion, prior-receipt-chain files, their schemas and validators, and conversion or renewal commands are removed from maintained and installed surfaces. Old shapes remain only in exact rejection fixtures. A current implementation or contract change therefore has no retirement record to renew.

An old target stays `blocked` until normal maintenance rewrites its maintained source directly to the current shape, regenerates the current trio, and removes every named former surface. No runtime command reads an old shape to manufacture a current one.

### 3. Old lifecycle fields leave the current contract

`v1_runtime_authority` and `legacy_v1_authority` are rejected by current source/compiled-contract validation. No maintained runtime tool parses them as input. Direct current maintenance writes a source that never contains either field.

### 4. Old commands have no daily dispatcher route

The former `compile-contract`, `select-route`, `start-run`, `advance-run`, `check-run`, and `close-run` handlers, route entries, generated-target instructions, and positive fixtures are removed from the public daily command registry. Current V2-named implementation modules may keep stable file names, but the active user path is the current compiler/supervisor/receipt flow.

Unknown old commands fail before execution. Old JSON shapes remain negative fixtures that prove rejection; they are never executable conversion input.

### 5. Residuals fail closed without making history fresh

A current target blocks with `former_runtime_residual` if any of these former authority surfaces reappear:

- `.skillguard/work-contract.json`;
- `.skillguard/check_manifest.json`;
- flat `.skillguard/runs/*.json` records whose schema is `skillguard.run_record.v1`.

Current run directories and immutable receipts are preserved. Other stable protocol files are not legacy merely because their schema id ends in `.v1`.

### 6. Consumers project current authority only

Compiler checks, project adoption, provenance, staged installation, active parity, global discovery, managed prompt projection, Portfolio, and installed smoke all consume the same `current` decision. None may inspect an old pair to recover success.

Global discovery may still list a skill whose authority is missing or invalid, but its route status is blocked and it has no executable default route until directly maintained in the current shape.

### 7. Installation and validation remain component-scoped

Negative fixtures are source-only and never installed; changing them cannot admit full validation. The installer consumes `projection:installation`, parity replays that projection, and smoke owners come only from exact changed-component edges.

Final validation remains one frozen full TestMesh parent under one owner. Both this change and `compose-validation-evidence` consume projections of that same parent receipt; neither verification contract reruns the parent.

### 8. Maintenance writes current inputs directly

`refresh-maintenance` and project-adoption upgrade modes are not current maintenance routes. Project adoption requires a complete explicit current contract and manifest input, then performs one direct current write and current validation. It never reads a former manifest, stale report, or old lifecycle record to derive the new authority.

### 9. Functional identity excludes execution output

Each owner execution key binds the normalized check declaration and its exact functional source component. Receipts, reports, logs, caches, timestamps, generated status, and content-addressed result sidecars are downstream evidence. They are stored outside maintained fixture source and excluded from source identity, so producing or reviewing evidence cannot invalidate the check that produced it.

### 10. Skill and ordinary-software compatibility are different decisions

For maintained skills, one current authority is mandatory: direct replacement plus former-shape rejection fixtures. No fallback reader, migration command, converter, alias, renewal path, or parallel success authority is admitted.

Ordinary software may need to read historical documents, stored data, protocols, or public interfaces. That branch is admitted only when an explicit requirement names the historical input, bounded reader owner, accepted/rejected shapes, output semantics, and claim or sunset boundary. DevelopmentProcessFlow owns this admission decision. The exception does not create a fallback path for SkillGuard or any covered skill.

### 11. SkillGuard governs native tests without cloning them

The target skill remains the owner of its existing native test implementation. The task-level verification contract or TestMesh normalizes each exact command, functional input projection, evidence domain, and obligation set into one primary execution owner. SkillGuard may compile that ownership, execute the declared native command once when its receipt is missing, and verify or aggregate the immutable receipt. It does not create an equivalent checker, second scheduler, wrapper command, or consumer-owned copy of the test.

Consumers carry only the owner receipt reference and their own projection or aggregation declaration. A consumer that carries command, selector, toolchain, dependency, or execution-callback authority is not a consumer and is rejected before execution.

## Risks / Trade-offs

- **Non-current skills remain blocked.** This is intentional: they cannot be mistaken for current execution authority.
- **Retirement history is no longer a live product surface.** Repository history may be inspected separately, but it cannot make current functional evidence stale.
- **Removing former commands may break old automation.** That automation must be rewritten to the current command rather than preserved through a compatibility route.
- **A broad delete could remove current protocols.** Removal is limited to named former runtime surfaces and legacy dispatcher/template paths, with negative fixtures kept separately.

## Replacement Plan

1. Update this OpenSpec change and extend the existing validation-composition and DevelopmentProcessFlow owners with direct current-authority and compatibility-admission rules.
2. Make source/compiled schemas and the compiler reject old lifecycle fields.
3. Simplify the runtime resolver to current-trio validation plus residual rejection; delete historical receipt validators, schemas, and conversion/renewal commands.
4. Remove legacy daily CLI handlers/routes/templates, maintenance refresh, and project-upgrade paths; convert positive former-path tests into current rejection tests.
5. Move all consumers to the current decision and exact content-impact projections; remove runtime outputs from maintained source and functional identity.
6. Remove live former runtime-authority and retirement-history files from SkillGuard and `skillguard-global-router`; keep only rejection fixtures and repository history.
7. Regenerate both current contract trios and run only affected model/unit/schema regressions.
8. Prove native test ownership is singular and that consumers contain no owner command or second scheduler.
9. Transactionally install the suite, refresh the router/prompt once, run the real FlowGuard→SkillGuard→OpenSpec receipt pilot, freeze, and execute one final parent TestMesh.

Rollback remains the existing atomic installation rollback. Source maintenance stays blocked until the complete current trio is valid; there is no conversion rollback route or daily legacy execution route.
