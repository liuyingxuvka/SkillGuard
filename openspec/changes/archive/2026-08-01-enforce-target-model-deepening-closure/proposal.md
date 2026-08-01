## Why

SkillGuard already requires target-owned depth profiles, exact check inventories, current receipts, and clean consumer projections. The previous implementation nevertheless treated membership in the generic `native_check_ids` inventory as sufficient and used an abstract Boolean model as the apparent proof. That does not establish that the target's actual iterative model-deepening check ran. SkillGuard must identify that check explicitly and project its exact current producer receipt without interpreting domain semantics.

## What Changes

- Add an explicit `model_deepening_check_id` to affected target depth profiles and bind it to one declared target-owned check.
- Add a typed model-deepening result to the target execution receipt, including exact check, execution-owner, request, freshness, terminal disposition, receipt id, and receipt hash.
- Add known-bad fixtures proving that self-reported understanding, open addressable gaps, stale receipts, and no-progress iterations block graduation.
- Replace SkillGuard's abstract-Boolean-only check with runtime tests of receipt selection, currentness, owner binding, and default-deny behavior.
- Keep SkillGuard domain-neutral and consume target-native receipts opaquely.
- Refresh local source/compiled contract/projection parity and author-side documentation.

## Capabilities

### New Capabilities
- None. This extends the existing universal execution-depth supervision.

### Modified Capabilities
- `universal-execution-depth`: require declared target-native iterative closure checks.

## Impact

- SkillGuard contract schema/compiler, execution-depth runtime, receipt schema, contract-source inputs, depth profiles, fixtures, tests, references, and local consumer staging.
- No domain evaluator, understanding-level schema, cross-unit receipt reuse, or consumer SkillGuard dependency.
