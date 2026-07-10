# Changelog

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
