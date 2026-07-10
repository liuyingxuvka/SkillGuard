# SkillGuard V2 Portfolio Runtime

The portfolio runtime is a private, machine-readable parent gate for one-skill-at-a-time maintenance. It does not replace target contracts or execute target-domain work. It records which maintained targets are current under the exact active SkillGuard runtime and keeps excluded, pending, blocked, stale, and revalidation-required entries visible.

## Lifecycle and queue boundary

- `active_owned`, `active_adopted`, and `pending_adoption` entries have a unique non-negative `order` and participate in graduation.
- `retired_private`, `excluded_private`, and `excluded_system` entries have `order: null`, `graduation_status: excluded`, and an explicit reason. They never block or silently enter the active queue.
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
| `representative_jobs` | graduation evidence and target entry | target verifier, then `graduate-portfolio` | coverage check and parent receipt | Every job names covered capability ids and direct evidence refs. The canonical job set hashes to the full receipt's `coverage_fingerprint`; an uncovered declared capability blocks graduation. |
| `full_run_receipt` | target entry | `graduate-portfolio` | audit, reuse, later graduation | Current only when source, contract, command, environment, coverage, and Guard identities match. Historical receipt content is preserved when status becomes `revalidation_required`. |
| `reuse_ticket` | target entry | `issue-portfolio-reuse-ticket` | audit and parent gate | Allowed only for a registered, non-broad, non-intersecting Guard change with unchanged five-part identity. The ticket must revalidate against the append-only change history, previous full receipt, and active Guard. |
| `graduation_status` | target entry | impact, reuse, graduation | every portfolio command | `current` is verifier-owned. Guard changes transition old current entries to `revalidation_required`; target evidence or a valid reuse ticket is required to restore currentness. |
| `failure_classification` | target entry/evidence | target maintenance workflow | graduation and reports | A non-null unresolved failure classification blocks graduation. |
| `guard_change_history` | registry | `mark-portfolio-impact` | audits and final report | Append-only semantic history; it records affected feature tags and broad-change scope without claiming revalidation. |

## Command sequence

1. Run `audit-portfolio` before maintaining a target. An incomplete registry is not a green portfolio.
2. After any SkillGuard behavior change, write a `skillguard.guard_change.v1` record and run `mark-portfolio-impact --write`. Every old current entry becomes `revalidation_required`; non-intersecting entries still need explicit reuse proof.
3. Use `issue-portfolio-reuse-ticket` only when the change is not broad, affected tags do not intersect, and source, contract, command, environment, and coverage fingerprints are unchanged.
4. Finish the target capability inventory, then run real positive, invalid-input, recovery/resume, out-of-scope, native, artifact, and judged-quality work. Each representative job must bind covered capability ids to direct evidence refs; the canonical job set is the receipt coverage fingerprint.
5. Run `graduate-portfolio --write`. The command blocks if any declared capability is uncovered, the target evidence is incomplete, its Guard identity differs, or any prior active entry is not current. A successful command writes the exact parent receipt before atomically updating only that target.
6. Rerun `audit-portfolio --candidate <next-skill-id>` before proceeding to the next target.

`--runtime-root` accepts the SkillGuard repository root, installed SkillGuard
directory, `scripts` directory, or the internal `skillguard_v2` package. The
runtime resolves these forms to the same executable identity; a mismatch
report includes both the expected and actual identity instead of a bare error.
For a real SkillGuard installation, that identity covers executable scripts,
JSON schemas, Skill instructions, references, TestMesh configuration, and the
compiled contract/check bindings rather than hashing only the inner package.

Registry-changing commands use a short-lived exclusive writer lock. A second
live writer blocks, while an abandoned same-machine lock can be recovered and
is reported in the command result.

## Claim boundary

Portfolio audit and receipts prove only the registry identities and evidence supplied at the named time. They do not execute target work, infer license rights, prove GitHub publication, or guarantee future AI behavior. The registry is private operational state and should not be committed to a public skill repository when it contains local source locations or private repository metadata.
