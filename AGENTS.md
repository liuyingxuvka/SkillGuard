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
