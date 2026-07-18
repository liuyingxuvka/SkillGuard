# Private maintenance-unit Portfolio

Portfolio is an author-side inventory of independently maintained units. It is
not a shared test-results database and is never part of a consumer skill.

## Core rule

Each maintenance unit proves itself.

- Unrelated units do not read one another's tests or receipts.
- Affected units rerun their own checks.
- Unaffected units remain current because no component edge reaches them, not
  because they received a reuse ticket.
- Graduation of one unit consumes no earlier unit's proof.

The retired reuse-ticket route and prior-graduate gate have no current success
path.

## Current states

- `pending`: author scope exists but validation has not closed.
- `revalidation_required`: a mapped functional component changed.
- `current`: the named unit's own complete current evidence passed.
- `blocked`: structure, identity, evidence, cleanup, or distribution is
  incomplete.
- `excluded` / `supporting`: non-active lifecycle records.

## Workflow

1. Build the current registry directly from one reviewed scope with
   `build-current-portfolio-registry`. No old green state is carried forward.
2. Run `audit-portfolio` to inspect unit structure and per-unit currentness.
3. After a SkillGuard functional change, run `mark-portfolio-impact`. Exact
   component edges move only affected targets/members to
   `revalidation_required`.
4. Run `prepare-portfolio-run` for one target unit. Freeze its complete job
   plan and exact target identity.
5. Run `execute-portfolio-run` for that frozen plan.
6. Capture required installed/scheduled production evidence for each member of
   that same unit with `capture-portfolio-production-revalidation`.
7. Run `assemble-portfolio-run`. It replays only the prepared unit's jobs,
   member bindings, installed projection, and closure.
8. Run `graduate-portfolio --write` for that unit. It updates only that unit
   and issues a receipt whose `prior_evidence` is empty by contract.
9. Audit the registry again.

## Impact rules

Functional source, contract, configuration, toolchain, or policy components
may invalidate the units explicitly connected to them.

Reports, receipts, logs, timestamps, progress, and installation bookkeeping
are evidence outputs. They do not create functional edges or trigger their own
producer.

An unmapped or ambiguously owned component blocks impact planning instead of
falling back to “rerun every skill.”

## Suite rule

A deliberately inseparable suite may be one maintenance unit with several
members. Member invalidation remains visible until the full suite's own
graduation closes it. This is same-unit composition, not cross-unit sharing.

## Privacy and distribution

Keep Portfolio registry, workspace paths, receipts, and local repository
metadata private on the maintainer computer. Never include them in a consumer
distribution, ordinary project, public skill package, or consumer release
identity.

## Claim boundary

Portfolio currentness proves only the named unit's recorded evidence under the
named author-side SkillGuard identity. It does not make another unit current,
prove installation or publication unless separately checked, or guarantee
future AI behavior.
