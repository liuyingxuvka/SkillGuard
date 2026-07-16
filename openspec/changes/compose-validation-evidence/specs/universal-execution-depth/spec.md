## MODIFIED Requirements

### Requirement: Canonical source and installed parity
The Git repository SHALL be the canonical SkillGuard source after migration. Installation SHALL consume the frozen content-impact plan, assemble one complete staged tree from unchanged current components plus affected `copy` and `generate` components, validate it, activate it atomically, retain a backup, and roll back automatically on failure. Canonical, staged, and active trees SHALL exclude every path classified as runtime-only while preserving declared static fixture evidence. Whole-tree byte parity MAY remain a cheap integrity check but SHALL NOT imply full validation; installed smoke owners SHALL be selected only from affected component edges.

#### Scenario: Partial installed sync
- **WHEN** an affected installable component is only partly staged or a required generated component is absent
- **THEN** component parity SHALL identify the exact incomplete component and activation SHALL remain blocked

#### Scenario: Source-only component changes
- **WHEN** only `source_only` test, fixture, model, or documentation components change
- **THEN** installation SHALL remain not required and SHALL NOT trigger installed smoke or full validation

#### Scenario: Runtime component changes
- **WHEN** one installable runtime component changes
- **THEN** the staged tree SHALL replace that component atomically and post-activation smoke SHALL execute only the owners reached from that component in the frozen impact plan

#### Scenario: Post-activation check fails
- **WHEN** staged activation succeeds but a required post-activation validation fails
- **THEN** the installer SHALL restore the previous active tree and retain failure evidence

#### Scenario: Runtime workspace enters canonical source
- **WHEN** a runtime workspace such as `.sg-runtime` exists under the canonical maintained skill root
- **THEN** canonical-source validation and installation SHALL fail until scoped cleanup removes it

#### Scenario: Static nested fixture resembles runtime control
- **WHEN** maintained fixture evidence contains a control-shaped nested sample beneath a declared fixture member root
- **THEN** canonical and installed parity SHALL preserve the sample and SHALL NOT confuse it with a live runtime control root
