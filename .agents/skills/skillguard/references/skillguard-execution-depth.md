# SkillGuard Declared-Check Execution Depth

SkillGuard answers one generic question: did the target skill complete every check that the target itself declared necessary for this exact request and claim?

It does not decide what the target should protect, which domain failures matter, what an oracle means, or how many checks the target ought to declare. Those decisions belong to the target skill.

## One fixed workflow

There is no optional, advisory, bypass, family-specific, or target-category mode.

1. Read the target's current `depth_profile` and exact `native_check_ids`.
2. Freeze one maintenance-unit inventory containing every member, semantic check, evidence subject, execution owner, evidence domain, and dependency.
3. Execute each owner once or reuse one immutable current terminal-success receipt only inside the same unit with the same complete execution identity and inputs.
4. Reconcile the frozen inventory against results by exact check id, owner id, request fingerprint, disposition, freshness, receipt id, and receipt hash.
5. Block when a result is absent, duplicated, stale, non-terminal, failed, skipped, timed out, cancelled, cleanup-unconfirmed, or bound to another request or owner.
6. Issue one declared-check execution receipt only when the unresolved-check set is empty and the enrolled provider runtime is current.
7. Require the requested closure to consume that exact receipt.

## Target ownership boundary

A target may declare one check or many checks. SkillGuard treats both shapes identically.

- The target owns route meaning, check meaning, fixtures, domain oracles, internal quality thresholds, and its safe claim.
- SkillGuard owns inventory equality, single execution ownership, receipt completeness, request/input freshness, runtime enrollment, and closure consumption.
- SkillGuard never branches on a target name or family and never infers semantics from a check id.
- A target-specific pattern becomes mandatory only because the target placed every member of that pattern in its own declared inventory.
- A different maintenance unit never satisfies the target's obligation, even when it runs the same command over the same files.

This separation lets an ordinary one-way skill use its natural verification without inventing an artificial second case, while a target with several native checks still cannot omit one and pass.

## Current profile

The current profile is `skillguard.depth_profile.v2` and permits only:

- target, profile, integration, native owner, and native route identity;
- a non-empty exact `native_check_ids` inventory;
- fixed `enforcement_level: enforced` and `skillguard_adds_domain_route: false`;
- closure profiles that must consume the receipt;
- enrolled provider runtime identity, capabilities, and readiness check ids;
- a bounded claim statement.

Former target-domain policy fields and any target classification are invalid current input. There is no alternate reader or fallback.

## Receipt boundary

`CONTRACT_DEPTH_PASS` means the declared inventory is structurally valid and bound to known current checks and owners. It does not prove execution.

`EXECUTION_DEPTH_PASS` means every frozen declared check has exactly one current terminal-success result for the same maintenance unit, member, evidence subject, semantic check, request, and runtime, with an immutable receipt identity and no unresolved check. It does not prove claims beyond the target's own check boundaries.

This receipt is author-maintenance evidence. It is not copied into the
graduated consumer and is not a consumer runtime prerequisite.

For scheduled production, the receipt must additionally bind the exact current installation receipt and installed runtime identity. Capability-validation evidence cannot substitute for scheduled-production authority.

## Conditional closure

Conditional targets retain their own route and branch contract. A native terminal receipt binds the exact declared-check receipt. Verifier-owned applicability evidence may mark a declared obligation not applicable only where the target's current branch contract allows it. An intermediate authorization is non-terminal and cannot be promoted to the fixed `enforced` terminal completion.

## Non-guarantees

SkillGuard does not prove future AI behavior, factual correctness, or that a target's own declared checks are a perfect domain specification. It proves only that the target's current declared verification inventory was executed and reconciled without hidden gaps for this exact request and claim.
