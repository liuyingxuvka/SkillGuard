## Context

The author source keeps `.skillguard/**` beside the target-owned skill files,
but graduation copies only the target-owned files. `check-skill` currently uses
one global heading tuple that includes `SkillGuard Maintenance`; that heading
therefore leaks an author requirement into the consumer entrypoint.

The existing current-runtime-authority model already owns the rule that a
consumer cannot carry SkillGuard prompts or control state. This repair extends
that owner instead of adding a parallel model.

## Goals / Non-Goals

**Goals:**

- Make `check-skill` validate the standalone target contract that consumers
  actually receive.
- Keep all author-maintenance requirements under author-only authority.
- Reject consumer entrypoints that instruct ordinary users or agents to use
  SkillGuard.
- Prove the corrected behavior with focused tests and the existing FlowGuard
  owner.

**Non-Goals:**

- Relax frontmatter, target workflow, hard-gate, output, safety, reference, or
  current author-contract checks.
- Add a mode, fallback, compatibility reader, or optional alternate section
  set.
- Move author contracts into the consumer distribution.

## Decisions

1. `REQUIRED_SKILL_SECTIONS` will contain only target-owned consumer sections.
   `SkillGuard Maintenance` is removed outright; it is not made conditional.
   Conditional acceptance would create two successful target formats and a
   continuing maintenance burden.
2. Author source currentness remains enforced through the exact
   `.skillguard/contract-source.json`, compiled contract, check manifest, and
   author repository policy. A consumer heading is not evidence for those
   authorities.
3. A regression fixture will build a current author contract around a
   consumer-clean `SKILL.md` and run the real `check-skill` command.
4. The current-runtime-authority model gains one field and one known-bad
   scenario for an author-maintenance section in a consumer prompt.

## Risks / Trade-offs

- A malformed author repository could omit author instructions from its policy
  while the target static check still passes. → `maintainer-audit` and the
  exact contract trio remain the author-side gates.
- Existing fixtures may have unnecessary maintenance sections. → They may
  remain as rejection/history material, but no current success requirement
  depends on them.
- Installed SkillGuard may remain stale after source repair. → Rebuild the
  frozen maintainer projection, activate transactionally, and re-run an
  installed check against a clean external target.

## Migration Plan

1. Change the static required-section set and add the focused regression.
2. Extend and run the existing FlowGuard model.
3. Run affected SkillGuard tests, compile/self-check the author contract, then
   run the single final full validation.
4. Transactionally install the current maintainer projection.
5. Re-run the FlowGuard and ResearchGuard external targets that exposed the
   defect.

Rollback restores the previous installed maintainer projection. Source rollback
is not a runtime compatibility path.

## Open Questions

None.
