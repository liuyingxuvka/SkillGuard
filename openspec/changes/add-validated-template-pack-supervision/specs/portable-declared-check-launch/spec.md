## ADDED Requirements

### Requirement: Declared command resolves to a canonical launch plan
Before execution, SkillGuard SHALL resolve every declared command into a structured launch plan containing requested token, resolved path or shim, required interpreter, exact argv, working directory, platform, environment fingerprint, and toolchain identity.

#### Scenario: Direct executable resolves directly
- **WHEN** a declared command resolves to a directly executable program on the active platform
- **THEN** the launch plan executes that path without an unnecessary shell

#### Scenario: Platform shim resolves through its interpreter
- **WHEN** a declared command resolves to a platform script or command shim that requires an interpreter
- **THEN** the launch plan names that interpreter and includes it in the execution identity

### Requirement: Contracts remain platform-neutral
Target contracts MUST declare structured commands and arguments and MUST NOT embed platform-specific shell bridges as the normal portability mechanism.

#### Scenario: One contract runs on supported platforms
- **WHEN** the same target-declared command is executed on Windows and a Unix-like platform
- **THEN** platform adapters produce appropriate launch plans without changing target contract semantics

#### Scenario: Shell string workaround is rejected
- **WHEN** a generated contract hard-codes a platform bridge that belongs to runtime resolution
- **THEN** contract validation reports the portability violation

### Requirement: Resolved launch identity controls receipt reuse
Receipt freshness SHALL include the resolved launch plan, executable/interpreter content identity, environment identity, target inputs, and command arguments.

#### Scenario: Same resolved plan may reuse success
- **WHEN** the frozen request, inputs, environment, command, resolved paths, interpreter, and tool content identities match a terminal-success receipt
- **THEN** the owner may reuse that exact receipt

#### Scenario: Resolved executable change stales receipt
- **WHEN** command lookup resolves to a different shim, interpreter, executable, or content identity
- **THEN** the previous receipt is stale even when the requested command token is unchanged

### Requirement: Timeout cleanup is terminal evidence
On timeout, cancellation, or interruption, the launcher SHALL terminate the full descendant process tree and SHALL record cleanup facts before another owner can start.

#### Scenario: Cleanup is confirmed
- **WHEN** the launcher confirms zero descendants after termination
- **THEN** it records a failed timeout receipt with retry guidance and permits later controlled execution

#### Scenario: Cleanup cannot be confirmed
- **WHEN** any descendant may remain after termination attempts
- **THEN** the disposition is `cleanup-unconfirmed`, no success receipt is published, and subsequent equivalent owner execution is blocked
