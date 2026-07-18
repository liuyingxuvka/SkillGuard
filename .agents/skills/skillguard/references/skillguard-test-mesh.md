# SkillGuard maintenance-unit TestMesh

TestMesh plans and aggregates validation for one maintenance unit. It is not a
cross-skill proof network and is never part of a consumer distribution.

## Frozen plan

The plan declares:

- one `maintenance_unit_id`;
- the unit's member skills;
- every semantic check and evidence subject;
- one execution owner per check;
- covered obligations and evidence domains;
- dependency order;
- exact source, configuration, toolchain, and environment inputs;
- one private owner-receipt root.

A foreign-unit owner, dependency, or receipt blocks the plan. Duplicate
semantic ownership is a boundary defect, not a reason to share evidence.

## Execution ownership

`plan_only` computes what is current and what requires execution without
launching a process. The unit's owner runner executes only the frozen missing
owners. `aggregation_only` consumes the unchanged plan and those exact
same-unit receipts.

Same-unit single-flight is allowed only when the full execution identity is
identical. A check in another maintenance unit always owns and produces its
own evidence, even when command text, input hashes, or tools match.

## Affected-only invalidation

Source, test, contract, configuration, toolchain, and policy components stale
only checks and projections that explicitly consume them. Reports, receipts,
logs, timestamps, progress, and status records are outputs and do not trigger
their producer.

Unmapped or ambiguous components block instead of falling back to run-all.

## Final validation

Freeze one final full plan only after the unit's source and toolchain are
stable. Run it under one explicit execution owner. Later readers may verify
the immutable aggregation but may not resume, backfill, or rerun missing
owners.

After timeout, cancellation, or interruption, evidence remains invalid until
the entire descendant process tree is confirmed absent.

## Consumer and provider boundary

Consumers do not receive TestMesh plans, commands, owner receipts, or
aggregation references. Official OpenSpec may supply read-only requirements
context but is never a TestMesh owner, receipt consumer, cache/session bridge,
or maintained target.

## Claim boundary

A passing aggregation proves only the frozen maintenance unit and exact
inputs. It cannot prove another unit, a consumer task, installation,
publication, or future AI behavior.
