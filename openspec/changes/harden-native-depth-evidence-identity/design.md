## Context

The current worktree contains two kinds of changes:

1. valuable generic supervision work: exact check ownership, immutable receipts, observation identity, evidence-domain separation, affected-only freshness, branch closure, transactional installation, TestMesh aggregation, and read-only receipt consumption;
2. an incorrect Guard-specific layer: purpose contracts, protected failures, semantic-obligation universes, native findings, and mandatory positive/shallow calibration applied to every maintained skill.

This design removes only the second category and retains the first. It extends the existing SkillGuard/OpenSpec/FlowGuard workflow rather than creating a replacement workflow.

## Goals / Non-Goals

**Goals**

- Give SkillGuard one fixed universal job: execute and reconcile the checks the target skill declares.
- Make missing, failed, skipped, timed-out, stale, duplicated, foreign, or unowned declared checks visible blockers.
- Preserve target-native ownership of routes, domain actions, judgments, models, oracles, and test meaning.
- Preserve exact execution, receipt, freshness, installation, branch, and consumer identity.
- Prove with a non-Guard fixture that no purpose statement or Guard-style counterexample is required.

**Non-goals**

- Deciding what PhysicsGuard, LogicGuard, SourceGuard, TraceGuard, WorldGuard, or FlowGuard should prevent.
- Interpreting a target's domain result.
- Requiring every skill to have good/bad pairs, semantic obligations, or a model universe.
- Adding a `core`, `guard`, `strict`, `advisory`, or other selectable purpose mode.

## Fixed Ownership Model

```text
Target skill owns:
  declared checks + commands + inputs + expected terminal results + domain meaning

SkillGuard owns:
  exact inventory + one execution owner + current execution + immutable receipts
  + freshness + visible gaps + installation/consumer projection + closure accounting
```

The target may declare any useful test family. SkillGuard treats each declaration uniformly. The absence of a Guard-style test category is not a mode and is not an error unless the target's own contract declares that category as required.

## Decisions

### 1. Declared-check inventory is the universal denominator

Every maintained target supplies one exact check manifest. Each required check has:

- `check_id` and `semantic_check_id`;
- exactly one `execution_owner_id`;
- command or native owner binding;
- exact functional inputs and dependencies;
- covered target-declared obligation IDs;
- expected terminal result;
- evidence domain and immutable receipt location.

SkillGuard reconciles `declared = executed_terminal + visible_not_run`. A smaller caller-selected set cannot become complete evidence. Duplicate owner declarations, owner cycles, missing results, or a result for an undeclared check block closure. Several semantic checks may share one compiler-proven execution owner when their owner behavior, toolchain, inputs, and evidence domain are identical; the frozen plan retains every `check_id` and projection while the owner process runs only once.

### 2. SkillGuard does not own target-domain purpose or findings

The following fields are removed from current SkillGuard authority:

- `purpose_contract_policy`
- `purpose_contract_identity`
- `protected_failure_claim_ids`
- `semantic_obligation_ids`
- `important_semantic_obligation_ids`
- `native_finding_identity`
- `semantic_obligation_results`
- `uncovered_semantic_obligation_ids`

Their schemas, runtime producers, prompt requirements, self-host fixtures, and tests are removed or rewritten. They may survive only as exact rejection fixtures when needed to prove the current schema rejects them.

Guard repositories may use similarly named domain-native concepts under their own schemas and namespaces. SkillGuard sees only the resulting declared check and receipt.

### 3. Request and observation identities remain generic

The top-level `request_fingerprint` is restored. A native contribution retains:

```text
target_skill_id
+ target_contract_hash / profile_hash
+ native_owner_id / native_route_id / native_check_id
+ run_id
+ target_obligation_ids
+ request_fingerprint
+ native_receipt_id / native_receipt_hash / native_receipt_artifact_ref
+ native_observation_locator
+ evidence_domain
```

`native_observation_locator` identifies target-owned observed material without claiming that SkillGuard understands its domain semantics. Numeric-only or mechanically renamed ranges remain invalid when the target declares content-addressed observation identity.

### 4. No universal positive/shallow calibration

SkillGuard no longer has a special mandatory calibration block. A target may declare checks named positive, negative, good, bad, replay, mutation, or any other category. Those checks are ordinary manifest members and follow the same execution/freshness rules.

SkillGuard's own regression tests include one synthetic failure: a required declared check is omitted, so supervision must fail. This proves SkillGuard's own behavior; it does not force every target to author the same fixture class.

### 5. Existing generic lifecycle protections remain

The following stay current:

- typed evidence domains where declared by the target;
- one immutable terminal success per exact execution identity;
- failed attempts never populate the reusable success slot;
- branch-conditional closure and verifier-owned applicability where the target declares branches;
- transactional whole-tree installation, rollback, and installed parity;
- affected-only invalidation from exact content-component edges;
- one final full validation owner after source/toolchain freeze;
- immutable TestMesh planning, public frozen-plan owner execution, aggregation, and read-only receipt consumption;
- exact shared-owner check projection: one owner receipt may cover several target-declared semantic projections only when the complete ordered `check_ids` and projection hashes remain frozen and aggregation-visible;
- truthful process-start accounting: a post-launch persistence error remains a failed owner attempt with `process_started=true` and a nonzero execution count;
- no background retry, scheduled task, or mutable-worktree full validation.

### 6. Field lifecycle disposition

Removed Guard-specific fields have disposition `delete_and_reject`. Generic replacements are:

| Removed field | Current generic owner |
|---|---|
| nested purpose request identity | top-level `request_fingerprint` |
| semantic locator naming | `native_observation_locator` |
| semantic results | target-declared check results |
| uncovered semantic obligations | missing target-declared obligation/check IDs |
| positive/shallow calibration authority | ordinary target-declared checks |

No alias, dual reader, fallback, or optional compatibility mode is allowed.

## FlowGuard Model

```mermaid
flowchart LR
  A["Load exact target contract"] --> B["Freeze declared check inventory"]
  B --> C["Assign one owner per check"]
  C --> D["Freeze exact TestMesh plan"]
  D --> E["Verify planned reuse; execute only will_execute owners"]
  E --> F{"Terminal result?"}
  F -->|"pass"| G["Store immutable receipt"]
  F -->|"fail / skip / timeout / not-run"| H["Keep exact visible blocker"]
  G --> I["Aggregate from the unchanged plan"]
  H --> I
  I --> J{"Every required declaration current?"}
  J -->|"yes"| K["Bounded closure"]
  J -->|"no"| L["Block; target owns repair"]
```

Edges mean execution order, result consumption, or closure blocking. The model contains no branch that selects a Guard purpose mode.

## Migration Plan

1. Revise this existing OpenSpec change and verification contract.
2. Remove Guard-specific purpose/calibration fields from SkillGuard source authority and runtime.
3. Rewrite the native-depth FlowGuard child model as declared-check supervision.
4. Regenerate the self-contract and check manifest.
5. Replace purpose tests with generic supervision and retired-field rejection tests.
6. Run focused compiler, schema, model, and ordinary-skill regressions.
7. Transactionally install and verify the canonical SkillGuard tree.
8. Freeze inputs, run one final full validation owner, and let OpenSpec consume its receipt.

## Risks

- **Intertwined unfinished work:** generic and purpose-specific changes share files. Mitigation: remove fields and branches surgically; never reset the dirty worktree.
- **Old generated contracts remain stale:** regeneration is mandatory after source correction.
- **Guard repositories temporarily depend on SkillGuard purpose APIs:** migrate PhysicsGuard to its native owner before deleting the final installed projection; other Guard repositories are upgraded in the fixed sequence.

## Open Questions

None. The user fixed the ownership and no-mode decisions.
