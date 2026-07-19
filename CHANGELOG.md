# Changelog

## v0.3.5 - 2026-07-19

- Bound each execution owner only to its declared target-input role fingerprints, while retaining explicitly universal inputs as universal; changing one role now invalidates only its consuming owner.
- Removed attempt identifiers and run-root output paths from semantic owner identity. Repeated runs with exact semantic inputs reuse one immutable terminal-success receipt and launch zero processes.
- Made every explicit selector fail closed independently and report unresolved selector details before planning; an unmapped input cannot select a broad run-all route.
- Split order-only dependencies from semantic receipt dependencies and reject order-only edges in execution identity.
- Added one complete pre-launch final-admission gate covering frozen source, toolchain, impact plan, selectors, dependencies, target inputs, installation, and unique execution ownership before the first owner starts.
- Removed OpenSpec task-checkbox progress from final verification freshness, eliminating the pass-then-checkmark-then-rerun loop.
- Upgraded the project adoption record, CI toolchain, and managed FlowGuard policy to 0.58.5, preserving one current route with no fallback, alias, compatibility reader, or parallel authority.
- Bound the public-export privacy owner to the exact current Git candidate inventory, expanded machine-local absolute-path rejection, and kept unrelated owner receipts reusable.
- Made branch-push CI the single regression gate and changed tag CI to a receipt-only version/tag/commit identity check.

## v0.3.4 - 2026-07-18

- Fixed `check-skill` so its required target sections are exclusively
  target-owned consumer instructions; the author-only `SkillGuard Maintenance`
  heading is no longer required in graduated entrypoints.
- Kept author currentness on the exact contract trio and author repository
  policy, with no conditional section mode, fallback, or compatibility route.
- Extended the current-runtime-authority FlowGuard model and external-target
  regression coverage to block author-maintenance instructions in consumer
  prompts while accepting clean consumer skills.
- Excluded generated `*.egg-info` package metadata from authoritative source,
  impact, and installation projections so clean Git checkouts reproduce the
  exact compiled installation inventory.

## v0.3.3 - 2026-07-16

- **BREAKING:** Separated private author maintenance from clean consumer
  distribution. Graduated skills no longer carry `.skillguard`, SkillGuard
  prompts, commands, receipts, Portfolio state, or router state.
- **BREAKING:** Bound every declared check and receipt to one maintenance unit,
  member, evidence subject, and semantic check; foreign-unit proof is rejected
  even when command text and inputs match.
- **BREAKING:** Replaced ordinary project adoption with explicit
  `maintainer-adopt` / `maintainer-audit`, with zero writes for ineligible
  business projects.
- **BREAKING:** Retired public ordinary global skill resolution, standalone
  consumer prompt installation, installed-skill contract auditing, and
  Portfolio result-reuse ticket paths.
- Contracted TestMesh and Portfolio to same-unit execution and independent
  status aggregation; semantic overlap now requires split, merge, or retirement
  rather than shared evidence.
- Added clean consumer distribution construction, target-runtime preflight,
  safe installer-owned withdrawal, conflict preservation, and transactional
  activation/rollback.
- Restored official OpenSpec to an external unmanaged boundary and limited
  FlowGuard integration to read-only proposal, design, specs, tasks, and status
  context.
- Removed target-specific conditional branch names from the universal compiler and runtime. Conditional branches, applicability, and total obligation disposition now come only from the target contract.
- Replaced native no-op, terminal, and applicability receipts with strict v2 schemas. Structural no-op branches emit `conditional_noop`; active branches emit `completed_branch`; no legacy receipt reader or compatibility alias remains.
- Limited scheduled-production identity checks to scheduled evidence and allowed non-scheduled targets to inherit their exact validated evidence domain without manufacturing scheduler fields.
- Removed the hidden skip-as-not-applicable closure path so only verifier-owned applicability receipts can mark a conditional obligation not applicable.
- Repaired official staged installation recovery so a separately verified current replacement can supersede a historical active and backup tree whose identities both drifted, while ordinary recovery remains fail-closed.
- Made idempotent author-repository adoption refresh an explicitly changed
  current SkillGuard version and managed inventory instead of silently
  preserving stale manifest metadata.
- Added arbitrary-branch compiler, closure, schema, non-scheduled terminal, portfolio, and installation-recovery regressions and passed the native self-host enforced closure.

## v0.3.2 - 2026-07-16

- Unified filesystem-object identity across portable content, contract compilation, external target binding, portfolio assembly, report output, installation verification, and TestMesh replay so Windows 8.3 and long path spellings cannot split one physical object into two identities.
- Preserved lexical final-component identity long enough to reject symlink and reparse-point stage roots before resolution.
- Removed clean-runner test dependence on a coincidental user-level SkillGuard installation by binding replay currentness to fixture-owned `CODEX_HOME` evidence.
- Split installation publication currentness from rollback integrity: an unreadable or policy-stale semantic projection remains non-current, while a byte-exact committed HEAD stays recoverably sound and may be transactionally replaced instead of crashing or rolling back.
- Added Windows short/long alias, reparse-stage, external-binding, report, portfolio, and replay regression coverage without weakening real escape, link, installation, or receipt-currentness blockers.
- Changed release closure ordering so corrective tags and GitHub Releases are created only after the pushed commit passes the Windows and Ubuntu GitHub Actions matrix.

## v0.3.1 - 2026-07-16

- Normalized line endings for text template inputs so compiled installation projections remain identical across Windows and Linux clean checkouts.
- Replaced retired one-shot TestMesh CI invocations with direct current test-suite commands, corrected the README's three-stage TestMesh guidance, and pinned CI to the public FlowGuard `v0.56.0` runtime.
- Added a regression proving `.template` source fingerprints are portable across LF and CRLF checkouts.

## v0.3.0 - 2026-07-15

- **BREAKING:** Collapsed SkillGuard to one fixed target-neutral workflow: freeze the target's exact declared checks, resolve one owner and valid dependency graph per check, admit only current immutable terminal results for the same request, and close only after exact reconciliation.
- **BREAKING:** Removed universal purpose contracts, protected-failure declarations, semantic-obligation universes, target-native findings, and mandatory positive/shallow calibration from SkillGuard. A target may declare such tests itself, but SkillGuard never invents or interprets them.
- **BREAKING:** Removed selectable closure levels. The sole current closure is `enforced`; non-enforced, duplicate, missing, or weakened closure projections fail closed.
- **BREAKING:** Collapsed integration to the fixed `native-integrated` marker and simplified project adoption input to `PATH|NATIVE_OWNER`. The target always owns its domain route and checks; SkillGuard never supplies a target-domain executor.
- Added the executable `.flowguard/declared_check_supervision` child model with one-check and multi-check positive paths plus 19 exact known-bad rejections.
- Added generic ordinary-skill, omitted-check, retired-field, singleton-closure, singleton-integration, receipt-freshness, installation, and project-adoption regressions.

### Superseded source-development notes

The behavior below records an earlier source-development state and was
superseded before the v0.3.0 release by the fixed-supervision behavior above.

- Added target-neutral execution-depth profiles that compile target-owned dimensions, important obligations, coverage floors, native routes/checks, closure profiles, and explicit integration modes without copying target-domain logic into SkillGuard.
- Added immutable target execution-depth receipts bound to actual current native check receipts; caller-authored pass, ownership, route, evidence-id, or freshness fields cannot establish closure authority.
- Added honest depth statuses, unique evidence-contribution accounting, two-key positive/shallow calibration, Guard and non-Guard vertical slices, and replay invalidation when contracts, profiles, inputs, runtime, or later receipts change.
- Hardened enforced evidence around exact target/contract/profile/native-owner/route/check/run/obligation identity, immutable semantic ranges, and non-interchangeable `fixture_calibration`, `capability_validation`, and `scheduled_production` domains.
- Replaced generic calibration authorization with a target-native evaluator pair: the positive case covers every important obligation and required capability, while a distinct shallow case omits exactly one important obligation and must be blocked for that exact omission.
- Added branch-conditional highest-quality closure for legitimate `no-update`, `waiting-for-user`, and `ui-running` terminals; targets must project both top-level `route_branch_closure_required: true` and conditional obligations, verifier-owned applicability receipts may mark finalize `not_applicable` without fabricating a finalize witness, and `prepared-update` keeps finalize active. Conditional targets cannot opt out by omitting their branch contract.
- Added profile-bound target-native terminal receipts: prepared updates may close a bounded routine authorization as `non_terminal_authorization`, but that receipt cannot be promoted into final completion; the later composed authorize-plus-finalize run requires its own `highest_quality` `terminal_completion` receipt, while no-op completion remains highest-quality only.
- Added two-stage `stage_depth`/`close` supervision so targets build terminal receipts from the exact issued depth id/hash; resuming the same run does not rerun completed checks and idempotently reuses the same depth receipt.
- Added scheduled-production installation currentness replay across depth issuance, terminal resolution, and closure using a portable active-installation receipt root, plus a target-owned terminal receipt builder/writer.
- Extended functional/release closure so enforced targets require a current `EXECUTION_DEPTH_PASS`; contract presence, boundary-only checks, bounded partial work, missing providers, not-run work, and stale evidence remain visible non-pass states.
- Added `project-adopt`, `project-audit`, and `project-upgrade` to install and verify a marker-bounded repository `AGENTS.md` block plus `.skillguard/project.json`, including the canonical SkillGuard repository URL, managed paths, native-route evidence, surrounding-content preservation, and corruption/staleness blockers.
- Added a first-class project-adoption FlowGuard route, schemas, fixtures, non-Guard repository slice, depth-calibration portfolio records, and focused regression coverage.
- Added proof-bound TestMesh source-parent reuse and closure receipts so one expensive parent execution can be replayed by later verification layers instead of rerun or replaced by a bare child result.
- Added content-addressed single-flight check execution with separate semantic check, execution, and execution-key identities; only terminal successes are reusable, failed attempts never satisfy reuse, source changes invalidate reuse, and runtime outputs do not alter source authority.
- Added a fail-closed, read-only full-parent TestMesh receipt consumer that rejects missing, partial, stale, tampered, or identity-incomplete proof without invoking the mesh executor or OpenSpec resume behavior.
- Added one managed validation-execution ownership policy: multi-skill validation freezes exact checks, obligations/domains, order, receipt roots, and one owner per check; consumers reuse exact current owner receipts without command duplication or evidence-output self-refresh; resume remains execution, full requires frozen source/toolchain plus one explicit owner, interrupted launchers require confirmed zero descendants, and Scheduled Task/background/unattended mutable-worktree retry is forbidden.
- Added immutable installation-verification and portfolio-impact receipts that bind current installed parity and exact revalidation-required target sets without overclaiming release or target revalidation.
- Preserved the native-route rule: complete target routes remain `native-integrated`, partial routes remain `hybrid-extension`, and `skillguard-runtime` requires reviewed native-route-absence evidence.

This source version does not by itself claim a Git tag, GitHub Release, remote CI pass, target-domain correctness, or future AI behavior guarantee.

## v0.2.0 - 2026-07-10

- Added the FlowGuard-backed executable-contract V2 compiler: a target model and confirmed binding source now deterministically produce a compiled contract and exact check manifest.
- Added typed route composition, target-local claimed runs, append-only event replay, immutable hard/witnessed/judged receipts, conditional skip proof, artifact validators, bounded loops, and monotonic routine/functional/release/highest-quality closure profiles.
- Added strict supervisor-packet consumption so unknown, misspelled, unreachable, or unselected evidence fields fail closed instead of disappearing silently.
- Added Guard-runtime fingerprints to run identity, receipts, and closure freshness so a SkillGuard behavior change creates a new run and invalidates affected older proof.
- Added audited failed/dead-writer lock recovery: live overlapping writers still block, exited or verified-failed owners can be recovered, legacy failed locks remain compatible, and idempotent resume reacquires its write locks.
- Added complete V1 field/command lifecycle control so V1 artifacts remain migration inputs or diagnostics and cannot become an alternate success path after a V2 contract is present.
- Added fast, focused, and full TestMesh profiles with source/command fingerprints, final child receipts, timeouts, cancellation, liveness-only progress events, and large-output capture without pipe deadlock.
- Added whole-tree staged installation with source-manifest parity, installed-layout smoke checks, atomic activation, retained backup, and automatic rollback on post-activation failure.
- Added canonical/installed/Git/tag/GitHub Release provenance checks, tracked-plus-unignored public-export privacy checks, hash-bound image review, and Windows/Linux GitHub Actions workflow definitions.
- Made committed contract fingerprints platform-stable by normalizing text LF/CRLF while preserving exact binary hashing, forced compiled JSON artifacts to canonical LF in Git checkouts, and set the supported runtime boundary to Python 3.11+ to match the current FlowGuard dependency.
- Completed two-stage SkillGuard self-hosting and an Autonomous UI external pressure run under the current Guard fingerprint; these local results do not by themselves prove remote CI or GitHub publication.

## v0.1.6 - 2026-06-28

- Tightened `deep-pass` so it now means current, target-specific semantic coverage rather than only structural contract-field presence.
- Hardened `check-readme-release` to require current-version README model evidence plus the README Showcase Writer fact ledger, capability claim matrix, narrative structure plan, and gap ledger.
- Added installed-skill publication-status reporting so local coverage is separated from GitHub publication evidence.
- Added regression coverage for stale README model evidence, compact README model evidence, and installed-audit publication boundaries.
- Re-synced the installed SkillGuard copy and re-audited installed user-created skills with the stricter checker before publication.

## v0.1.5 - 2026-06-28

- Promoted Deep Contract Mode into a universal target-lock workflow: every covered skill now needs target rule inventory, route inventory, workflow stage inventory, native check inventory, test gap plan, coverage matrix, and runtime lock policy instead of a generic profile-only wrapper.
- Added universal target extraction and depth checks so each target skill's own entrypoints, routes, workflow stages, hard gates, output requirements, native checks, evidence requirements, and closure blockers must be represented before coverage can pass.
- Re-audited covered installed user skills one by one: 64 covered skills passed with complete target-lock rows, non-empty route/stage/matrix coverage, and `may_define_parallel_execution_route=false`.
- Kept FlowPilot native-integrated during the deeper audit, preserving its own route/check surface with `run_record_required=false` instead of creating a SkillGuard-owned parallel route.
- Fixed runtime closure bookkeeping so accepted SkillGuard-owned runs advance to the final route phase instead of leaving stale phase state behind.

## v0.1.4 - 2026-06-28

- Added deep runtime-contract coverage fields for source requirements, acceptance obligations, skill-specific checks, closure blockers, current run records, non-parallel route proof, and cleanup gates.
- Added the `check-depth` command and negative deep-contract fixtures so shallow contracts, missing README gates, stale run evidence, and parallel route risks are blocked explicitly.
- Added the `check-readme-release` command so bilingual README mirrors, text-to-image hero provenance, README model evidence, version consistency, command-surface wording, and public-boundary checks are executable before publishing.
- Preserved native and hybrid target skill routes while upgrading installed skills to the deeper SkillGuard contract schema.
- Corrected native/hybrid contracts so they bind target-owned routes and checks with `run_record_required=false`; only `skillguard-runtime` targets retain accepted SkillGuard run records.
- Rebuilt the README with the README Showcase Writer workflow: English-first structure, full Chinese mirror, text-to-image concept hero, project-specific prompt/design notes, and current release boundaries.

## v0.1.3 - 2026-06-27

- Reworked the public README into a clearer release page with current usage, runtime-contract workflow, global-router boundary, validation scope, and source-only release status.
- Added a README hero image and design notes that explain the SkillGuard workflow without exposing local machine details.
- Clarified that the global SkillGuard router is a selection and maintenance layer, not a mandatory pre-execution gate for every skill.
- Fixed global-registry freshness checks so `.codex/...` scan roots resolve through the supplied Codex home instead of falling back to a narrower default scan.
- Sandboxed mutating global-router fixture commands so repeated tests do not leave generated timestamp residue in fixture evidence files.

## v0.1.2 - 2026-06-27

- Corrected the public release train back to the repository's `0.x` version policy after erroneous `v1.0.1` and `v1.0.2` labels were published.
- Reworded the SkillGuard global-router boundary text to avoid false overclaim scanner matches.
- Kept source and installed SkillGuard entrypoints synchronized after the final OpenSpec verification pass.
