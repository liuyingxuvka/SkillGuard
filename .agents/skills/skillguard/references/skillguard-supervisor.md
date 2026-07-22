# SkillGuard author-side supervisor

The supervisor executes one explicitly maintained unit's declared workflow. It
does not reimplement the target skill, and it never writes into an ordinary
business project by default.

## Required author context

Before compilation, run claim, receipt lookup, or directory creation, the
caller must provide:

- an explicit `skill_maintainer_source` repository;
- one `maintenance_unit_id`;
- one declared member skill;
- an author `run_state_root`;
- an author `owner_evidence_root`;
- the separate task-data `target_root`.

The run and evidence roots must belong to the author-maintenance workspace.
They have no fallback to `target_root`, the consumer skill, the current working
directory, or a user's ordinary project. Missing or invalid author context
blocks with zero writes.

## Command

```text
python scripts/skillguard_supervise.py <skill-root> <packet.json> \
  --repository-root <author-repository> \
  --target-root <task-data-root> \
  --run-state-root <private-author-run-root> \
  --owner-evidence-root <private-author-evidence-root>
```

The maintained source contains the current author contract trio and declared
FlowGuard model. Compilation regenerates only the compiled author contract and
check manifest.

## Packet boundary

The packet selects routes already declared by the target and supplies only
task inputs, witnessed observations, declared judgments, or contract-authorized
skip evidence. It cannot assert pass status, invent a receipt, change the
maintenance unit, change an execution owner, or broaden the closure.

Conditional targets use the target's own branch contract. An intermediate
authorization is non-terminal; final closure consumes the exact target-native
terminal and current declared-check evidence.

## Evidence authority

- `hard` evidence comes from a stored, executed, passing declared check.
- `witnessed` evidence binds a concrete executor, target, input, output, and
  limitations.
- `judged` evidence binds a declared rubric, evaluator, input, conclusion,
  limitations, and confidence boundary.
- `skip` is legal only for a model-declared optional step after its condition
  and verifier evidence pass.

Every declared check projection includes maintenance unit, member, evidence
subject, semantic check, execution owner, covered obligations, and evidence
domain. Its producer receipt separately binds the owner, request, inputs,
dependencies, toolchain, environment, and policy. Keeping these identities
separate lets one explicitly declared same-unit producer satisfy several exact
semantic projections without making the projections interchangeable.

One exact terminal-success receipt may be reused only inside the same
maintenance unit under that complete identity. A foreign-unit receipt or
dependency blocks before process launch and cannot be projected into closure.

SkillGuard never infers producer sharing from command, argument, name, or
output similarity and never decides that a target's declared capability should
be deeper. The target skill owns those declarations; the supervisor verifies
their exact execution and evidence only.

The unit has one canonical owner-evidence root. Complete streams are stored as
deterministic compressed objects with separate logical and storage hashes.
`evidence-audit` and `evidence-gc-plan` are read-only; apply quarantines an
exact current plan, and purge is a separate quarantine-only operation gated by
current and release-pinned replay.

## Execution and cleanup

The supervisor:

1. freezes the unit's complete check inventory;
2. resolves current same-unit receipts;
3. executes only missing owners;
4. records immutable results and sidecars;
5. confirms zero descendant processes after timeout, cancellation, or
   interruption;
6. reconciles every declared check exactly;
7. derives only the fixed `enforced` closure.

Missing, duplicate, failed, skipped, stale, timed-out, cancelled,
cleanup-unconfirmed, non-terminal, wrong-member, wrong-subject, or wrong-unit
evidence blocks.

## Consumer boundary

Supervisor packets, run state, receipts, compiled contracts, check manifests,
and author roots are not consumer files. A graduated consumer uses its own
`SKILL.md`, scripts, references, assets, runtime, and native checks without
calling this supervisor or locating SkillGuard.

## Claim boundary

A supervisor result proves only the named maintenance unit's exact author-side
run and bounded closure. It does not prove another unit, consumer installation,
publication, future AI behavior, or the correctness of the target's own domain
specification.
