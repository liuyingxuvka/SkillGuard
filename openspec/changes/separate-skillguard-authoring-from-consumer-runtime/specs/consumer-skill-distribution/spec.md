## ADDED Requirements

### Requirement: Clean consumer projection
The consumer distribution SHALL contain only target-owned domain entrypoints, prompts, references, assets, scripts, native runtime, and a target-owned release manifest.

#### Scenario: Consumer bundle scan
- **WHEN** a graduated skill distribution is built
- **THEN** it SHALL contain no `.skillguard/**`, SkillGuard managed marker, receipt, supervisor, Portfolio, router, or author-maintenance command

#### Scenario: Target-native validation script
- **WHEN** a target requires a native validation script during ordinary work
- **THEN** the script MAY be distributed only under a target-owned path without importing or invoking SkillGuard

### Requirement: Hidden runtime migration gate
Consumer construction MUST block when excluding author-control paths would remove referenced target-domain runtime or data.

#### Scenario: Runtime beneath control root
- **WHEN** a target imports or hashes a file beneath `.skillguard/runtime`
- **THEN** the consumer build SHALL block until the file is moved to a target-owned namespace and native parity is current

#### Scenario: Control-only metadata
- **WHEN** a target's `.skillguard` tree contains only author contracts, checks, receipts, or adapters
- **THEN** the consumer projection SHALL exclude the entire tree without changing target-domain behavior

### Requirement: Consumer independence
A graduated skill MUST install and perform its representative domain work in an environment without SkillGuard.

#### Scenario: Clean CODEX_HOME
- **WHEN** the consumer bundle is installed into an isolated `CODEX_HOME` with no SkillGuard or SkillGuard global prompt
- **THEN** target selection, native checks, artifacts, and claim boundaries SHALL remain functional

#### Scenario: Ordinary project execution
- **WHEN** the installed target runs in a clean business project
- **THEN** no SkillGuard directory, process, prompt, or global router SHALL be created

### Requirement: Safe installed withdrawal
Consumer upgrades MUST use staged activation, rollback, and ownership-aware removal of retired control files.

#### Scenario: Installer-owned unchanged file
- **WHEN** a prior installer-owned `.skillguard` file still matches its recorded hash
- **THEN** the new consumer transaction SHALL remove it as part of atomic activation

#### Scenario: Locally modified file
- **WHEN** a prior installed control file no longer matches its recorded hash
- **THEN** the installer SHALL preserve it, report a conflict, and block a broad clean-layout claim
