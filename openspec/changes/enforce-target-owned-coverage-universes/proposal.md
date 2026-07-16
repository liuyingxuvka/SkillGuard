## Why

Universal Execution Depth can currently report a pass from declared obligation counts and caller-labeled contributions without proving that the target evaluated an adequate, target-owned universe of cases. This permits empty denominators, sparse time-series sampling, reused payloads, weak calibration, and prompt/runtime version drift to look deeper than they are. Current multi-repository runs also show that the skill/model repository and task-data root are independent authorities; collapsing them during closure makes valid calibration look stale.

## What Changes

- **BREAKING**: Enforced depth dimensions require non-empty obligation denominators and a target-owned coverage-universe contract with owner and immutable fingerprint.
- Track eligible, selected, and validated scope; floor values and their origin; strata; critical uncovered items; per-object depth; and requested-versus-covered claim scope.
- Require a content-addressed discovered/declared/excluded object attestation so a target cannot shrink the denominator by omitting a low-ranked object; every exclusion needs a typed disposition and reason and contributes to no covered claim.
- Bind each object to a content-addressed child universe, then consume a precommitted target-native dynamic-floor receipt whose algorithm, input population, count, strata, and receipt identity are current. The effective floor is the field-wise stricter of the compiled safety floor and the native floor.
- Bind evidence uniqueness to immutable receipt/payload identity plus a declared contribution range, so renaming a contribution cannot duplicate proof.
- Bind both calibration keys to a complete fixture/model/config input manifest, exact command fingerprints, actual observed status/blocker, and a content-addressed native observation artifact; a zero exit or fixture-authored expectation is not evidence.
- Support class-aware per-object floors and a native critical-object scope so a high aggregate result cannot hide one shallow required object while noncritical observations remain visible.
- Preserve separate `repository_root` and `target_root` roles across issuance, closure, and replay with portable content hashes rather than persisted absolute paths.
- Add provider/runtime readiness and enrollment auditing so a new prompt cannot supervise an older or unenrolled runtime.
- Replace SkillGuard self-host's same-receipt/multiple-label evidence with genuinely distinct target-owned receipts and add shallow negative fixtures.
- Synchronize schemas, compiler, supervisor, closure, references, SkillGuard entrypoint, README, FlowGuard models, and tests while preserving the target's native-route authority.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `universal-execution-depth`: Strengthen execution-depth acceptance with target-owned coverage universes, immutable contribution uniqueness, class-aware per-object policy, content-addressed native calibration, dual-root replay, and provider/runtime enrollment readiness.

## Impact

The change affects SkillGuard V2 depth schemas and compilation, execution-depth receipt issuance and evaluation, supervisor packet validation, closure gates, self-host fixtures, documentation, FlowGuard models, and focused regression suites. Existing advisory profiles remain visible but cannot enter enforced mode until migrated; native target routes and checks remain the only domain authorities. Release, installation, publication, and archival are outside this active change.
