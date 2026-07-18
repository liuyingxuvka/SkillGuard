# SkillGuard author-repository adoption

This workflow is only for a repository that authors and maintains skills.
It is not project adoption in the ordinary sense.

## Current author surfaces

- `AGENTS.md` contains one marker-bounded
  `MANAGED SKILLGUARD AUTHOR RULES` block.
- `.skillguard/author-project.json` records the explicit author repository,
  maintenance units, and member skills.

Both surfaces are author-side control material. They must never be copied into
a consumer skill or an unrelated project.

## Preconditions

Before `maintainer-adopt` writes anything, every declared member must already
have a current `.skillguard/contract-source.json` that proves:

- `repository_role: skill_maintainer_source`;
- a non-empty `maintenance_unit_id`;
- the member's `skill_id` is present in `member_skill_ids`;
- the skill path is inside the author repository.

Missing or ambiguous preconditions block before the AGENTS file or manifest is
written.

## Commands

```text
python scripts/skillguard.py maintainer-adopt \
  --root <author-repository> \
  --managed-skill "<skill-path>|<native-owner>"

python scripts/skillguard.py maintainer-audit \
  --root <author-repository>
```

`maintainer-adopt` writes the one current author shape directly. It does not
convert an older project-adoption manifest.

`maintainer-audit` is read-only. It checks the marker block, manifest hash,
repository role, unit/member bindings, paths, and native owners.

## Ordinary-project zero-write rule

If the root is not an explicit skill-author repository, SkillGuard must:

- create no `.skillguard` directory;
- modify no `AGENTS.md`;
- create no receipt, router, Portfolio, or run state;
- return a blocker explaining that ordinary projects are outside the adoption
  boundary.

## Claim boundary

Author adoption proves only that a source repository carries current
SkillGuard maintenance instructions. It does not prove a member passed its
checks, graduated, was installed, or will behave correctly in future use.
