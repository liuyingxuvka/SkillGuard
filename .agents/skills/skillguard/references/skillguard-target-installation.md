# Standalone consumer installation

This transaction installs one graduated target skill without installing
SkillGuard into that skill.

## Prepare

```text
python scripts/skillguard_consumer_install.py \
  --repository-root <author-repository> \
  --skill-root <author-repository/member-root> \
  --stage-root <isolated-stage/skill-id> \
  --codex-home <CODEX_HOME> \
  --prepare
```

Preparation builds the target-owned consumer projection and audits it before
activation.

The staged tree must not contain:

- `.skillguard/**`;
- SkillGuard imports or command instructions;
- SkillGuard receipt/run/router/Portfolio references;
- author-only tests, fixtures, models, plans, or maintenance notes;
- runtime hidden under `.skillguard/runtime`.

## Activate

```text
python scripts/skillguard_consumer_install.py \
  --repository-root <author-repository> \
  --skill-root <author-repository/member-root> \
  --stage-root <isolated-stage/skill-id> \
  --codex-home <CODEX_HOME> \
  --activate
```

Activation uses one target-owned release identity and a transactional backup.
The installed `consumer-release.json` names only the target skill and its
files; it contains no SkillGuard contract hash, maintenance unit id, or author
receipt.

## Recover or roll back

```text
python scripts/skillguard_consumer_install.py \
  --codex-home <CODEX_HOME> \
  --skill-id <skill-id> \
  --recover

python scripts/skillguard_consumer_install.py \
  --codex-home <CODEX_HOME> \
  --skill-id <skill-id> \
  --rollback <transaction-id>
```

## Claim boundary

This workflow proves the installed tree equals the audited clean consumer
projection. It does not prove the target's domain task succeeded, publication
occurred, or SkillGuard exists on the consumer machine.
