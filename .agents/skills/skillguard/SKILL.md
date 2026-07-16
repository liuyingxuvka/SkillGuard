---
name: skillguard
description: "Use when maintaining, reviewing, or releasing Codex skill repositories and skill-like workflows that need inventory, activation-boundary checks, hard validation gates, and evidence-backed status reporting."
---

# SkillGuard

## Purpose

SkillGuard is a guardrail workflow for Codex skill maintenance and skill-release work. It helps agents inspect skill materials, clarify activation boundaries, enforce hard validation gates, and report evidence-backed status without treating unstated assumptions or old evidence as proof.

Use SkillGuard to keep public skill repositories honest about what exists, what was checked, what still needs review, and what must be blocked before release or adoption.

## Entrypoint Scope

This `SKILL.md` is the activation and routing entrypoint for the SkillGuard skill. It is not evidence that every referenced workflow, script, fixture, test, package command, release artifact, git remote, or publication step already exists.

When a task asks for implementation, validation, packaging, publication, or release work, inspect the current filesystem first and report missing local materials as absent or skipped. Do not turn an intended workflow in the README into a completed capability unless current files and fresh checks support that claim.

## Local Material Routing

Start from the current layout instead of assuming generated files exist. SkillGuard can run from the source repository layout or from the installed Codex skill layout.

- In the source repository layout, treat this file as the Codex skill entrypoint under `.agents/skills/skillguard/SKILL.md`; in the installed layout, treat local `SKILL.md` as the entrypoint.
- Use the repository README, pyproject metadata, VERSION file, and AGENTS file for the public repository contract, metadata, version, and contributor boundaries only when the source repository layout is present.
- Use the repository references directory for the maintained SkillGuard standards only when the source repository layout is present.
- Use `assets/schemas/` and `assets/templates/` for local schema and template checks.
- Resolve runtime authority before consuming a contract. Authority is exactly `current` or `blocked`: `current` requires `.skillguard/contract-source.json`, `.skillguard/compiled-contract.json`, the exact `.skillguard/check-manifest.json`, and no former-runtime residual. There is no compatibility, conversion, retirement, renewal, or fallback authority.
- Every covered skill upgrade uses direct current replacement. Former shapes are exact rejection fixtures only; do not add a compatibility reader, fallback, migration or upgrade command, converter, alias, renewal path, dual manifest, or parallel authority. If an ordinary software product truly must read an old document, stored-data format, protocol, or public interface, require an explicit requirement and a bounded FlowGuard-owned reader model; that exception never becomes a skill-runtime path.
- Use `.skillguard/runs/` only for current immutable execution records. Former flat run records and former per-check stub directories may exist only inside exact rejection fixtures; they are never maintenance inputs.
- Use the current depth profile in `.skillguard/contract-source.json` plus immutable target execution receipts when maintained targets must prove that every target-declared check actually completed rather than merely proving contract presence. Stable schema identifiers may retain a version suffix, but they do not create a second route. Follow `references/skillguard-execution-depth.md`.
- Use repository-root `.skillguard/project.json` and the marker-bounded SkillGuard block in AGENTS.md for portable project adoption. Follow `references/skillguard-project-adoption.md`; use `project-adopt` to write the sole current shape from explicit inputs and `project-audit` for read-only checking.
- Use other `.skillguard/` material under the skill directory when the task asks for maintained SkillGuard records, evidence, reports, or self-check material.
- Use the `skillguard-global-router` skill and the `scan-global-skills`, `build-global-registry`, `check-global-registry`, `resolve-global-skill`, `render-global-prompt`, `install-global-prompt`, `check-global-prompt`, and `refresh-global-router` commands when the task is about user-level skill routing, global prompt projection, managed user-level AGENTS prompt blocks, or new-skill onboarding defaults.
- Treat local `scripts/` and `fixtures/` under this skill as evidence only after direct inspection in the current task finds those paths and their current content. Treat repository tests and examples as source-repository evidence only when that layout is present and the paths exist.

Do not cite or require scripts, fixtures, examples, tests, package commands, releases, git remotes, or publication records unless they exist in the current filesystem and were inspected for the current task.

## Entrypoint Acceptance Map

Use this map when checking whether the entrypoint itself is acceptable:

- Frontmatter: the file starts with closed YAML frontmatter containing `name: skillguard` and a specific `description`.
- Activation boundary: `Use When` and `Do Not Use When` define when SkillGuard applies and when it must stay inactive.
- Local routing: `Local Material Routing` identifies the current repository materials and separates existing local paths from absent optional paths.
- Workflow: `Required Workflow` orders inspection, target confirmation, inventory, deterministic checks, judgment checks, evidence collection, and pass/fail/block reporting.
- Gates: `Hard Gates` lists the checks that must stay visible and cannot be replaced by confidence, intent, or stale reports.
- Output: `Output Requirements` defines the evidence, blocker, skipped-check, residual-risk, and claim-boundary fields expected in SkillGuard reports.
- Maintenance: `SkillGuard Maintenance` says when this entrypoint and related public files must be kept in sync.

If a current check cannot support one of these criteria, report the specific gap. Do not compensate by adding unrelated files, broad repository edits, generated outputs, git operations, package metadata changes, or release claims.

## Use When

Use this skill when the user asks to:

- Create, update, audit, or prepare a Codex skill or skill-like workflow.
- Review a skill repository for public readiness, activation clarity, privacy safety, metadata consistency, or release claims.
- Check whether a skill's description is too broad, too vague, or likely to activate for unrelated tasks.
- Validate a maintained skill target, suite summary, README, `SKILL.md`, metadata, fixtures, schemas, scripts, or check evidence.
- Check README-facing release gates such as bilingual mirror coverage, text-to-image hero provenance, README model evidence, version consistency, command-surface wording, and public-boundary safety.
- Compare parent status against child evidence so a suite or release summary does not hide stale, failed, missing, or skipped checks.
- Produce a status report that needs current evidence, blockers, skipped checks, residual risk, and claim boundaries.
- Ensure that every check declared by a maintained skill was actually completed for the current request instead of merely loading the skill or running generic boundary checks.
- Adopt, audit, or directly rewrite a repository's sole current SkillGuard maintenance state so future AIs and other computers can locate the canonical SkillGuard repository.

## Do Not Use When

Do not use this skill for unrelated coding tasks that do not involve a skill, skill repository, skill-like workflow, or skill-release boundary.

Do not use this skill for generic README writing, ordinary package publication, broad repository cleanup, dependency upgrades, application feature work, or release notes unless the work is specifically about a Codex skill or its maintenance evidence.

Do not use this skill merely because a repository contains Markdown, Python, tests, or a release process. The task must involve skill maintenance, skill activation, skill validation, or skill-publication claims.

Do not use this skill to certify AI correctness, guarantee Codex activation, or bypass human review. SkillGuard can require evidence and structure judgment records, but it cannot prove that future model behavior will always be correct.

## Required Workflow

1. Inspect the current materials before editing or judging them.

   Identify the target skill path, repository root, maintained target, suite file, or release artifact. Record whether files already exist and preserve user or peer-agent work.

2. Confirm the scope and target.

   State whether the task is for one skill, a suite of skills, a public repository foundation, a release check, or a repair. If the target is unclear, block or ask for the missing information instead of guessing.

3. Inventory the relevant files.

   List the skill entry file, referenced documents, schemas, templates, package metadata, status records, and public documentation that matter to the requested check. Include scripts, fixtures, tests, generated outputs, and release artifacts only when they exist or when their absence is itself the finding.

4. Initialize or update maintained records only when the current task owns that work.

   If the task only asks for review, do not create new maintained files. If initialization is requested, create only the target files required by the documented structure and preserve existing content.

5. Apply deterministic checks first.

   Check file existence, frontmatter, required headings, parseable metadata, referenced paths, version consistency, status-record freshness, and any fixture or command availability that the current task actually claims. If a task depends on a local script, fixture, test, example, release artifact, or command that is absent, report that absence as a finding instead of fabricating or assuming the missing material.

6. Apply judgment checks only after deterministic evidence is clear.

   Review activation scope, non-use boundaries, unsafe claims, stale evidence risk, parent overclaim, privacy exposure, and whether instructions are operational enough for future agents.

7. Collect fresh evidence.

   Use current filesystem content, parser output, command output, hashes, line counts, timestamps, or concrete reviewer notes. Do not rely on old reports unless they are still tied to unchanged files.

8. Report pass, fail, or block.

   A missing required file, stale required evidence, privacy exposure, malformed metadata, or unvalidated release claim must be reported as a failure or blocker. Do not downgrade it to a warning just to complete the task.

9. For a maintained project, verify both portable project adoption and one current target execution receipt covering every declared check before making a completion or release claim.

## Current Runtime Contract

Use the current runtime contract when the task is about making a target skill's actual work path enforceable, not merely reviewing repository files.

SkillGuard must:

- compile or maintain a confirmed current `.skillguard/contract-source.json` whose fixed integration marker is `native-integrated`; the target always owns its domain route and declared checks, while SkillGuard only supervises them;
- bind native routes and native checks directly when the target skill already owns routing, validation, controller, or closure behavior; do not create a second SkillGuard execution router beside the native system;
- require the target-native route decision before non-trivial skill work starts;
- claim one current target-local evidence run for every non-trivial supervised task while preserving the target skill as the only owner of its domain action;
- use that run only for route selection, prerequisites, native action/check binding, immutable evidence, exact-input freshness, and closure supervision; never use it as a second target-domain executor;
- advance phases only when required evidence and checks are present for earlier phases;
- run route, phase-order, evidence, quality-floor, freshness, suite-child, and closure checks before closure;
- block missing contracts, hollow contracts, ambiguous routes, skipped phases, stale evidence, prose-only evidence, quality downgrades, and closure overclaims.

SkillGuard is the contract supervisor attached to the original skill system. It may retain a current evidence run, but every domain action and native check must bind back to the original router, controller, simulator, checker, or release flow. A second implementation of the target workflow is invalid. Historical run records never gain current success authority.

AI or human judgment may be recorded after deterministic evidence is clear, but it cannot replace required runnable checks or make skipped work pass.

## Current Executable Contract

For current maintenance and self-hosting:

- compile with `scripts/skillguard_compile.py`; `--check` is read-only and fails on missing or stale generated files;
- execute any confirmed target contract with `scripts/skillguard_supervise.py` and follow `references/skillguard-supervisor.md`; pass the skill root, packet path, target root, and repository root as command arguments. The packet supplies the request, per-step witnessed or judged evidence, optional-skip proof, and the sole `enforced` closure, while the supervisor performs route selection, the target-local claim, native checks, artifact validation, immutable receipts, closure, and replay;
- keep `repository_root` and `target_root` distinct when the target skill uses both: the repository root owns maintained skill and contract inputs, while the target root owns current task data and artifacts; bind both through portable content identities rather than local absolute paths;
- freeze the exact `native_check_ids` declared by the target skill before execution. Every declared check must have exactly one execution owner, explicit dependencies, and one current terminal receipt for the same request; missing, duplicate, stale, non-terminal, skipped, failed, timed-out, cancelled, or cleanup-unconfirmed results block;
- do not classify target skills or infer check meaning from names. SkillGuard must not branch on a target family, invent a purpose contract, require a good/bad pair, or interpret a target oracle. A target that declares one check is supervised by the same fixed workflow as a target that declares several checks;
- keep target-domain rules inside the target skill. If a target skill requires particular fixtures, counterexamples, or domain oracles, it declares those as its own checks and SkillGuard supervises their exact receipts without reimplementing their semantics;
- keep `capability_validation` and `scheduled_production` non-interchangeable. Source-only checks cannot close scheduled production; scheduled production additionally requires trigger/execution, installation-receipt, and installed-runtime identity;
- use the function and route ids in the compiled contract instead of inferring workflow from headings;
- claim the run before target work and resume only by replaying its contract snapshot and hash-chained events. For route-conditional scheduled production, use the explicit two-stage supervisor: `supervision_mode: stage_depth` with `profiles: []` executes checks and returns status `staged` plus one exact depth receipt; the target then builds/writes its native terminal receipt with `build_target_native_terminal_receipt(...)` and `write_target_native_terminal_receipt(...)`; `supervision_mode: close` resumes the same request/run, reuses the same depth receipt id/hash, consumes the portable terminal ref, and closes without rerunning completed checks;
- treat AI “complete” as evidence submission only; a native check, artifact validator, witnessed action verifier, or versioned judgment rubric must issue the authoritative receipt;
- enforce the primary evidence class declared by each action: a hard model/check receipt cannot stand in for a `judged` step, and a model/check receipt cannot stand in for a `witness` step;
- require immutable stored check/artifact records before hard evidence can pass. Keep `semantic_check_id`, per-attempt `execution_id`, and exact `execution_key` distinct; only an immutable terminal success may be reused, while failed attempts never populate the canonical success slot and source/input changes fail stale;
- before multi-skill validation, freeze one owner plan in the existing verification contract or TestMesh: list every exact check, covered obligation/evidence domain, dependency order, persistent receipt root, and exactly one primary execution owner. Consumers resolve and verify the exact current owner receipt and never carry or rerun its command. Missing, duplicate, cyclic, stale, or identity-incomplete ownership blocks before execution; maintained inputs invalidate only affected receipts, while reports, receipts, progress logs, and runtime outputs stay outside source authority and cannot retrigger their producer;
- include declared implementation source in the contract fingerprint while excluding only transient runtime material such as `.skillguard`, `__pycache__`, test/tool caches, bytecode, and `node_modules`; a real source change must still stale the generated contract and prior closure;
- keep declared-reference checks semantic: local Markdown links/images/reference definitions and explicitly declared script, schema, artifact, or guide paths remain references, while fenced examples, inline shell commands, CLI argument values, database URIs/SQL, undeclared database runtime locations, and inline transient `.skillguard/runs`, locks, bootstrap, or test-results output locations are runtime text rather than required local files;
- include the current SkillGuard runtime fingerprint in external receipts so a Guard behavior change makes only affected prior evidence stale;
- reject former runtime files, commands, lifecycle fields, receipts, schemas, conversion scripts, and history directories. They may appear only in exact negative fixtures. Ordinary maintenance must write the current trio directly, delete the named former surfaces, and validate the resulting current shape; no product code reads or converts the old payload;
- close only with the fixed `enforced` closure and preserve missing, failed, blocked, skipped, stale, uncertain, and not-run gaps;
- use `scripts/skillguard_self_host.py` and `references/skillguard-self-host.md` for the single current-authority self-host run.
- use `scripts/skillguard_test_mesh.py --profile <fast|focused|full> --mode plan_only` with exact run, skill, target, and persistent owner-evidence roots to create the immutable affected-owner plan. Plan-only launches no child process. Pass that exact file to `--mode owner_execution_only --frozen-plan <plan>`; the public runner validates the frozen identities and dependency order, verifies planned reuse read-only, and resolves only `will_execute_owner_ids` through the existing single-flight owner authority. A repeated invocation may reuse newly current receipts but cannot replan, broaden, or repeat a process. Then pass the same unchanged plan to `--mode aggregation_only --frozen-plan <plan>`; aggregation only references exact immutable owner receipts and never reissues them. Downstream verification uses `--replay-aggregation-ref <ref>` and is structurally read-only. A full aggregation additionally requires the exact current installation receipt and global-prompt binding. When the maintained target is outside the canonical SkillGuard repository, bind that one current source authority explicitly with `--canonical-skillguard-root`; this is a location binding, not an operating mode or alternate authority;
- treat every process timeout as an owner-execution boundary rather than a TestMesh retry signal: the launcher must confirm zero descendants, publish no success receipt when cleanup is unconfirmed, and return control to the frozen plan without broadening its affected set;
- bind every registered ordinary long self-host check to its exact measured command, all accepted measurement samples, and a hash-bound pre-run timeout record; the current installation-safety command measured 352.834 seconds in isolation and 563.984 seconds inside complete self-host, uses the maximum with a 600-second ceiling plus 120 seconds of runtime-variance grace, declares 900 seconds, and must block before run claim when the check is missing, duplicated, retargeted, or declares 720 seconds or less;
- derive the self-host report claim boundary from the exact replay-verified `enforced` closure; a missing, duplicate, or mismatched closure projection fails closed;
- keep the self-host CLI terminal narrow: ordinary `Exception` failures emit one path-safe six-field JSON terminal without traceback and return nonzero, while `KeyboardInterrupt` and `SystemExit` are not caught;
- emit `progress` only for a positive stdout/stderr byte delta, keep `heartbeat` liveness-only, validate the sequence/hash chain, and require final child artifacts, current source fingerprints, exit status, visible skips/timeouts, and no cancellation for parent confidence;
- on timeout, terminate the process tree and retain a durable immutable owner-bound receipt with millisecond timing, full-stream hashes, total and captured byte counts, termination facts, and retry/resume guidance; a timeout receipt is failed-boundary evidence, never a pass;
- run `scripts/skillguard_provenance.py` before installed sync and release claims; `--development` may retain a structured unavailable GitHub snapshot without blocking solely because `gh` is missing, but release mode must fail closed with `github_release_unavailable`; keep the canonical local source, installed copy, Git origin, version/tag, and GitHub Release identities distinct, and block any installed downgrade or partial-file sync;
- treat SkillGuard and `skillguard-global-router` as one runtime-integrity cohort: the fingerprint must include the sibling router skill, current source/compiled contract, manifest, scripts, and references, and must fail closed when any required surface is missing or unreadable.
- use `content_role_overrides` only for reviewed ambiguous content: a path may name one maintained file or one maintained directory subtree, a directory applies to every inventoried descendant including future files, and overlapping overrides block instead of selecting by order or specificity. Do not replace automatic classification with a per-file inventory.
- run `scripts/skillguard_privacy.py` over tracked and unignored release candidates; reject secrets, machine-specific paths, runtime state, private file types, and images without a current hash-bound visual review.
- run `scripts/skillguard_install.py` for exact-component staged installation; require installation-projection parity plus clean-layout command, self-check, public `check-skill`, runtime import, and current-authority smoke before activation; the smoke must reject former-runtime residuals before transient paths are ignored. Source-only tests, fixtures, models, notes, reports, receipts, logs, and timestamps are outside installation freshness unless the frozen installation projection explicitly owns them. On Windows, preflight portable file/directory destination lengths before creating either staged member and use a shorter isolated stage root when blocked; if copying fails, remove every newly created suite-member root or report cleanup blockers; preserve the previous active copy as a backup and automatically restore it if post-activation validation fails. Partial file copying is not an acceptable installation or upgrade path. After activation, capture and verify the installation receipt under active `.sg-runtime/installation`, then construct scheduled identities only through `build_scheduled_production_identity(...)`. Every depth issuance and terminal closure replays its `installation_receipt_root_ref`, receipt id/hash, and installed runtime fingerprint against the current active installation; hash-shaped fields alone are not parity evidence.
- run `scripts/skillguard_target_install.py` for one maintained non-SkillGuard target. Supply the canonical repository root, exact skill root, isolated stage root, and CODEX_HOME. The compiler-owned `member_root_path` must resolve the skill root exactly; stage and active trees contain only `projection:installation`; each skill uses its own target transaction, HEAD, receipt, backup, rollback, and recovery namespace while sharing the global installation mutex. This route never discovers or executes target commands. Native target checks remain separate frozen execution owners and run only after activation when their current contract requires them. See `references/skillguard-target-installation.md`.

## Portfolio Validation Workflow

Use the portfolio validation workflow after SkillGuard self-hosting when maintained targets are optimized one at a time. Follow `references/skillguard-portfolio.md`.

- Keep the portfolio registry private and outside public target repositories when it contains local source locations, private repository metadata, or unpublished evidence.
- Treat `--target-repository-root` as the canonical local source, `--workspace-root` as the private working root, and `--installed-target-root` as a non-authoritative installed copy. Canonical and installed roots must be separate and non-nested; the installed role is available only when it exists as a directory.
- Persist the three-role projection with path tokens and opaque identity hashes only. Send resolved path diagnostics to private stderr with home redaction; never put user-home absolute paths into portable portfolio output.
- When a reviewed current scope replaces stale registry authority, run `build-current-portfolio-registry` from that exact hash-valid scope. It creates revision one directly, reads no prior registry, carries no old green receipt or reuse ticket, keeps active targets pending or revalidation-required, and preserves exclusions and complete supersession tuples. A file output acquires the same sole portfolio-registry writer lock before construction and commit, so a live impact, reuse, graduation, or replacement writer blocks it without overwrite. It is not a migration, compatibility, or fallback path.
- Run `audit-portfolio` before target work and before the next target graduates. Pending or revalidation-required skills remain visible; excluded private/system skills and supporting repositories use explicit non-active lifecycle records.
- When a reviewed scope marks a target as superseded, require the complete target-neutral tuple: `retirement_disposition: superseded`, one distinct active `superseded_by_skill_id`, `installation_disposition: absent`, and `router_authority: blocked`. Scope and registry validation block partial tuples, missing/inactive replacements, and self-reference. Before claiming zero installation or router authority, separately confirm the old skill is absent from the installed root and current router registry.
- After any SkillGuard behavior change, run `mark-portfolio-impact` with the old/new Guard identities, compiler-derived changed component ids, affected feature tags, broad-change flag, reason, and an immutable `--receipt-root`. Invalidate only the exact target/member edges reached from those changed functional components. Unrelated targets remain current and need neither execution nor a reuse ticket. Reports, receipts, logs, timestamps, generated status, and install bookkeeping have no portfolio edge unless the frozen policy explicitly classifies them as functional input. The impact receipt proves invalidation only; it neither revalidates a target nor permits reuse of an affected receipt.
- Use `issue-portfolio-reuse-ticket` only for a non-broad, non-intersecting Guard change when source, contract, command, environment, and coverage fingerprints are all unchanged.
- For a suite, require `member_capability_inventory` to give every target capability exactly one member owner. Every declared member path must appear, and jobs from one member must not claim another member's capabilities.
- Use the production `prepare-portfolio-run`, `execute-portfolio-run`, `capture-portfolio-production-revalidation`, `assemble-portfolio-run`, and `graduate-portfolio` commands instead of test helpers. Keep all five as current typed `route-task` entries so the route-first handoff selects the exact phase rather than a generic audit. `prepare` atomically freezes exactly one complete ordered target-level plan, every job spec, the active Guard, target identity, and—when supplied—the content-exact installed-member parity receipt before the earliest claim. `execute` resumes the same preparation and sends every frozen job through ordinary claimed current runs in isolated working copies. `capture` records each member's exact scheduled-production depth, terminal, declared-check depth, closure, scheduler/execution, and current installed-runtime identities; source-only validation is non-authoritative and cannot be promoted into scheduled-production evidence. `assemble` rejects a missing job or current production receipt, re-scans the installed root for a prepared suite so post-prepare member drift cannot pass, shares one sealed installation context across all members, later-currentness checks, and the graduation dry-run, and does not write the registry or publish anything. Source-only capability self-checks are typed non-authoritative evidence and cannot graduate a target. `audit-portfolio`, `assemble-portfolio-run`, and `graduate-portfolio` require explicit target repository-root mappings for every prior active entry whose currentness they consume; stored green state is never enough.
- Every capability must equal one target-authored semantic variant through its real member contract function/route, step, obligation, exact frozen-manifest check, and artifact path. The actual selected functions/routes, required steps, frozen checks, receipts, and closure consumption must be replayed; a related-looking green check or plan-only declaration is not coverage.
- For `invalid_input` and `out_of_scope`, require verifier-owned typed terminal and ordered mutation-observation records bound to the same preparation and run. The before scan must precede the claim, the class-specific terminal must follow execution, the after scan must follow the terminal, and the two maintainable-source fingerprints must match. Request labels, stdout, copied hashes, or missing output are not rejection proof.
- For installation, compare the exact compiler-owned install projection of each affected canonical member with its installed member. The final suite completeness scan is a cheap read-only file gate after declared-check receipts are frozen; its report is an output and cannot invalidate or rerun native tests. A current primary member cannot hide an affected router-member mismatch, but an unrelated source-only test/model/note/report change must not make another member's install projection stale.
- Run `graduate-portfolio` only after receipt-bound representative real jobs cover every target and member capability plus the required positive, invalid-input, recovery/resume, out-of-scope, native-check, and artifact-check classes. SkillGuard derives outcomes from current runtime facts; target stdout is diagnostic only. Every `record:<workspace-relative-path>@<sha256>` evidence ref must resolve to a current identity-bound record, and command, environment, result, evidence-file, and evidence-payload hashes must be recomputed. It must block on any unresolved ref, plan/spec/check-path mismatch, payload mismatch, coverage/class gap, or prior active entry without current full evidence or a history-verifiable reuse ticket.
- Treat direct replacement, impact, reuse, and graduation as single-writer registry mutations. A live registry writer blocks a second writer; an abandoned local writer lock is recoverable without accepting concurrent lost updates.
- Classify target failures as `target_implementation_gap`, `target_contract_binding_gap`, `skillguard_model_miss`, `skillguard_runtime_or_validator_gap`, or `environment_or_external_blocker`; an unresolved classification blocks graduation.
- If a target exposes a SkillGuard miss, add the observed regression and generalized bad family first, repair SkillGuard, rerun self-host and affected prior targets, then retry the current target.

## Declared-Check Execution Depth

Use declared-check execution depth when SkillGuard must answer whether a target skill's own required checks were actually completed for the current claim. Read `references/skillguard-execution-depth.md` before adding or changing a `depth_profile`.

There is one fixed workflow and no optional mode:

1. The target skill declares its native owner, route ids, and exact required check ids.
2. SkillGuard freezes that inventory and its dependency graph for the request.
3. Each declared check executes once under its frozen owner or reuses one exact current immutable success receipt.
4. SkillGuard reconciles the inventory and receipts by check id, owner id, request fingerprint, terminal disposition, freshness, and receipt identity.
5. Closure may consume the depth receipt only when every declared check passed and no unresolved check remains.

`CONTRACT_DEPTH_PASS` proves only that the target's declared inventory is structurally complete and bound to current owners. `EXECUTION_DEPTH_PASS` proves that every check in that frozen inventory has one current terminal-success receipt for the same request and runtime, and that the receipt was consumed by the requested closure. Contract depth never implies execution depth. Missing, failed, skipped, stale, timed-out, cancelled, cleanup-unconfirmed, or not-run checks remain visible blockers.

SkillGuard does not know what a target check means. It does not classify targets, detect a family name, assign a model purpose, invent a counterexample, or mandate a particular number or pattern of checks. The target skill retains full ownership of its domain actions, depth standard, fixtures, oracles, and claim boundary. When a target owns several checks, SkillGuard requires all of them only because the target declared them; when a target owns one check, SkillGuard does not force it to invent another.

Branch-conditional targets must still project their own conditional obligations and route/branch requirements. Native terminal closure binds the exact current declared-check receipt and any verifier-owned applicability receipt. An intermediate authorization remains non-terminal and cannot substitute for the fixed `enforced` terminal completion.

Finally, compare the active provider runtime with the profile's required runtime contract, capabilities, enrollment status, and readiness checks. A profile attached to an old runtime is an explicit non-pass state, never an execution-depth pass.

## Project Adoption Workflow

Use the project adoption workflow when a repository contains one or more SkillGuard-maintained skills and future agents or machines need a portable maintenance handoff. Read `references/skillguard-project-adoption.md` before changing adoption behavior.

- Run `project-adopt` once to create repository-root `.skillguard/project.json` and install the managed AGENTS.md block while preserving surrounding project instructions.
- Run `project-audit` before non-trivial maintenance closure and after transfer, installation, current route changes, prompt changes, or SkillGuard source changes.
- When adoption is non-current, rerun `project-adopt` only with the complete explicit current managed-skill list. It directly replaces the managed block and manifest; it must not reuse, convert, or renew old rows.
- Require exactly one begin marker and one end marker, the canonical [SkillGuard repository URL](https://github.com/liuyingxuvka/SkillGuard), a current manifest/block hash pair, existing managed skill entrypoints, the fixed `native-integrated` marker, and an explicit native owner record.
- Treat a missing, malformed, duplicated, tampered, or stale managed block or manifest as blocked. The project prompt is routing and maintenance evidence only; it does not replace a target execution-depth receipt, native tests, installation parity, or release proof.

## Target Contract Integrity

Use target contract integrity checks when the question is not only "does a contract file exist?" but "does the current contract faithfully preserve the checks the target skill chose for itself?"

SkillGuard compares the target `SKILL.md`, adjacent native route/check materials, and the current source/compiled/manifest trio selected by `check-runtime-authority`. Any non-current target is blocked until ordinary maintenance replaces it directly. Current run directories provide execution evidence only and never become contract authority.

The integrity check is deliberately target-neutral:

1. Read the target skill's entrypoint and native route/check records.
2. Freeze the exact target-declared check inventory, owners, dependencies, evidence domains, and closure bindings.
3. Confirm every declared check appears exactly once in the compiled contract and check manifest.
4. Confirm no undeclared SkillGuard-owned domain route, semantic oracle, fixture pattern, target category, or quality mode has been added.
5. Run `check-contract` for structural currentness and `check-depth` for exact declared-check coverage.
6. Block on missing, duplicate, ownerless, cyclic, stale, non-terminal, skipped, failed, or not-run declared checks.

The target skill decides what its checks mean and how many it needs. SkillGuard neither requires a paired example nor weakens a target that declares several domain checks. A contract passes this boundary only when it preserves the target's own inventory exactly and the current execution receipt accounts for every member.

For release-facing README work, run `check-readme-release` in addition to the general SkillGuard checks. This gate is the executable bridge to the README Showcase Writer contract: English-first Chinese mirror, text-to-image hero evidence, README model evidence, version consistency, command-surface wording, and public/private boundary checks.

README model evidence must be current to the release being checked and must include the README Showcase Writer's internal artifacts: repository fact ledger, capability claim matrix, narrative structure plan, and gap ledger. A compact "root claim/mechanism/evidence/boundary" note is useful context, but it is not enough to support highest-standard README coverage.

## Global Router Workflow

Use the global router workflow when the task is about making SkillGuard routing available at the user level across installed or repository-local skills.

SkillGuard should:

- scan explicit skill roots for `SKILL.md` files and resolve each adjacent SkillGuard authority as exactly `current` or `blocked`; a blocked skill may remain visible in diagnostics but has no executable default route;
- build a global registry artifact as the route-selection source of truth;
- render a managed user-level AGENTS prompt block from that registry;
- install or replace only the managed SkillGuard global router block while preserving unrelated user prompt content;
- check the installed block against the current registry hash before claiming global prompt freshness;
- resolve the user's task to exactly one current skill, then hand off to that skill's own `SKILL.md` and current source/compiled/manifest trio; never recover a route from historical migration material;
- refresh the global registry and managed prompt block whenever a skill is added or a skill's entrypoint, contract, check manifest, or native route binding changes.

The global router is a routing and prompt-projection layer only. It does not execute the selected skill, prove target skill tests, prove package publication, or certify future AI behavior.

## Hard Gates

These gates are mandatory for SkillGuard work. If a gate cannot be checked, mark it as skipped with a reason or block the task. Do not claim success for unchecked gates.

- Required files must exist for the stated scope.
- `SKILL.md` frontmatter must be structurally valid and closed before body content.
- Required sections must be present for the artifact being checked.
- Activation boundaries must say when to use the skill and when not to use it.
- Public files must not expose credentials, machine-specific local paths, confidential task material, or internal coordination records.
- Validation evidence must be fresh enough for the current files being judged.
- Parent or suite status must cite current child evidence and must not hide failed, missing, blocked, skipped, or stale child checks.
- AI or human judgment must be recorded as judgment, not as deterministic proof.
- Release, package, command, fixture, schema, git, and publication claims must be directly validated before they are described as complete.
- Failures and blockers must remain visible in the final report.
- Runtime contract work must not close unless the selected route, run record, required phases, required evidence, required checks, quality floors, and closure boundary are all current for the declared scope.
- Target contract integrity work must not close on `check-contract` alone. It must run `check-depth` when the task claims that a target skill's declared checks are completely covered.
- Declared-check supervision must not close on `CONTRACT_DEPTH_PASS`, profile presence, generic boundary checks, or caller-authored observations. It requires a current immutable target execution receipt bound to actual target-owned native check receipts and consumed by the fixed `enforced` closure.
- Enforced execution depth must freeze the target's complete declared-check inventory and require one exact current terminal-success receipt per check under one owner. SkillGuard must not classify targets or invent target-domain semantics.
- Capability-validation evidence cannot authorize scheduled production; scheduled production must bind the exact installation/runtime execution identity.
- A conditional obligation must not escape the fixed `enforced` closure by omitting its branch contract. Require top-level `route_branch_closure_required: true`, the `conditional: true` obligation projection, exact route/branch requirements, a current native terminal and declared-check receipt, and verifier-owned `not_applicable` evidence for legitimate no-op obligations. An intermediate authorization is non-terminal and cannot substitute for terminal completion.
- A SkillGuard-maintained repository must not claim maintenance closure when `project-audit` reports a missing, stale, duplicated, tampered, or incomplete project prompt/manifest.
- README release work must not close on prose review alone. It must run `check-readme-release` when the task claims README bilingual, hero, model, version, command-surface, or public-boundary readiness.
- Runtime contract work must bind the target's native route/check system and must not add a parallel SkillGuard execution route. Each SkillGuard phase must name the native route binding and native check binding that prove the phase.
- Global router work must not claim current user-level routing unless the registry and managed user-level AGENTS prompt block were refreshed or checked against the current registry hash.

Hard gates are not suggestions. Vague confidence, intent, partial inspection, or a prior successful run is not enough to pass a hard gate.

## Output Requirements

SkillGuard reports should include:

- `checked_target`: the skill path, maintained target, suite file, repository area, or release artifact.
- `status`: `pass`, `fail`, or `block`, with `needs-review` or `stale` only when those labels are more accurate for the requested scope.
- `evidence`: current files inspected, commands or parsers run, hashes or line counts when useful, and the specific records used for the decision.
- `failures` and `blockers`: missing files, malformed metadata, stale evidence, unsafe claims, privacy findings, unclear activation boundaries, or unavailable required tools.
- `skipped_checks`: every skipped check and the reason it was skipped.
- `residual_risk`: what remains uncertain after the completed checks.
- `claim_boundary`: what the report does and does not prove.

Do not claim that scripts, fixtures, schemas, command-line tools, package publication, git commits, GitHub releases, external credentials, or downstream validation are complete unless those exact items were directly validated in the current task.

## SkillGuard Maintenance

When SkillGuard changes, keep the public contract synchronized across the maintained files:

- Update `SKILL.md` when activation scope, non-use boundaries, hard gates, or output requirements change.
- Update the repository README when public usage, status meanings, command names, non-guarantees, or repository structure change.
- Keep version metadata synchronized when release metadata changes.
- Keep validation commands and examples aligned with the scripts, fixtures, schemas, and tests that actually exist.
- Keep `check-runtime-authority`, `check-contract`, and `check-depth` aligned with the single current source/compiled/manifest authority, exact former-surface rejection fixtures, generated templates, and installed-skill behavior.
- Keep the declared-check depth profile, inventory freezing, receipt reconciliation, conditional branch/no-op closure, target receipt, compiler, supervisor, closure, fixtures, and schemas synchronized.
- Keep TestMesh parent closure/replay semantics, installation verification receipts, and portfolio-impact receipts synchronized with their current commands and claim boundaries.
- Keep `project-adopt`, `project-audit`, the repository-root manifest, managed AGENTS.md block, canonical repository URL, and project-adoption fixtures synchronized.
- Keep `check-readme-release` aligned with README Showcase Writer requirements and public release evidence.
- Refresh the global registry and managed prompt block when a skill is added or when the router projection reports that `SKILL.md`, current authority, native route binding, or router command behavior changed. Evidence outputs and ordinary unchanged skill use do not trigger a refresh.
- Preserve privacy boundaries in public files. Do not copy private workspace instructions, local machine paths, private task text, or internal coordination details into maintained artifacts.
- Re-run the relevant deterministic checks after edits and record any judgment-based review separately from parser or command results.
- Treat stale evidence as stale. If an exact maintained component changes, rerun only its affected owner or consume a new owner receipt before claiming acceptance; never edit timestamps or evidence metadata to manufacture freshness.
