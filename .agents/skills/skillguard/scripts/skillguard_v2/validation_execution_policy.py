"""Canonical prompt projection for validation execution ownership."""

from __future__ import annotations


VALIDATION_EXECUTION_POLICY_ID = "skillguard.validation_execution_ownership.current"
SKILLGUARD_ACTIVATION_POLICY_LINES = (
    "- Creating, updating, directly rewriting, installing/synchronizing, or releasing an explicitly registered maintained skill source requires SkillGuard author-side supervision; no migration or compatibility route exists.",
    "- Covered skill maintenance uses direct current replacement. Do not add a compatibility reader, fallback, migration or upgrade command, converter, alias, renewal path, dual manifest, or parallel authority. An ordinary software historical reader is allowed only when an explicit requirement names the old document/data/interface and FlowGuard records its bounded owner and claim boundary.",
    "- Ordinary use of an installed consumer skill for its domain work does not start SkillGuard maintenance or validation and must not require SkillGuard files, imports, commands, receipts, or router state.",
    "- SkillGuard supervises the author-side frozen owner plan, receipts, affected-only revalidation, clean consumer projection, and closure; the target skill retains its domain actions, judgment, and native-check authority.",
)
VALIDATION_EXECUTION_POLICY_LINES = (
    *SKILLGUARD_ACTIVATION_POLICY_LINES,
    "- Before validating one maintenance unit, freeze its unit id, member ids, exact semantic checks, evidence subjects, covered obligations/domains, dependency order, private receipt root, and exactly one execution owner per check; missing, duplicate, foreign-unit, or cyclic ownership blocks execution.",
    "- Reuse one immutable terminal-success receipt only inside the same maintenance unit when unit, member, evidence subject, semantic check, owner, request, inputs, dependencies, toolchain, and environment are all exact. A different unit must execute and own its own evidence even when command text and inputs look identical.",
    "- Consumer distributions contain no SkillGuard receipt reference or execution-owner projection. They run their target-owned checks directly when their own workflow requires them.",
    "- Compile the complete maintained inventory into exact content components before validation. A change invalidates only owners and projections that explicitly consume its changed component; an unmapped or ambiguous file blocks instead of falling back to run-all.",
    "- Treat maintained test, code, contract, configuration, toolchain, and policy changes as freshness inputs only through those exact component edges. Reports, receipts, progress logs, checkboxes, and other runtime outputs are evidence outputs and must not refresh source authority or trigger their own validation.",
    "- Installation consumes only the frozen `projection:installation`; source-only tests, fixtures, models, and notes do not make an installation stale. A read-only installation currentness check never launches smoke or another validation owner.",
    "- Treat `--resume` as an execution command that may run missing owners; it is never a read-only receipt audit, and a receipt consumer must not invoke it.",
    "- Start exactly one final full validation for the maintenance unit only after its source, toolchain, and impact-plan identities are frozen, under one explicit execution owner. Other maintenance units and consumers do not consume that parent receipt.",
    "- After any launcher timeout, cancellation, or interruption, confirm the entire descendant process tree count is zero before accepting evidence or starting another owner; `cleanup-unconfirmed` results are invalid and non-reusable.",
    "- Never use a Windows Scheduled Task, background resume, or unattended retry script to run full validation or resume a mutable worktree.",
)


__all__ = [
    "VALIDATION_EXECUTION_POLICY_ID",
    "VALIDATION_EXECUTION_POLICY_LINES",
    "SKILLGUARD_ACTIVATION_POLICY_LINES",
]
