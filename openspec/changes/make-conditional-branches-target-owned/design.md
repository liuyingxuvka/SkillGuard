## Context

Conditional closure is represented in target contracts through `route_branch_requirements`: each target owns its route IDs, branch IDs, required obligations, and verifier-backed `not_applicable` rules. SkillGuard nevertheless duplicates one historical Khaos Brain update policy in two universal modules. The compiler requires four literal branch names, and the native-terminal runtime classifies and accepts branches through the same literal allowlist. The runtime also assumes every conditional terminal is scheduled production even though execution depth already supports non-production evidence domains.

The current Khaos Brain contract intentionally has only two branches: `no-update` and `explicit-manual-update`. Its manual path is authorized in the current conversation and must not gain a prepared state, waiting state, scheduled identity, or compatibility branch merely to satisfy SkillGuard.

## Goals / Non-Goals

**Goals:**

- Make the target contract the sole authority for conditional branch identifiers and obligation disposition.
- Preserve fail-closed enforced closure: every conditional obligation is explicitly applicable or verifier-approved as not applicable on every branch.
- Derive terminal classification from target-declared applicability rules, not lexical branch names.
- Bind the native terminal to the exact current passing depth receipt and inherit its evidence domain.
- Continue to validate installation identity when, and only when, that evidence domain is `scheduled_production`.
- Directly replace the current behavior with no aliases, legacy branch map, or fallback reader.

**Non-Goals:**

- SkillGuard will not decide what a branch means in a target domain.
- SkillGuard will not manufacture current-conversation authorization or define a generic manual-update protocol; the target's native owner and checks remain responsible.
- This change does not relax declared-check ownership, receipt freshness, closure profiles, or installation parity.
- This change does not repair the separate missing FlowGuard suite-map adoption artifact in the SkillGuard repository.

## Decisions

### 1. The enforced branch projection is the only branch inventory

The compiler will use the exact `(native_route_id, branch_id)` pairs declared consistently across closure profiles. It will not compare them with a SkillGuard-owned name set. Unknown branches remain impossible at runtime because `_profile_route_requirement` requires exactly one matching target declaration.

Alternative considered: add the new Khaos branch to the hard-coded allowlist. Rejected because it preserves duplicate authority and retired behavior.

### 2. Conditional obligations must be total and genuinely conditional

For every enforced route/branch pair, each `conditional: true` obligation must be either active in that branch or named by exactly one verifier-backed `not_applicable` rule. Across the complete branch universe, each conditional obligation must be active in at least one branch and not applicable in at least one branch. This replaces the historical assumptions that three named branches are no-ops and one named branch is completing.

Alternative considered: accept any arbitrary branch map without cross-branch checks. Rejected because a target could silently omit an obligation or mark it unreachable everywhere.

### 3. Terminal kind is derived structurally

A branch with one or more verifier-backed `not_applicable` rules produces a conditional-no-op receipt and applicability receipts. A branch with no applicability rules produces a completed-branch terminal receipt. Both represent terminal completion; neither is inferred from its name.

### 4. Native terminal inherits the depth receipt evidence domain

The terminal builder selects exactly one current `EXECUTION_DEPTH_PASS` matching target, contract, owner, run, route check, and run identity. It copies the depth receipt's evidence domain. For `scheduled_production`, the existing exact installation identity is required and reverified. For non-scheduled domains, a scheduled identity is forbidden and remains empty. This lets target-native checks bind manual authorization without teaching SkillGuard domain-specific manual semantics.

### 5. Direct replacement only

The code, schemas, fixtures, and documentation will move together. No compatibility constants, old branch aliases, migration command, or dual parser will remain. Historical receipts are not current execution authority and are not read through an alternate path.

### 6. Verified forward replacement breaks an unrecoverable historical-install deadlock

Ordinary recovery continues to require the exact recorded backup identity. If both a historical head's active tree and its backup have drifted, restoration remains blocked. When a separately prepared stage has current authority, exact canonical parity, and a passing smoke receipt, activation may classify the non-empty current active tree as replacement-only input, mark the historical head committed for chain continuity, and let the new transaction snapshot that exact tree before replacement. The drifted tree never becomes validation evidence or an alternate runtime authority.

## Risks / Trade-offs

- [Risk] A previously accepted target depended on the accidental literal branch set. → The compiler will now report exact missing disposition or branch ownership findings; the target must declare its real current contract.
- [Risk] Generic totality checks could expose incomplete existing conditional fixtures. → Update fixtures to explicit arbitrary branch names and keep negative tests for omission, overlap, non-monotonicity, and unverifiable not-applicable claims.
- [Risk] Non-scheduled conditional closure could accidentally skip installation verification. → Installation verification remains mandatory for the `scheduled_production` evidence domain and scheduled identity is forbidden elsewhere.
- [Risk] Receipt schema/code drift. → Update schema assets and run the native contract, compiler, closure, self-host, and installation parity checks before installation.
- [Risk] Forward recovery could hide an unrestorable historical backup. → Permit it only during activation of a separately verified stage, require a non-empty safe directory, preserve the exact active tree as the new transaction backup, and retain explicit replacement-recovery provenance.

## Migration Plan

1. Update the OpenSpec contract and regression fixtures.
2. Replace compiler branch-name logic with target-owned totality checks.
3. Replace native-terminal branch-name and scheduled-only logic with structural classification and evidence-domain inheritance.
4. Run focused tests and the SkillGuard native self-host checks.
5. Install the whole current SkillGuard tree through its official staged installer and verify parity.
6. Recompile Khaos Brain's update skill; do not restore any retired branch.

Rollback is the SkillGuard installer's staged backup/restore of the immediately previous installed tree. There is no product-level compatibility route.

## Open Questions

None. The target contract and the current depth receipt already contain the required branch and evidence authority.
