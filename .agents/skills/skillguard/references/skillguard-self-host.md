# SkillGuard self-check ownership

SkillGuard self-checks are author-side checks of the current SkillGuard source
and contract. They do not load or execute a FlowGuard model, and they do not
decide target-domain meaning.

The current self-check groups are the three operations declared in
`.skillguard/contract-source.json`: `read`, `change`, and `release`. Each group
has one current owner, an exact case set, current source and contract
identities, and an immutable terminal result. Static file existence, a report,
or a command's exit text cannot replace execution of the declared owner.

Before running a group, freeze the source tree, contract, check manifest,
toolchain, environment, maintenance unit, case set, evidence subjects,
dependencies, and private evidence root. Missing, duplicate, foreign, stale,
skipped, failed, timed-out, cancelled, or cleanup-unconfirmed cases block the
group. A changed source or contract creates a new identity; it does not inherit
the old result.

The supported author entrypoint is the installed current script:

```powershell
python <installed-skillguard>/scripts/skillguard.py <read|change|release> `
  --root <author-root> --request <request.json> --json
```

Use the target-owned native runner and its declared request when a self-check
needs to execute. Keep all run directories, receipts, reports, and terminal
evidence under the explicit private author evidence root. The `read` operation
never compiles, creates a run directory, launches a check, writes a receipt, or
refreshes an installation/router state.

Self-check evidence proves only the current SkillGuard source and its declared
author contract. It does not prove a target skill's quality, consumer
installation, GitHub CI, tag, release, or future behavior.

Direct-current replacement is mandatory. There is no self-host migration,
compatibility reader, alias, old profile, Portfolio bridge, or fallback
success path. A former field or command is a typed rejection and remains
unread.
