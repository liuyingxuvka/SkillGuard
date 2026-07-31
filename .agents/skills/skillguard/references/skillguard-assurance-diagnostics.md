# SkillGuard Assurance Diagnostics

Use this route only after the current author contract trio and a hashed closure
evaluation already exist. It explains supplied authority; it is not a second
AssuranceGraph, validation owner, freshness engine, or closure path.

## Input authority

The current input schema is
`skillguard.assurance_diagnostic_input.v1`. It binds:

- the validated current compiled contract;
- the matching exact check manifest and content-impact graph;
- one hashed `skillguard_v2_closure_evaluation`;
- the supplied current, missing, failed, blocked, or stale owner receipts;
- an explicit deletion-evaluation budget;
- optional advisory next actions;
- an optional target-authored mutation contract and native receipt.

Reject unknown root fields and former schema names. The compiled contract and
manifest must agree on their check-declaration and impact-graph identities.
The closure assessment hash must replay exactly.

## Blocker basis

Derive blocker atoms from the current manifest and supplied receipts. Each atom
states its owner, semantic check, affected obligations, receipt state,
dependencies, provenance, and advisory next actions. A dependency blocker also
explains obligations of checks that transitively consume it.

Run deterministic deletion over the obligations currently blocked by closure:

- report `subset_minimal` only after every retained atom has a necessity
  witness showing an obligation that becomes unexplained when that atom is
  removed;
- always report `minimum_cardinality_proven: false` unless a future explicit
  exhaustive owner proves otherwise;
- report `bounded_incomplete` when the evaluation budget ends before deletion
  completes, and emit no necessity/minimality claim for the unfinished basis.

The basis is an explanation of the supplied terminal. It does not license that
terminal or replace alternate blocker detail.

## Target-owned mutation evidence

Mutation adequacy is optional and target-owned. SkillGuard consumes it only
when the target declares the current contract schema
`skillguard.target_mutation_contract.v1` with:

- target and check identities;
- non-empty target mutation operators;
- target oracle;
- applicability statement;
- equivalent-mutant disposition;
- threshold;
- exact contract hash.

The native receipt must use
`skillguard.target_mutation_receipt.v1`, bind the same target/check/contract,
replay its receipt hash, and explicitly be current. SkillGuard copies the
target result (`pass`, `fail`, `blocked`, or `not_run`) and target metrics
without recomputing the score or reinterpreting the domain judgment.

Missing declaration or receipt is `not_run`; incomplete, mismatched, stale, or
invalid evidence is `blocked`. Ordinary tests never imply mutation adequacy.

## Forbidden actions

Diagnostics never:

- execute or resume an owner;
- write run state or evidence;
- issue or verify closure on a new authority path;
- turn a blocked or failed closure into pass;
- remove, relax, auto-scope, or otherwise weaken an obligation.

An advisory action proposing obligation weakening is explicitly rejected.

## Command

```powershell
python .agents/skills/skillguard/scripts/skillguard.py assurance-diagnostics --input <current-input.json>
```

The command may write only to the existing bounded report destinations when an
output path is supplied. A successful command means the diagnostic projection
was derived; it never means the source closure passed.
