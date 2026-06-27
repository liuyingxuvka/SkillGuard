# Changelog

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
