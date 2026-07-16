## ADDED Requirements

### Requirement: Shared portable-artifact policy
SkillGuard SHALL maintain one versioned path-classification policy, or explicitly named projections of that policy, for source inventories, compilation and runtime fingerprints, installation, installed parity, provenance, privacy, fixture cleanup, and synchronized-target checks.

#### Scenario: Consumer classifies a path
- **WHEN** any covered subsystem decides whether a repository-relative path is portable or runtime-only
- **THEN** it SHALL consume the shared policy result and record the policy version rather than use an independent ignore set

#### Scenario: Policies disagree
- **WHEN** two covered consumers would classify the same path and context differently without a declared projection rule
- **THEN** validation SHALL block with a policy-divergence finding

### Requirement: Runtime workspaces are never portable
Live runtime workspaces, caches, locks, run records, bootstrap outputs, test result roots, temporary generation directories, and roots such as `.sg-runtime`, `.sg-fixtures`, `.sgf`, and `.runtime_workspaces` MUST NOT be installed, synchronized, hashed as maintained source, or accepted by source/installed parity.

#### Scenario: Canonical skill contains `.sg-runtime`
- **WHEN** a live `.sg-runtime` directory exists beneath a maintained skill root
- **THEN** source-boundary validation and installation SHALL block and SHALL identify the exact runtime path

#### Scenario: Installed skill contains runtime residue
- **WHEN** an active installed skill contains a runtime-only path
- **THEN** installed parity SHALL fail even if all expected portable files match

### Requirement: Static fixture evidence remains portable
The shared policy SHALL preserve intentionally maintained static fixture evidence, including control-shaped sample paths nested beneath a declared fixture member root, while distinguishing it from a live target control root.

#### Scenario: Fixture contains sample run record
- **WHEN** a declared static fixture contains a nested `.skillguard/runs` sample beneath its fixture member root
- **THEN** the policy SHALL classify that sample as portable fixture evidence and installation/parity SHALL retain it

#### Scenario: Live target run record appears at control root
- **WHEN** the same `.skillguard/runs` shape occurs at a maintained target's live control root
- **THEN** the policy SHALL classify it as runtime-only and block portability

### Requirement: Portable inventory is deterministic
For the same repository bytes, policy version, root context, and declared source paths, SkillGuard SHALL produce the same sorted portable inventory and hash on every run.

#### Scenario: Filesystem enumeration order changes
- **WHEN** the host returns directory entries in a different order
- **THEN** the normalized inventory rows and inventory hash SHALL remain identical

### Requirement: Maintained content is classified into semantic components
Every maintained portable leaf file SHALL be assigned exactly one semantic role and one installation disposition before validation planning. SkillGuard SHALL group files automatically by semantic role, installation disposition, and exact consumer set; reviewed overrides MAY resolve genuinely ambiguous files but SHALL NOT replace automatic classification with a hand-maintained file list.

#### Scenario: Test-only content changes
- **WHEN** a maintained file is classified as `test_dev` with `source_only` installation disposition
- **THEN** only the exact test owner consumers SHALL be affected and installation SHALL remain not required

#### Scenario: Reviewed fixture subtree gains a descendant
- **WHEN** a target owner declares one maintained directory as a reviewed `fixture_reference` and `source_only` override and a new inventoried descendant is added beneath it
- **THEN** the descendant SHALL inherit that exact role and disposition, SHALL remain outside installation, and SHALL NOT require a new per-file override

#### Scenario: Skill root is the repository root
- **WHEN** a maintained skill uses the repository root as its skill root and keeps regression evidence beneath `fixtures/`
- **THEN** SkillGuard SHALL classify those descendants as `fixture_reference` and `source_only` exactly as it does for a nested skill fixture directory

#### Scenario: Reviewed overrides overlap
- **WHEN** two reviewed content-role overrides select the same maintained file
- **THEN** impact planning SHALL block without choosing a more-specific selector, declaration order, or fallback role

#### Scenario: Content classification is missing or ambiguous
- **WHEN** a maintained file has no role, multiple primary roles, no consumer, or an unresolved installation disposition
- **THEN** impact planning SHALL block before any owner executes and SHALL NOT broaden to a full run

#### Scenario: Evidence output is written
- **WHEN** a report, receipt, sidecar, log, lock, progress record, or generated verification result changes beneath a declared evidence root
- **THEN** the portable-content policy SHALL classify it as runtime evidence output and it SHALL NOT change any maintained component hash

### Requirement: One declared member root maps the exact installation member
SkillGuard SHALL compile and hash the canonical skill root's repository-relative `member_root_path` into the current content-impact plan. Installation SHALL strip exactly that one declared root from every projected maintained path. Any projected path outside that root SHALL block; SkillGuard SHALL NOT guess a layout from the skill id, search parent directories, or repair the mismatch by fallback.

#### Scenario: Public repository uses a nested skills root
- **WHEN** the current compiled contract for `storyline-design` contains `skills/storyline-design/scripts/storyline_route_check.py`
- **THEN** the manifest SHALL declare `member_root_path: skills/storyline-design`, installation replay SHALL resolve `scripts/storyline_route_check.py` beneath the canonical Storyline skill root, and the component and projection hashes SHALL remain bound

#### Scenario: Installation path names another skill
- **WHEN** a `storyline-design` installation component contains `skills/other-skill/SKILL.md`
- **THEN** installation replay SHALL block before copy or activation and SHALL NOT search another root, infer a skill-id prefix, or fall back to a repository-relative path

### Requirement: Runtime cleanup is scoped and provable
Runtime cleanup SHALL resolve and verify every target path beneath an explicitly authorized root, remove only paths classified as runtime-only, and rerun source or installed boundary validation afterward.

#### Scenario: Cleanup candidate escapes root
- **WHEN** a cleanup candidate resolves outside the authorized maintained or installed skill root
- **THEN** cleanup SHALL block without removing any path

#### Scenario: Scoped cleanup succeeds
- **WHEN** runtime residue is removed from an authorized root
- **THEN** subsequent boundary, inventory, and parity checks SHALL show that no runtime path remains and no portable fixture was lost
