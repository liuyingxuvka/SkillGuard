## Why

SkillGuard already supervises skill contracts, native checks, execution receipts, freshness, installation, and closure. During the native-depth hardening work it was extended one layer too far: it began requiring every maintained skill to declare a Guard-style purpose contract, protected failure claims, a semantic-obligation universe, and a mandatory positive/shallow pair.

That is the wrong ownership boundary. An ordinary skill may have no Guard model at all. SkillGuard must verify the checks the target skill actually declares; it must not invent what the target should prevent, require a domain counterexample format, or interpret target-domain findings.

This change keeps the valuable exact execution identity and receipt work, removes the Guard-specific semantic layer from SkillGuard, and restores one fixed universal responsibility.

## What Changes

- **BREAKING** Remove `purpose_contract_policy`, `purpose_contract_identity`, protected-failure, semantic-obligation, and target-native-finding authority from the SkillGuard runtime contract.
- **BREAKING** Remove the universal requirement for a positive/shallow calibration pair. If a target declares good, bad, negative, replay, or other tests, SkillGuard executes them as ordinary declared checks; it does not require those categories from every skill.
- Require one exact declared-check inventory for every maintained target, with one execution owner per check and an immutable terminal result for the current inputs.
- Preserve exact target, contract, owner, route, check, run, obligation, receipt, observation-locator, evidence-domain, freshness, branch, installation, and consumer identity where the target declares those surfaces.
- Restore the generic top-level `request_fingerprint`; rename the generic locator concept to `native_observation_locator` so it does not imply that SkillGuard owns domain semantics.
- Reject hidden skipped, timeout, not-run, stale, duplicate-owner, duplicate-execution, and undeclared-result rows.
- Add an ordinary non-Guard regression target proving that SkillGuard does not demand a model purpose, protected failure, or Guard-style counterexample.
- Keep Guard-family purpose/blockability contracts out of this repository. PhysicsGuard, LogicGuard, SourceGuard, TraceGuard, WorldGuard, and FlowGuard own those rules in their native workflows.

## Capabilities

### Modified Capabilities

- `native-depth-evidence-identity`: exact target-native execution and observation identity without target-domain purpose semantics.
- `universal-execution-depth`: current execution of target-declared obligations and checks, with no mandatory Guard-style calibration.

## Impact

Implementation affects SkillGuard schemas, compiler/runtime validators, check execution, receipts, templates, fixtures, self-contract, prompts, FlowGuard child model, and tests. Existing exact identity, evidence-domain, freshness, branch, installation, TestMesh, and receipt-consumer work remains in scope. Purpose and blockability requirements move to the Guard repositories that own their domain models.

No compatibility reader or optional mode will be introduced. The sole current SkillGuard contract accepts the generic fields and rejects the removed Guard-specific fields.
