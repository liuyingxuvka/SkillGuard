"""Canonical prompt projection for validation execution ownership."""

from __future__ import annotations


VALIDATION_EXECUTION_POLICY_ID = "skillguard.validation_execution_ownership.current"
SKILLGUARD_ACTIVATION_POLICY_LINES = (
    "- Creating, updating, directly rewriting a non-current target, installing/synchronizing, or releasing a maintained skill requires SkillGuard maintenance supervision; no migration or compatibility route exists.",
    "- Covered skill maintenance uses direct current replacement. Do not add a compatibility reader, fallback, migration or upgrade command, converter, alias, renewal path, dual manifest, or parallel authority. An ordinary software historical reader is allowed only when an explicit requirement names the old document/data/interface and FlowGuard records its bounded owner and claim boundary.",
    "- Ordinary use of an already-installed skill for its domain work does not start SkillGuard maintenance or validation.",
    "- SkillGuard supervises the frozen owner plan, receipts, affected-only revalidation, installation projection, and closure; the target skill retains its domain actions, judgment, and native-check authority.",
)
VALIDATION_EXECUTION_POLICY_LINES = (
    *SKILLGUARD_ACTIVATION_POLICY_LINES,
    "- Before multi-skill validation starts, freeze one task-level validation plan in the existing verification contract or TestMesh: list every exact check, covered obligation and evidence domain, dependency/order, persistent receipt root, and exactly one primary execution owner; missing, duplicate, or cyclic ownership blocks execution.",
    "- Before executing a listed check, resolve its exact owner receipt from the frozen execution identity and inputs. Reuse only a current immutable terminal-success receipt; consumer skills verify and project that receipt and must not carry or rerun the owner's command.",
    "- Compile the complete maintained inventory into exact content components before validation. A change invalidates only owners and projections that explicitly consume its changed component; an unmapped or ambiguous file blocks instead of falling back to run-all.",
    "- Treat maintained test, code, contract, configuration, toolchain, and policy changes as freshness inputs only through those exact component edges. Reports, receipts, progress logs, checkboxes, and other runtime outputs are evidence outputs and must not refresh source authority or trigger their own validation.",
    "- Installation consumes only the frozen `projection:installation`; source-only tests, fixtures, models, and notes do not make an installation stale. A read-only installation currentness check never launches smoke or another validation owner.",
    "- Treat `--resume` as an execution command that may run missing owners; it is never a read-only receipt audit, and a receipt consumer must not invoke it.",
    "- Start exactly one final full validation only after source, toolchain, and impact-plan identities are frozen, under one explicit execution owner; later consumers project its immutable parent receipt and never launch another equivalent full run.",
    "- After any launcher timeout, cancellation, or interruption, confirm the entire descendant process tree count is zero before accepting evidence or starting another owner; `cleanup-unconfirmed` results are invalid and non-reusable.",
    "- Never use a Windows Scheduled Task, background resume, or unattended retry script to run full validation or resume a mutable worktree.",
)


__all__ = [
    "VALIDATION_EXECUTION_POLICY_ID",
    "VALIDATION_EXECUTION_POLICY_LINES",
    "SKILLGUARD_ACTIVATION_POLICY_LINES",
]
