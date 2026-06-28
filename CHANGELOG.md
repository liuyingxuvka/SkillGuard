# Changelog

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
