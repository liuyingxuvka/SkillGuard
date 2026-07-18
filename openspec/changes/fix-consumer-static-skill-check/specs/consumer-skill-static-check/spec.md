## ADDED Requirements

### Requirement: Consumer-owned entrypoint sections
`check-skill` SHALL require only target-owned sections that remain meaningful
in the graduated consumer distribution and SHALL NOT require an author-only
SkillGuard maintenance section.

#### Scenario: Clean consumer-style target
- **WHEN** a current maintained target has valid frontmatter, target-owned
  workflow and validation sections, and no SkillGuard text in its `SKILL.md`
- **THEN** the required-section check SHALL pass

#### Scenario: Target workflow section is missing
- **WHEN** a current maintained target omits a required target-owned workflow
  or hard-gate section
- **THEN** `check-skill` SHALL fail the required-section check

### Requirement: Author authority remains external to the consumer prompt
Author-maintenance currentness SHALL be proven by the exact author contract
trio and author repository policy, not by a section embedded in the target
consumer `SKILL.md`.

#### Scenario: Author contract is incomplete
- **WHEN** a consumer-clean target lacks one current author contract file
- **THEN** `check-skill` SHALL block on author authority even though its
  consumer entrypoint sections are valid

#### Scenario: Consumer prompt contains author maintenance
- **WHEN** a staged consumer `SKILL.md` contains a SkillGuard maintenance
  section or instruction
- **THEN** consumer-distribution validation SHALL block

### Requirement: One current static target format
The static target checker MUST have one required-section set and MUST NOT
provide a legacy, mode-selectable, conditional, or fallback section policy.

#### Scenario: Retired author heading is supplied
- **WHEN** a caller attempts to rely on the old author-heading requirement
- **THEN** it SHALL receive no alternate success route or compatibility mode
