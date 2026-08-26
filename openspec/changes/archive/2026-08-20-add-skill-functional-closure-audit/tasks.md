> **Historical-only ledger:** the checkboxes below preserve the state of this
> superseded proposal for provenance. They are not current implementation work,
> do not create a second authority, and must not be used as evidence that the
> current runtime is complete. Any unresolved item is a direct-current repair
> input or blocker under `build-executable-skill-contract-runtime`.

## 1. Models and contracts

> Superseded: do not execute these tasks. Use `../build-executable-skill-contract-runtime/tasks.md`.

- [ ] 1.1 Add the FlowGuard capability-closure child model with behavior commitments, lifecycle stages, failure/recovery transitions, claim scopes, and freshness rules.
- [ ] 1.2 Add target field-lifecycle and ContractExhaustion records for closure schema keys, malformed records, stale evidence, false success, missing recovery, and insufficient quality evidence.
- [ ] 1.3 Bind model obligations to owner code contracts and required unit/fixture evidence in Model-Test Alignment records.

## 2. Functional-closure schemas and templates

- [x] 2.1 Add `skillguard_functional_closure.schema.json` with outcomes, paths, stages, failures, quality requirements, evidence axes, and claim boundary.
- [x] 2.2 Add `skillguard_portfolio_registry.schema.json` with active/retired lifecycle, canonical source, installed path, repository identity, visibility, and release policy.
- [x] 2.3 Add portable functional-closure and private portfolio-registry templates with no machine-specific values.

## 3. Capability audit engine

- [x] 3.1 Add a separate `capability_engine.py` and register `check-capability`, `audit-capabilities`, and `check-source-sync` without breaking existing command dispatch.
- [x] 3.2 Implement schema, cross-reference, path-order, native-binding, failure-disposition, terminal, non-goal, and evidence-fingerprint validation.
- [x] 3.3 Implement routine, functional, release, and highest-quality floors with separate execution, environment, quality, result, and freshness decisions.
- [x] 3.4 Emit stable gap codes, affected ids, concrete repair actions, skipped checks, residual risk, and claim boundary.
- [x] 3.5 Implement portfolio discovery and aggregation that preserves every child status and excludes explicitly retired entries only when a registry says so.
- [x] 3.6 Add target-owned public-surface inventory/disposition validation and a SkillGuard self check that compares all current commands with route and required-check declarations.

## 4. Source provenance and non-downgrade

- [x] 4.1 Load and validate an explicit private portfolio registry while sanitizing paths from public output.
- [x] 4.2 Compare source and installed entrypoint, work-contract, check-manifest, functional-closure, and normalized semantic fingerprints.
- [x] 4.3 Block ambiguous/missing source ownership and any source-to-installed reduction in structural or functional protection.
- [ ] 4.4 Record the three retired private repositories in the local portfolio registry used for this project and exclude them from active repair counts.

## 5. SkillGuard self-hosting and integration

- [x] 5.1 Add SkillGuard's own functional-closure record and current evidence artifacts for the command, fixture, source-sync, and report paths. The record remains routine/fixture-scoped; functional, release, installation, and publication claims still require their own native terminal evidence.
- [ ] 5.2 Add functional status fields to installed-skill audit output while preserving the existing structural decision and public command boundary.
- [x] 5.3 Update the SkillGuard entrypoint, work contract, check manifest, functional closure blockers, command surface, and global-router freshness expectations. Direct-current structural evidence: current entrypoint/contract/manifest self-check passes, the target-owned routine closure has four explicit paths and current evidence, the command denominator is 54/54 with no empty required checks, and the explicit two-root global-router refresh/check passes. Functional/release/install behavior remains separately bounded by the pending native receipt tasks.
- [x] 5.4 Bind the target-owned surface inventory and adequacy/model-deepening readiness to the depth profile and make portfolio graduation fail closed when the gate is absent or incomplete.
- [x] 5.5 Make consumer-release verification use the FlowGuard canonical wire identity, validate the canonical safe member inventory, and reject author identity leakage in consumer files.
- [x] 5.6 Close SkillGuard's own current public-command reverse denominator with one current route and one target-native check binding per command; require exact name/kind/function/disposition/check metadata; regenerate the route projection, inventory hash, compiled contract, and check manifest, and retain the historical under-declaration state as a deterministic negative fixture. Direct-current evidence: 54/54 public commands, 54/54 current routes, 0 empty required-check lists, exact metadata regression coverage, current surface-inventory fingerprint `sha256:85d2a900b1a00bcae3656d7e98ad4e778f389ddcd8fe1dd1b1f4cb4bbcfa646a`, current contract/manifest regenerated and source self-check passed. This closes structural reverse-denominator accounting only; native functional/release receipts remain separate pending work.
- [x] 5.8 Bind copied generated installation authorities into installation projection identity and expose declared surface-inventory diagnostics in the private registry without changing route identity.
- [ ] 5.7 Produce one frozen native execution receipt for every declared self check and consume it through the single-owner portfolio graduation path; structural `check-contract`/`check-depth` passes do not satisfy this task.

## 6. Fixtures and tests

- [ ] 6.1 Add positive functional closure fixtures for routine, functional, release, and highest-quality scope.
- [ ] 6.2 Add known-bad fixtures for missing outputs/stages/recovery/terminals, prose-only evidence, stale or failed evidence, weak claim scope, and non-goal false success.
- [ ] 6.3 Add portfolio fixtures proving mixed child truth and source-sync fixtures proving normalization-only drift, ambiguous ownership, retired exclusion, and downgrade blocking.
- [ ] 6.4 Add standard-library unit tests for all new command paths, schemas, reports, public path sanitization, and the existing command boundary.
- [ ] 6.5 Run the complete verification contract and repair all failures without weakening required gates.
- [x] 6.6 Add deterministic surface-inventory and consumer-release positive/negative fixtures, including the known 51-command, 26-route-gap, 44-empty-check self case and underscore identity leak.
- [x] 6.8 Add mutation/negative tests for re-sealed command under-declaration, malformed consumer member inventories, author hash fields, incomplete retired sentinels, generated installation authority drift, and registry surface diagnostics.
- [ ] 6.7 Add and execute the complete SkillGuard self-host functional/release evidence matrix, including clean consumer projection and transactional installation currentness; leave the unit blocked until all terminal receipts are current.

## 7. Documentation, installation, and release

- [ ] 7.1 Update README English/Chinese sections, command surface, examples, status meanings, non-guarantees, and functional-vs-structural explanation.
- [ ] 7.2 Update README model evidence, CHANGELOG, VERSION, pyproject metadata, and public portable examples for the new release.
- [ ] 7.3 Run source self-check, check-contract, check-depth, check-capability, fixtures, unit tests, FlowGuard models, OpenSpec validation/verification, and privacy scans.
- [x] 7.4 Stage a non-downgrade installed SkillGuard update, verify the installed commands and self-capability, then refresh/check the global registry and managed prompt. Direct-current evidence: staged and activated transaction `install-db9d972bfe0042b3b8208f9f3a30c059` passed stage parity, activation smoke, source/installed projection parity, installed contract/self-check/command/import/zero-bytecode checks, followed by explicit global-router refresh and registry freshness check with 2 current author entries. This does not claim functional/release/publication closure.
- [ ] 7.5 Commit and publish from the local source branch, verify GitHub default branch/tag/release, rerun the full verification contract after publication, and preserve rollback evidence.
