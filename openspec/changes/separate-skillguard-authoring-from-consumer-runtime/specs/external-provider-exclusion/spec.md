## ADDED Requirements

### Requirement: Explicit external unmanaged providers
SkillGuard SHALL support explicit `external_excluded` entries that remain outside managed-target contract, installation, routing, and graduation authority.

#### Scenario: Official OpenSpec registered
- **WHEN** official OpenSpec skills are present in the installed skill root
- **THEN** SkillGuard SHALL classify them as external exclusions rather than managed, blocked, or contract-missing targets

#### Scenario: Unregistered ordinary skill
- **WHEN** a skill is neither explicitly managed nor externally excluded
- **THEN** SkillGuard SHALL make no maintenance-currentness claim and SHALL NOT block ordinary use

### Requirement: Official provider content integrity
SkillGuard MUST NOT modify, wrap, install control state beside, or regenerate official external provider skills.

#### Scenario: Official OpenSpec update
- **WHEN** the pinned official OpenSpec generator updates its skills
- **THEN** the resulting directories SHALL remain free of SkillGuard sections and `.skillguard` state

#### Scenario: Local injected provider content
- **WHEN** an installed official provider contains a prior local SkillGuard layer
- **THEN** migration SHALL replace the complete provider skill from the official generator rather than preserve the injected layer

### Requirement: Read-only specification context
FlowGuard MAY read official provider proposal, design, specification, task, and status identifiers as development-process context, but the provider MUST NOT own FlowGuard product behavior or test execution.

#### Scenario: OpenSpec requirement maps to FlowGuard work
- **WHEN** a FlowGuard change implements an OpenSpec requirement
- **THEN** FlowGuard MAY record the provider/change/task relation while owning its own model, checks, and evidence

#### Scenario: Receipt bridge requested
- **WHEN** an OpenSpec path attempts to carry, replay, resume, cache, or consume a FlowGuard or SkillGuard test receipt
- **THEN** the integration SHALL block and no owner command SHALL execute

### Requirement: No custom provider verification authority
Official OpenSpec authority SHALL be limited to its supported artifacts and native commands; custom verification contracts, reports, sessions, and caches MUST NOT be treated as official provider state.

#### Scenario: Legacy verification artifacts remain
- **WHEN** `verification-contract.yaml`, `verification-report.json`, or custom spec-session state is discovered
- **THEN** it SHALL be classified as historical or target-owned maintenance material and SHALL have no provider runtime authority
