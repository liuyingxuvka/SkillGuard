## ADDED Requirements

### Requirement: Explicit author-maintenance activation
SkillGuard SHALL activate only for creating, updating, auditing, validating, installing, synchronizing, or releasing an explicitly managed skill source.

#### Scenario: Ordinary skill use
- **WHEN** a user invokes a graduated skill for its domain work
- **THEN** SkillGuard SHALL remain inactive and missing SkillGuard state SHALL NOT block the domain task

#### Scenario: Explicit skill maintenance
- **WHEN** a user updates the canonical source of an explicitly managed skill
- **THEN** SkillGuard SHALL activate the author-maintenance workflow and retain the target's native action and check ownership

### Requirement: Explicit author repository and evidence root
Every supervised maintenance run MUST bind an author repository role, maintenance unit, and author evidence root before state is created.

#### Scenario: Author root supplied
- **WHEN** an eligible skill-maintainer repository supplies its unit identity and evidence root
- **THEN** run, receipt, and execution state SHALL be created only beneath that author-controlled root

#### Scenario: Author root omitted
- **WHEN** a supervised maintenance request omits the author evidence root
- **THEN** the request SHALL block before creating `.skillguard`, run, lock, receipt, or prompt state

### Requirement: Ordinary project zero-write boundary
SkillGuard MUST reject ordinary business projects and consumer repositories as author-maintenance roots with zero writes.

#### Scenario: Business project uses FlowGuard
- **WHEN** an ordinary project uses an installed FlowGuard skill
- **THEN** SkillGuard SHALL NOT create `.skillguard`, modify `AGENTS.md`, or install a project manifest

#### Scenario: Maintainer repository adoption
- **WHEN** a repository explicitly declares `repository_role: skill_maintainer_source`, its maintenance units, and consumer exclusion
- **THEN** author-maintenance adoption MAY write the current author manifest and managed author prompt

### Requirement: Author and consumer prompt separation
Author-maintenance prompts MUST be stored and projected separately from target-domain consumer instructions.

#### Scenario: Graduated target prompt
- **WHEN** a consumer `SKILL.md` is generated
- **THEN** it SHALL describe only the target's activation, workflow, checks, and claim boundary and SHALL NOT mention SkillGuard runtime state

#### Scenario: Author router prompt
- **WHEN** the author registry is refreshed
- **THEN** its managed prompt SHALL be installed only in the declared author environment and SHALL NOT enter a consumer distribution
