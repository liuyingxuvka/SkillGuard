# SkillGuard author-side supervisor

This reference defines the author-only ownership boundary for the current
SkillGuard contract. It does not define target-domain meaning and it does not
load or execute a FlowGuard model.

Before a current source change, freeze exactly one maintenance unit, its member
ids, declared checks, evidence subjects, dependency order, private evidence
root, toolchain, and one execution owner per check. The current source of
truth is `.skillguard/contract-source.json`; its compiled contract and check
manifest are derived outputs. Missing, duplicate, foreign, stale, malformed,
failed, skipped, timed-out, cancelled, or cleanup-unconfirmed evidence blocks
the current result.

The only public operation facts are `read`, `change`, and `release`:

```text
read    -> inspect the accepted current result; zero producers and zero writes
change  -> execute the selected current owner closure and accept by CAS
release -> verify the declared release scope and fill only missing owners
```

Each operation must bind its request, input bytes, dependency identities,
toolchain, environment, maintenance unit, owner, and evidence subject. A
parent summary cannot replace a leaf result. A result from another maintenance
unit cannot be reused, even when the command text is identical.

The supervisor may validate target-owned check identity and terminal evidence,
but it does not decide whether a target check is sufficient for the target's
domain. The target owns its behavior, judgment, fixtures, actions, and native
checks. SkillGuard reports the exact evidence boundary and keeps unknown,
blocked, not-run, skipped, stale, and failed states visible.

Read is strictly side-effect free: it does not compile, create a run
directory, acquire a lease, launch an owner, write a receipt, refresh a
router, install a consumer, or publish a release. Change and release stop on
source drift, CAS conflict, missing owners, failed cleanup, or incomplete
evidence.

Direct-current replacement is the only supported maintenance format. There is
no compatibility reader, migration command, alias, dual authority, Portfolio
bridge, old route catalog, or fallback success path. Retired inputs return a
typed rejection and remain unread.

The author entrypoint is:

```powershell
python <installed-skillguard>/scripts/skillguard.py <read|change|release> `
  --root <author-root> --request <request.json> --json
```

The installed skill directory supplies the script; `--root` is the separately
selected maintained author repository. Installation, global-router currentness,
Git, tags, and publication are separate claims and require their own evidence.
