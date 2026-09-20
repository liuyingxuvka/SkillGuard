---
name: skillguard
description: Maintain explicitly registered SkillGuard source contracts, evidence, installation and release boundaries.
---

# SkillGuard

SkillGuard is an author-side contract and evidence tool. It is not a consumer
runtime dependency and it does not load or execute a FlowGuard model. Use it
only when the repository explicitly declares a SkillGuard maintainer source,
maintenance unit, member identity and private evidence root.

The target owns its domain route, semantics, fixtures, native checks,
completion criteria and result. SkillGuard owns only deterministic contract
identity, route admission, check execution, evidence freshness, installation
parity and release-boundary reporting. Reports, logs, progress notes and old
receipts never refresh source authority.

## Public operations

The only public operations are:

- `read`: read the current explicit contract and accepted result. This is
  side-effect free and starts zero producers.
- `change`: select from declared facts, execute only the selected declared
  checks, and atomically accept the result when every required oracle passes.
- `release`: verify one accepted current result and expose release evidence.
  Installation and Git publication remain separate transactions.

Use the script with fixed arguments:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py --help
python .agents/skills/skillguard/scripts/skillguard.py read --root <root> --request <request.json> --json
python .agents/skills/skillguard/scripts/skillguard.py change --root <root> --request <request.json> --json
python .agents/skills/skillguard/scripts/skillguard.py release --root <root> --request <request.json> --json
```

Legacy command names, `--profile`, `fast`, `focused`, and `full` are rejected;
they do not forward to another handler and they produce no producer or write.

## Current contract

The single source is `.skillguard/contract-source.json` with
`schema_version: skillguard.skill_contract.v3`. It declares only:

`inputs`, `routes`, `steps`, `obligations`, and `checks`.

Each route contains a `choice_group`, finite exact-equality `when` predicates,
step IDs and obligation IDs. Each check contains its real command, argument
list, input IDs and expected oracle. There is no keyword score, similarity,
first-match fallback, model path, global prompt, portfolio capability or
fragment authority. The compiled contract and check manifest are deterministic
derived records, never a second hand-written source.

Route admission requires explicit request facts. Missing facts, no route,
ambiguous same-group matches and unknown routes block before any producer.
Steps are consumed once in the selected decision; a failed check never causes
route reselection. Manual judgment is labelled judgment evidence and is never
converted into a hard execution pass.

## Evidence and installation boundary

Freeze one maintenance unit, exact checks, input identities, dependencies,
toolchain and one execution owner before running a change. A current accepted
result may be reused only when those identities and the request match exactly.
Missing, stale, duplicate, foreign, failed, skipped, timed-out, cancelled or
cleanup-unconfirmed evidence blocks. After a timeout or cancellation, confirm
the entire descendant process tree is gone before accepting evidence.

Installation consumes the frozen installation projection only. It is a
transaction with a staging directory, parity check, rollback on failure and an
immutable installation receipt; it never runs a self-audit as a hidden side
effect. Source, installed tree, Git branch and release artifact are reported
separately.

## Claim boundary

Passing `read`, `change` or `release` proves only the explicitly selected
contract and evidence scope. It does not prove every future AI session will
invoke SkillGuard, target-domain quality, Azure/production deployment, or
remote GitHub state. Final reports must state `evidence`, `failures`,
`blockers`, `skipped_checks`, `residual_risk`, `producer_count` and
`claim_boundary`.
