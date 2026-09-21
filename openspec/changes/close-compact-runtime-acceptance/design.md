## Context

The proposal is implemented over a dirty but identity-pinned source worktree
that already contains historical OpenSpec changes and a published `0.7.7`
release. The audit package records the exact C00-C13 order, current false
positive self-check behavior, consumer import failure, protected inventories,
and source/release boundaries. The design must repair the compact runtime while
keeping author maintenance, consumer operation, installation, and publication
as separate claims.

## Goals / Non-Goals

**Goals:**

- Rebuild exact declared-check evidence and execution accounting at the actual
  process-start boundary.
- Make the consumer projection independently importable and executable with a
  minimal explicit closure and transactional installation.
- Replace static self-check presence tests with real target-owned self-runner
  groups and current case identities.
- Preserve target-domain authority, direct-current semantics, and exact
  blocked/not-run states through final verification.

**Non-Goals:**

- Reopening or mass-checking historical OpenSpec changes.
- Deleting historical tags/releases, changing the user HOME installation, or
  publishing a candidate during this change.
- Restoring the retired platform, compatibility readers, migrations, aliases,
  root-search, or generic fallback routes.
- Interpreting target-domain meaning inside SkillGuard or treating narrow CI as
  full runtime/installation evidence.

## Decisions

1. **One named change owns the closeout.** The repository-local change is
   `close-compact-runtime-acceptance`; historical changes stay immutable. The
   same-named FlowGuard change coordinates cross-Guard journeys but never shares
   receipts or execution owners.

2. **Current identity is frozen before execution.** C00 records source HEAD,
   tracked bytes, interpreter, clean workspace, package identity, and remote
   boundary. Any mismatch blocks and requires a new prepared identity.

3. **Denominator is rebuilt from current declarations.** A typed immutable
   snapshot owns the complete required-check set. Empty, duplicated, foreign,
   or rehashed-invalid sets block before process launch. This preserves the
   check universe instead of making the denominator fit observed output.

4. **Counts are invocation-local at process start.** A successful OS process
   creation increments the owner execution count in its invocation context.
   Shared attempt directories are evidence output only and cannot be used to
   infer another request's count. Every failure path persists started state and
   verifies descendant cleanup.

5. **Consumer closure is explicit and clean.** The minimal runtime import
   closure is selected from source dependencies and tested with a clean
   interpreter that exposes only staged scripts. Author code, FlowGuard,
   editable finders, old `run_store`, and root-search are excluded rather than
   reintroduced as a compatibility layer.

6. **Self-audit is target-owned execution.** The admission, execution, and
   release groups run exact declared cases and record their collected multiset,
   setup/call/teardown, source, contract, and owner identities. A static
   `is_file` check cannot satisfy any group.

7. **Protection inventory is the denominator.** C08 reconciles retained,
   ported, and retired nodes, including the additional mappings found in the
   audit. Counts are evidence, not deletion targets; every missing or ambiguous
   owner blocks.

8. **Freeze precedes final validation and packaging.** C10 freezes source,
   contract, test, toolchain, environment, self-audit, and owner-plan identity.
   C11 runs one final Windows 3.12 full-suite owner; C12 verifies measurements
   and produces a source-safe candidate; C13 remains a later authorized
   publication step.

## Risks / Trade-offs

- [Dirty parallel worktree] → use only the declared isolated worktree and
  record ownership before each batch; do not reset or stage unrelated changes.
- [Minimal closure omits a needed runtime module] → test import and target
  operation in the clean interpreter, then add only the exact current source
  dependency and re-run closure checks.
- [Concurrency obscures ownership] → use invocation-local state and retain
  immutable attempt receipts; never recompute counts from a shared directory.
- [Legacy tests encode retired API shapes] → use the audited fixed-edit and
  protection disposition tables; do not restore the retired platform.
- [Remote branch or release moves] → record the exact mismatch as blocked and
  stop publication; never force-push or overwrite an existing release.

## Migration Plan

1. Execute C00 and create the prepared identity.
2. Implement and validate C01-C03 in the SkillGuard owner scope; coordinate
   FlowGuard C04-C07 without shared files or receipts.
3. Execute C08 collection/protection migration and CI denominator repair only
   after both compact owner scopes are stable.
4. Execute C09 journeys and measurement fixture collection.
5. Execute C10 self-audit/current-plan acceptance and delivery freeze; if any
   identity changes, repeat preparation and freeze instead of reusing evidence.
6. Execute C11 once, then C12 read-only verification and package generation.
7. Leave C13 blocked until explicit future patch publication authorization and
   remote preconditions are confirmed.

\n