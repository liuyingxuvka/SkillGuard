## ADDED Requirements

### Requirement: Canonical local source remains publication authority
SkillGuard SHALL require one canonical local source for every active maintained skill and SHALL treat installed and GitHub copies as derived synchronization targets.

#### Scenario: Installed copy is newer
- **WHEN** installed protection or behavior is newer than the selected canonical source
- **THEN** synchronization is blocked until the source is intentionally reconciled; the installer does not overwrite the installed copy

### Requirement: Public artifacts exclude local run and private path data
SkillGuard SHALL keep run evidence outside installed skill packages and SHALL tokenize or reject private absolute paths and target-specific inputs in published artifacts.

#### Scenario: Generated contract contains a user home path
- **WHEN** a published generated artifact contains an unapproved machine-specific source root
- **THEN** the public-boundary check fails before installation or publication

### Requirement: Publication evidence is separate from functional evidence
SkillGuard SHALL require separate current source, installed, repository, tag/release, and post-publication receipts for publication claims and SHALL NOT treat functional closure alone as proof of publication.

#### Scenario: Local release profile passes but GitHub tag is absent
- **WHEN** local checks pass but no matching remote tag/release receipt exists
- **THEN** SkillGuard reports local release readiness without claiming publication complete

### Requirement: Adopted skills preserve upstream and maintainer identities
SkillGuard SHALL require a maintained skill without a user-owned repository to record its upstream source, license/redistribution decision, selected adoption mode, local canonical source, and any later maintainer repository as separate identities.

#### Scenario: GitHub upstream is forkable
- **WHEN** an adoption candidate has a licensed GitHub upstream and the maintainer chooses continued derivative maintenance
- **THEN** the plan validates changes on a local maintenance branch, creates a GitHub fork in the maintainer account, records distinct `origin` and `upstream` remotes, pushes the validated branch, and forbids GitHub-web edits from becoming canonical source

#### Scenario: License is missing or ambiguous
- **WHEN** the upstream material has no clear redistribution permission
- **THEN** SkillGuard blocks public repository creation and permits only a scoped local overlay or an upstream clarification action

### Requirement: Functional pass does not grant publication rights
SkillGuard SHALL keep functional closure, repository ownership, attribution, and redistribution permission as separate decisions.

#### Scenario: Third-party skill passes all runtime checks
- **WHEN** an adopted third-party skill reaches functional closure but its publication permission is unresolved
- **THEN** SkillGuard reports functional pass and publication blocked without changing the upstream ownership claim

### Requirement: Adopted forks receive a traceable maintainer release
For a publishable GitHub fork, SkillGuard SHALL require a new maintainer version and non-moving tag, release notes that identify the upstream repository and base commit/tag, and current post-publication installation and parity evidence.

#### Scenario: Local adopted skill reaches release closure
- **WHEN** the validated local maintenance branch passes release closure and publication permission is current
- **THEN** the branch is pushed to the maintainer fork, a new maintainer version/tag and GitHub Release are created, and clean-install verification binds the fork commit, release tag, installed copy, and upstream base

#### Scenario: Upstream tag would be reused
- **WHEN** publication attempts to move, overwrite, or ambiguously reuse an upstream release tag
- **THEN** SkillGuard blocks publication and requires a distinct maintainer release identity
