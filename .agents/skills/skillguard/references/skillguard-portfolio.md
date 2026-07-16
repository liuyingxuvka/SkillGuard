# SkillGuard current Portfolio Runtime

The portfolio runtime is a private, machine-readable parent gate for one-skill-at-a-time maintenance. It does not replace target contracts or execute target-domain work. It records which maintained targets are current under the exact active SkillGuard runtime and keeps excluded, pending, blocked, stale, and revalidation-required entries visible.

## Lifecycle and queue boundary

- `active_owned`, `active_adopted`, and `pending_adoption` entries have a unique non-negative `order` and participate in graduation.
- `retired_private`, `excluded_private`, and `excluded_system` entries have `order: null`, `graduation_status: excluded`, and an explicit reason. They never block or silently enter the active queue.
- A retired entry that has been replaced uses the complete supersession tuple: `retirement_disposition: superseded`, one distinct `superseded_by_skill_id` that resolves to an active entry, `installation_disposition: absent`, and `router_authority: blocked`. A partial tuple, self-reference, missing replacement, or inactive replacement blocks scope and registry validation.
- `supporting_repository` entries have `order: null`, `graduation_status: supporting`, and a `parent_skill_id`; their behavior is checked through the owning target rather than falsely graduated as a standalone skill.
- `FlowGuard` and `FlowPilot` can remain active but ordered last while their canonical worktrees are still changing.

## Field lifecycle

| Field | Canonical owner | Writers | Readers | Lifecycle and invalidation |
|---|---|---|---|---|
| `active_guard` | portfolio registry | `mark-portfolio-impact` | every portfolio command | Replaced only by a declared `guard_change`; old child evidence cannot remain current merely because the target source did not change. |
| `canonical_source` | target entry | `graduate-portfolio` after target evidence passes | audit, reuse, graduation | `path_token` is private-registry metadata; `source_fingerprint` and `version` identify the validated target state. |
| `contract_hash` | target entry | `graduate-portfolio` | audit, reuse, parent gate | Must equal the current full-run receipt and reuse identity. |
| `consumed_guard_feature_tags` | target entry | reviewed registry maintenance | impact and reuse | A tag intersection forbids reuse and requires real revalidation. |
| `capability_inventory_status` / `required_capability_ids` | target entry | reviewed target inventory | audit and graduation | A target can be inventoried as pending, but it cannot graduate until the inventory is current and non-empty. |
| `member_capability_inventory` | reviewed scope and target entry | reviewed target inventory | scope projection and graduation | Every capability has exactly one member owner. The union must equal the target inventory, every declared member path must appear, and a job from one member cannot claim another member's capability. |
| `job_plan_ref` / `job_plan_hash` | target-level preparation | claimed run and graduation verifier | runtime replay and graduation | Exactly one complete ordered plan binds every representative job to a member, class, job spec, and capability set before the earliest claim. A missing, second, replaced, or post-claim plan blocks replay. |
| `job_spec_ref` / `job_spec_hash` | pre-claim portfolio planner | claimed run and representative job | runtime replay and graduation | The specification maps every claimed capability through the exact member contract function/route, step, obligation, frozen-manifest check, and required artifact/replay facts. The claimed run freezes the exact specification. |
| `preparation_id` / preparation receipt | production `prepare` phase | `prepare-portfolio-run` | execute, assemble, graduation | Binds the one global plan, every exact spec, current Guard, target identity, optional installed parity, and a timestamp before every claim. Every job run must freeze the same preparation identity. |
| execution / assembly result refs | production runner | `execute-portfolio-run`, then `assemble-portfolio-run` | resume, graduation | Typed, schema-valid, internally hashed phase results are reused only after their referenced evidence and preparation bindings are revalidated. |
| installed parity receipts | installed-content verifier | prepare, assemble, and suite graduation | active-Guard and installed-current gates | Bind every declared member and complete file-level hashes. Assembly re-scans the installed root; a router or other member drift after preparation blocks final assembly. |
| `representative_jobs` | graduation evidence and target entry | target verifier, then `graduate-portfolio` | coverage check and parent receipt | Every job names its exact member, covered capability ids, predeclared spec, and direct evidence refs. The canonical job set hashes to the full receipt's `coverage_fingerprint`; an uncovered target or member capability blocks graduation. |
| `required_job_class_ids` | target entry | reviewed target inventory | audit and graduation | Defaults to positive, invalid input, recovery/resume, out of scope, native check, and artifact check. Missing required classes block graduation even when capability ids are covered. |
| `evidence_refs` | representative job | target verifier | graduation and later audit | Each ref uses `record:<workspace-relative-path>@<sha256>`, stays under the declared private workspace, and resolves to a structured record bound to the same job, capabilities, Guard, source, and contract. |
| `full_run_receipt` | target entry | `graduate-portfolio` | audit, reuse, later graduation | Carries the command set, environment, and result bundle. Current only when their recomputed hashes plus a fresh target-source scan, exact production bindings, current installation/smoke replay, coverage, evidence records, and Guard identities match. Historical receipt content is preserved when status becomes `revalidation_required`. |
| `production_revalidation_binding_refs` / `production_revalidation_fingerprint` | external scheduled-production runs and portfolio assembler | `capture-portfolio-production-revalidation`, then `assemble-portfolio-run` | graduation, full receipt, later currentness | Exactly one immutable binding per target member. Each binding preserves its scheduler/trigger and scheduled-execution ids, replays the exact scheduled-production declared-check receipt, a `terminal_completion` native terminal, fixed `enforced` closure consumption, and the current installed SkillGuard transaction plus current installed-smoke result/command/environment identities. Capability validation never substitutes for this domain. |
| `reuse_ticket` | target entry | `issue-portfolio-reuse-ticket` | audit and parent gate | Allowed only for a registered, non-broad, non-intersecting Guard change with unchanged five-part identity. The ticket must revalidate against the append-only change history, previous full receipt, and active Guard. |
| `graduation_status` | target entry | impact, reuse, graduation | every portfolio command | `current` is verifier-owned. Guard changes transition old current entries to `revalidation_required`; target evidence or a valid reuse ticket is required to restore currentness. |
| `failure_classification` | target entry/evidence | target maintenance workflow | graduation and reports | A non-null unresolved failure classification blocks graduation. |
| `guard_change_history` | registry | `mark-portfolio-impact` | audits and final report | Append-only semantic history; it records affected feature tags and broad-change scope without claiming revalidation. |
| `retirement_disposition` / `superseded_by_skill_id` | reviewed scope, then registry projection | reviewed portfolio maintenance | scope validation, registry validation, audit | A `superseded` entry points to exactly one distinct active replacement; it never remains in the active order. |
| `installation_disposition` / `router_authority` | reviewed scope, then registry projection | reviewed portfolio maintenance | scope validation, registry validation, installation/router audit | Superseded entries use exactly `absent` and `blocked`. These declarations define the authority boundary; a completion claim still needs a current read-only scan proving the old skill is not installed and is absent from the current router registry. |

## Canonical, working, and installed path roles

Portfolio reuse and graduation keep three path roles distinct:

| Role | Token | Authority and availability |
|---|---|---|
| canonical local source | `target_repository_root` | Authoritative target source. It must resolve to an existing directory. |
| private working root | `workspace_root` | Owns the private registry, evidence records, and transaction outputs. It must resolve to an existing directory but does not replace target source authority. |
| installed copy | `installed_target_root` | Optional and non-authoritative. It is available only when the declared path exists and is a directory. |

Every role projects `state`, the four `declared`/`resolved`/`verified`/`missing` status flags, `exists`, `is_directory`, `identity_verified`, and `available`. Canonical and installed paths are rejected when they resolve to the same location or either is nested under the other; an installed copy can therefore never masquerade as the editable canonical source.

Portable command output uses `skillguard.path_role_projection.v1` / `skillguard_path_role_projection`. It persists role tokens and opaque identity hashes, not home-directory absolute paths. The private stderr display uses `skillguard.runtime_path_display.v1`, sets `display_redaction: home_redacted`, and replaces paths under the user home with `<HOME>/...`. The display is diagnostic only and does not establish installation, parity, or publication.

## Command sequence

The five production phases are separate current entries in the public `route-task` registry. Route the intended phase first; do not treat `audit-portfolio` as an execution fallback for prepare, execute, capture, assemble, or graduate.

0. If a newer reviewed scope makes the existing registry non-current, run `build-current-portfolio-registry --scope <current-scope> --registry-id <id> --output <registry>`. This direct replacement reads no prior registry, starts at revision one, preserves active/excluded/supporting lifecycle declarations from the exact scope, and carries no historical graduation or reuse authority. A file output must acquire the same sole registry-writer lock used by later mutations; a live writer blocks replacement without changing the registry. The former registry is a disposed residual, not migration input.
1. Run `audit-portfolio` before maintaining a target. Supply one repeatable `--target-repository-root SKILL_ID=PATH` for every active entry whose currentness is being claimed. Audit re-scans the target identity and replays production plus installation evidence; omission is a blocker, not permission to trust stored green state. One audit invocation shares one sealed installation context across entries that name that exact identity. An incomplete registry is not a green portfolio.
2. After any SkillGuard behavior change, write the one current Guard-change record and run `mark-portfolio-impact --write`. Only the compiler-derived exact target/member edges reached from changed functional components become `revalidation_required`. Non-intersecting entries stay current and need neither execution nor a reuse ticket; reports, receipts, logs, timestamps, and install bookkeeping are not functional components.
3. Use `issue-portfolio-reuse-ticket` only when the change is not broad, affected tags do not intersect, and source, contract, command, environment, and coverage fingerprints are unchanged.
4. Finish the target and per-member capability inventories, then run `prepare-portfolio-run` with the complete representative-job matrix. Preparation atomically writes one global plan, every exact spec, and one preparation receipt before any claim. A suite supplies `--installed-target-root` so every installed member is content-checked at the same boundary.
5. Run `execute-portfolio-run` with the preparation ref. It claims each real positive, invalid-input, recovery/resume, out-of-scope, native, artifact, and applicable judged-quality job through the one current runtime in an isolated working copy, while preserving the same plan and preparation identity for resume.
6. For every target member, run `capture-portfolio-production-revalidation` against its exact workspace-local current scheduled-production run, target-data/shadow root, and fixed `enforced` closure receipt. Capture derives the member binding; it does not accept caller-authored status, route, branch, declared-check outcome, or installation identity.
7. Run `assemble-portfolio-run` with the preparation and execution refs plus one repeatable `--production-revalidation-ref` for every member. For a suite, supply the installed root again so assembly performs a fresh member-level content scan. Assembly revalidates typed terminals, ordered mutation observations, selected routes, manifest checks, artifacts, receipts, closure consumption, and persisted phase schemas before producing a non-writing graduation candidate. Missing, duplicate, foreign-member, capability-only, non-enforced, non-terminal, wrong-domain, or stale installation bindings block specifically.
8. Assembly first requires one exact installation identity across all member bindings and replays that current installation receipt once. The resulting verified installation snapshot is shared read-only with every depth/closure/terminal replay. Multiple installation identities block; the assembler must not rerun the same installation/smoke transaction once per member.
9. Run `graduate-portfolio --write` only with the verifier-assembled evidence and full receipt. Provide `--portfolio-target-repository-root SKILL_ID=PATH` for each prior active entry whose currentness must authorize this graduation. The command independently replays the preparation, capability evidence, every member production binding, shared installation context, and each prior target's later-currentness proof; it re-scans required suite parity and blocks if any declared capability, member, job class, plan/spec/check path, phase result, or prior active entry is missing, stale, misbound, or changed. A successful command writes the exact parent receipt before atomically updating only that target.
10. Rerun `audit-portfolio --candidate <next-skill-id>` before proceeding to the next target.

The production handoff is explicit and repeatable:

```text
skillguard.py capture-portfolio-production-revalidation \
  --workspace-root <private-workspace> \
  --target-repository-root <canonical-target-repository> \
  --member-skill-id <exact-member-skill-id> \
  --member-skill-path <portable-member-path-or-dot> \
  --run-root <workspace-local-scheduled-production-run> \
  --target-root <workspace-local-target-data-or-shadow-root> \
  --closure-receipt-id <exact-enforced-closure-id>

skillguard.py assemble-portfolio-run \
  ... \
  --production-revalidation-ref <member-one-record-ref> \
  --production-revalidation-ref <member-two-record-ref> \
  --portfolio-target-repository-root <prior-skill-id>=<prior-canonical-repository>
```

`capture` derives target, contract/profile, owner, route/check, run, declared-check depth, terminal, closure, and installation fields from current receipts. It does not accept or emit target-category classifications. `assemble` treats every command-line member ref as an assertion only: it loads the complete target identity, requires exactly one ref per member, replays the refs, and writes the normalized member set plus `production_revalidation_fingerprint` into graduation evidence and the full receipt.

`--runtime-root` accepts the SkillGuard repository root, installed SkillGuard
directory, `scripts` directory, or the internal `skillguard_v2` package. The
runtime resolves these forms to the same executable identity; a mismatch
report includes both the expected and actual identity instead of a bare error.
For a real SkillGuard installation, that identity covers executable scripts,
JSON schemas, Skill instructions, references, TestMesh configuration, and the
compiled contract/check bindings rather than hashing only the inner package.
For the SkillGuard suite, the identity also fails closed unless the sibling
`skillguard-global-router` Skill, current source/compiled contract, manifest,
scripts, and references are all present and readable.

Registry-changing commands use a short-lived exclusive writer lock. A second
live writer blocks, while an abandoned same-machine lock can be recovered and
is reported in the command result.

The declared-reference scanner separately preserves real local Markdown links,
images, reference-style definitions, and explicitly declared local artifacts.
Fenced command examples, inline command/CLI argument values, database URIs or
SQL, undeclared database runtime locations, and transient SkillGuard run, lock,
bootstrap, or test-result output locations are classified as runtime text
instead of being turned into false missing-file blockers. Explicit declarations
and Markdown links remain real references even when they target a runtime path.

## Claim boundary

Portfolio audit and receipts prove only the registry identities and evidence supplied at the named time. They do not execute target work, establish that an installed copy was activated, infer license rights, prove GitHub publication, or guarantee future AI behavior. The registry, resolved-path display, and unredacted operational context are private state and should not be committed to a public skill repository.
