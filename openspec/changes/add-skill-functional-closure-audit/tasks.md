## 1. Models and contracts

> Superseded: do not execute these tasks. Use `../build-executable-skill-contract-runtime/tasks.md`.

- [ ] 1.1 Add the FlowGuard capability-closure child model with behavior commitments, lifecycle stages, failure/recovery transitions, claim scopes, and freshness rules.
- [ ] 1.2 Add target field-lifecycle and ContractExhaustion records for closure schema keys, malformed records, stale evidence, false success, missing recovery, and insufficient quality evidence.
- [ ] 1.3 Bind model obligations to owner code contracts and required unit/fixture evidence in Model-Test Alignment records.

## 2. Functional-closure schemas and templates

- [ ] 2.1 Add `skillguard_functional_closure.schema.json` with outcomes, paths, stages, failures, quality requirements, evidence axes, and claim boundary.
- [ ] 2.2 Add `skillguard_portfolio_registry.schema.json` with active/retired lifecycle, canonical source, installed path, repository identity, visibility, and release policy.
- [ ] 2.3 Add portable functional-closure and private portfolio-registry templates with no machine-specific values.

## 3. Capability audit engine

- [ ] 3.1 Add a separate `capability_engine.py` and register `check-capability`, `audit-capabilities`, and `check-source-sync` without breaking existing command dispatch.
- [ ] 3.2 Implement schema, cross-reference, path-order, native-binding, failure-disposition, terminal, non-goal, and evidence-fingerprint validation.
- [ ] 3.3 Implement routine, functional, release, and highest-quality floors with separate execution, environment, quality, result, and freshness decisions.
- [ ] 3.4 Emit stable gap codes, affected ids, concrete repair actions, skipped checks, residual risk, and claim boundary.
- [ ] 3.5 Implement portfolio discovery and aggregation that preserves every child status and excludes explicitly retired entries only when a registry says so.

## 4. Source provenance and non-downgrade

- [ ] 4.1 Load and validate an explicit private portfolio registry while sanitizing paths from public output.
- [ ] 4.2 Compare source and installed entrypoint, work-contract, check-manifest, functional-closure, and normalized semantic fingerprints.
- [ ] 4.3 Block ambiguous/missing source ownership and any source-to-installed reduction in structural or functional protection.
- [ ] 4.4 Record the three retired private repositories in the local portfolio registry used for this project and exclude them from active repair counts.

## 5. SkillGuard self-hosting and integration

- [ ] 5.1 Add SkillGuard's own functional-closure record and current evidence artifacts for the command, fixture, source-sync, and report paths.
- [ ] 5.2 Add functional status fields to installed-skill audit output while preserving the existing structural decision and public compatibility.
- [ ] 5.3 Update the SkillGuard entrypoint, work contract, check manifest, functional closure blockers, command surface, and global-router freshness expectations.

## 6. Fixtures and tests

- [ ] 6.1 Add positive functional closure fixtures for routine, functional, release, and highest-quality scope.
- [ ] 6.2 Add known-bad fixtures for missing outputs/stages/recovery/terminals, prose-only evidence, stale or failed evidence, weak claim scope, and non-goal false success.
- [ ] 6.3 Add portfolio fixtures proving mixed child truth and source-sync fixtures proving normalization-only drift, ambiguous ownership, retired exclusion, and downgrade blocking.
- [ ] 6.4 Add standard-library unit tests for all new command paths, schemas, reports, public path sanitization, and compatibility with existing commands.
- [ ] 6.5 Run the complete verification contract and repair all failures without weakening required gates.

## 7. Documentation, installation, and release

- [ ] 7.1 Update README English/Chinese sections, command surface, examples, status meanings, non-guarantees, and functional-vs-structural explanation.
- [ ] 7.2 Update README model evidence, CHANGELOG, VERSION, pyproject metadata, and public portable examples for the new release.
- [ ] 7.3 Run source self-check, check-contract, check-depth, check-capability, fixtures, unit tests, FlowGuard models, OpenSpec validation/verification, and privacy scans.
- [ ] 7.4 Stage a non-downgrade installed SkillGuard update, verify the installed commands and self-capability, then refresh/check the global registry and managed prompt.
- [ ] 7.5 Commit and publish from the local source branch, verify GitHub default branch/tag/release, rerun the full verification contract after publication, and preserve rollback evidence.
