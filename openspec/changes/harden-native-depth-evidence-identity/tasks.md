## 1. Correct the ownership model

- [x] 1.1 Re-run the existing-model preflight and preserve the existing compiler, check runner, receipt, closure, installation, portfolio, and TestMesh owners.
- [x] 1.2 Freeze the no-mode architecture: SkillGuard has one fixed declared-check supervision responsibility; Guard purpose/blockability remains target-owned.
- [x] 1.3 Revise the existing proposal, design, specs, verification contract, and task list instead of creating a parallel OpenSpec change.

## 2. Remove the Guard-specific SkillGuard layer

- [x] 2.1 Remove purpose-contract, protected-failure, semantic-obligation, native-finding, and universal positive/shallow-calibration fields from the current SkillGuard schemas and validators.
- [x] 2.2 Remove the corresponding runtime producers, imports, prompt requirements, self-host inputs, templates, and capability claims.
- [x] 2.3 Restore generic `request_fingerprint` and `native_observation_locator` identities.
- [x] 2.4 Reject all removed fields as retired/unknown current authority with no alias, fallback, or optional mode.

## 3. Strengthen fixed declared-check supervision

- [x] 3.1 Freeze the exact target-declared check inventory before execution.
- [x] 3.2 Require exactly one execution owner and one visible terminal disposition per required check.
- [x] 3.3 Keep failed, skipped, timeout, running, not-run, stale, duplicate, foreign, and cleanup-unconfirmed results visible.
- [x] 3.4 Preserve exact receipt reuse, affected-only freshness, branch closure, installation, TestMesh aggregation, and receipt-consumer ownership.
- [x] 3.5 Add the public immutable-plan TestMesh owner runner with strict owner/dependency validation, exact `will_execute` resolution, repeated-invocation single-flight reuse, and same-plan aggregation.
- [x] 3.6 Preserve every semantic check projection when several checks share one compiler-owned execution owner; reject omission or ambiguity before execution.

## 4. Rewrite the FlowGuard child model and field lifecycle

- [x] 4.1 Replace `.flowguard/native_depth_identity` with `.flowguard/declared_check_supervision`, using `Input x State -> Set(Output x State)` blocks.
- [x] 4.2 Replace purpose/semantic field lifecycle rows with generic request, check, receipt, locator, domain, terminal-disposition, and consumer rows.
- [x] 4.3 Add known-bads for missing check, duplicate owner, undeclared result, stale receipt, hidden skip, bypass flag, duplicate execution, and non-terminal evidence.
- [x] 4.4 Reattach the corrected child model to the existing SkillGuard parent without duplicating target-native evaluators.
- [x] 4.5 Add model-miss cases for a valid shared owner and for post-launch persistence failure with truthful process-start accounting.

## 5. Replace tests and fixtures

- [x] 5.1 Add an ordinary non-Guard fixture proving purpose, protected-failure, semantic-obligation, and positive/shallow fields are not required.
- [x] 5.2 Add a synthetic omitted-required-check case proving SkillGuard itself detects incomplete declared execution.
- [x] 5.3 Add retired-field rejection tests and remove purpose-specific runtime tests.
- [x] 5.4 Update remaining generic identity, freshness, installation, branch, and receipt tests to the corrected contract.
- [x] 5.5 Add observed and same-class frozen-runner regressions for shared-owner projection, omission rejection, and post-launch persistence failure.

## 6. Regenerate current authority and documentation

- [x] 6.1 Update `SKILL.md`, execution-depth/supervisor/self-host references, README, templates, and managed prompt text to the fixed generic responsibility.
- [x] 6.2 Regenerate `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` from the corrected source.
- [x] 6.3 Prove no source SkillGuard prompt or global router claims Guard-purpose ownership; repeat against the installed projection after activation.

## 7. Focused validation and installation

- [x] 7.1 Run compiler/schema checks, corrected FlowGuard model checks, generic-supervision tests, and retired-field tests; repair every failure.
- [x] 7.2 Run affected SkillGuard regression owners only after source/contract identity stabilizes.
- [x] 7.3 Transactionally prepare and activate the canonical SkillGuard tree, verify rollback safety and exact installed parity.
- [x] 7.4 Run only the affected frozen-runner, schema, and FlowGuard model checks for this repair; do not start another final full owner.

## 8. Final frozen verification

- [x] 8.1 Freeze repository, contract, manifest, environment, installation, and runtime fingerprints.
- [ ] 8.2 After every maintained Guard-family source, installation projection, and global-router projection is frozen, execute exactly one final full TestMesh owner in the foreground; it must produce terminal artifacts, and any interruption requires confirmed descendant cleanup before retry. The earlier parent receipt is historical because later installation/router projection changes correctly invalidated it.
- [ ] 8.3 Replay the resulting current immutable full parent receipt; OpenSpec verification must consume it without executing another full owner.
- [ ] 8.4 Run strict OpenSpec validation, project audit, installed-currentness checks, and predictive-KB postflight.
