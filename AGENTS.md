# Repository Agent Policy

This repository contains SkillGuard, a public tool and skill package for maintaining Codex skills. Agents and contributors should keep changes scoped, evidence-based, and safe for a public open-source repository.

## Working Scope

- Keep edits limited to the files required by the current task.
- Preserve existing user or peer-agent work. Do not overwrite a file without first inspecting the current content.
- Do not create implementation directories, release artifacts, credentials, remotes, or repository history unless the current task explicitly owns that work.
- If a task is limited to documentation or metadata, do not use it to add scripts, schemas, tests, fixtures, package code, or generated outputs.

## Multi-Agent Coordination

- Assume another agent may be editing the same repository.
- Recheck target files immediately before writing.
- If an unexpected file appears, treat it as user or peer-agent work and either preserve it or report a concrete conflict.
- Avoid broad formatting, cleanup, dependency installation, or generated rewrites unless the task explicitly requires them.

## Validation Expectations

- Run the narrowest practical checks for the files you changed.
- For metadata, parse machine-readable files with a real parser when available.
- For documentation, verify required sections, commands, status meanings, limitations, and claim boundaries directly from current file content.
- Report skipped validation as skipped. Do not describe a check as passing unless it actually ran against current files.

## Privacy And Public-Safety Boundaries

- Do not commit credentials, secrets, tokens, API keys, private keys, private task payloads, internal coordination records, private transcripts, local absolute paths, user-specific filesystem details, or private workspace transcripts.
- Use public, portable paths and examples in documentation.
- Keep machine-specific setup notes out of tracked files unless they are intentionally documented as examples.

## Claim Boundaries

- Do not claim that SkillGuard is fully implemented, validated, released, published, or integrated with external services unless current repository evidence proves that exact claim.
- Do not claim that SkillGuard guarantees Codex activation, AI correctness, fully automated semantic judgment, or one-click migration.
- Keep parent or suite summaries tied to child evidence. A high-level status must not hide stale, missing, blocked, or unreviewed child work.

## Packaging Boundaries

- Keep version fields synchronized when editing release metadata.
- Do not add CLI entry points, package discovery rules, dependencies, or build configuration for files that do not yet exist.
- Prefer conservative metadata until implementation, validation, and release nodes create the corresponding artifacts.

<!-- BEGIN FLOWGUARD PROJECT RULES -->
## FlowGuard Project Rules

This project uses FlowGuard for non-trivial maintenance, feature work, bug
fixes, refactors, tests, release work, project upgrades, and evidence-sensitive
process changes.

FlowGuard repository:
https://github.com/liuyingxuvka/FlowGuard

Project FlowGuard record:
- Manifest: `.flowguard/project.toml`
- Machine log: `.flowguard/adoption_log.jsonl`
- Human log: `docs/flowguard_adoption_log.md`

Current adoption record:
- FlowGuard package version: `0.52.2`
- FlowGuard schema version: `1.0`

Before non-trivial work:
1. Verify the real package:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`
2. Check the installed package version:
   `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`
3. Audit the project record:
   `python -m flowguard project-audit --root .`
4. Compare the installed version with `.flowguard/project.toml`.
5. If the installed version is newer, run:
   `python -m flowguard project-upgrade --root .`
   This updates the project record and scans existing FlowGuard artifacts,
   model evidence, tests, docs, and guidance for deterministic upgrades into
   the current FlowGuard shape. Use `--records-only` only when intentionally
   scoping out artifact/model/test upgrade scanning.
   Then rerun affected models/tests before broad confidence and record the result.
6. If the installed version is older than the project record, stop and upgrade
   the local FlowGuard toolchain before claiming FlowGuard confidence.

FlowGuard runtime guidance is latest-schema-first: old artifacts may be
detected and upgraded at project/tool boundaries, but normal route logic should
not preserve long-lived compatibility branches for obsolete fields, aliases, or
wrappers.

Default replacement means dispose the old path, old field, alias, wrapper, or
fallback unless compatibility or preservation is explicitly requested. If
compatibility is explicit, record the preserved surface, compatibility intent,
and current evidence; otherwise delete, block, migrate, delegate, repair, or
scope it out with a concrete reason.

Field-bearing work should use or update FieldLifecycleMesh: high-level behavior
models include behavior-bearing fields, while child/leaf field rows account all
discovered fields and record owner, readers, writers, projection, lifecycle,
and old-field disposition.

UI runnable claims and file/work-package claims need current UI click-through
or artifact-payload evidence gates before broad done/release confidence.

Non-trivial rough-plan discussion, multi-skill/tool workflow setup, staged
execution, install/sync, release/archive/publish, post-change owner scans, and
final process claims enter `flowguard-development-process-flow` first as the
development-process simulator. Record `plan_detailing`, `agent_workflow`, and
`execution_freshness` modes; delegate to PlanDetailing or
AgentWorkflowRehearsal only when explicit or simulator-selected.

After non-trivial FlowGuard-managed work, let DevelopmentProcessFlow consume
post-change scan signals for changed artifacts, skipped routes, stale evidence,
open obligations, or split/reduction pressure. The scan output routes each gap
to the owning specialist, such as Model-Test Alignment, Architecture
Reduction, StructureMesh, ModelMesh, TestMesh, or AgentWorkflowRehearsal.

Do not create a fake local FlowGuard replacement. Do not claim full FlowGuard
completion from an AGENTS/manifest/log update alone; executable model checks,
tests, replay, and closure evidence still need to be current for the claim.
<!-- END FLOWGUARD PROJECT RULES -->
