## ADDED Requirements

### Requirement: External checks bind one canonical repository and one member

`check-contract` and `check-skill` SHALL accept one explicit canonical `--repository-root` and SHALL resolve the declared `--target` as exactly one member root inside it. Repository-relative contract, model, check, implementation, and declared-reference paths SHALL resolve only from that canonical repository root.

#### Scenario: Nested external member passes

- **WHEN** a caller supplies a canonical repository root and a nested current target member inside it
- **THEN** both commands bind the same repository/member pair
- **AND** repository-relative material resolves from the repository root rather than the member directory or SkillGuard's own repository

#### Scenario: Member escapes the declared root

- **WHEN** the declared target resolves outside the canonical repository root
- **THEN** the command blocks with a target-binding error
- **AND** it does not retry from the member, current working directory, SkillGuard repository, or another root

#### Scenario: Repository-relative reference is absent but a member copy exists

- **WHEN** a repository-relative declared reference or contract path is absent from the explicit canonical repository root
- **AND** a same-named path exists under the target member
- **THEN** `check-skill` or `check-contract` SHALL fail or block on the missing canonical path
- **AND** it SHALL NOT select the member copy by existence, retry, inference, or fallback

### Requirement: Standalone dot binding remains deterministic

When `--target .` is used without an external repository root, the commands SHALL bind the current directory as both canonical repository root and member root, with portable `member_root_path` equal to `.`.

#### Scenario: Standalone current skill

- **WHEN** a current skill is checked from its own directory with `--target .`
- **THEN** the command uses one standalone binding
- **AND** no external-root inference or fallback occurs

### Requirement: Binding reports are portable and schema-governed

Successful checks SHALL emit a `target_binding` object conforming to `skillguard.external_target_binding.v1`. The projection SHALL record verified roles, binding mode, portable member path, containment, and `fallback_used=false`, and SHALL NOT persist absolute machine paths.

#### Scenario: Explicit binding report

- **WHEN** an external nested target check succeeds
- **THEN** its binding projection validates against the current schema
- **AND** the report contains no absolute repository or member path

### Requirement: Former target-root spelling has no success route

`check-contract --target-root` SHALL be rejected. SkillGuard SHALL NOT preserve it as an alias, compatibility reader, or fallback for `--repository-root`.

#### Scenario: Former option is supplied

- **WHEN** a caller invokes `check-contract` with `--target-root`
- **THEN** argument validation rejects the invocation
- **AND** no contract compilation or static target validation runs
