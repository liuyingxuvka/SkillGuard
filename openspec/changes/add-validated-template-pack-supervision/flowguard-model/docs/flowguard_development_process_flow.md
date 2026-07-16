# FlowGuard DevelopmentProcessFlow Notes

Use this scaffold to model a development lifecycle as a stateful process.

## What DevelopmentProcessFlow Reviews

- versioned requirements, designs, models, code, tests, docs, release assets,
  adapters, field lifecycle meshes, field projections, replacement
  dispositions, bug-repair closure rows, and route-owner report artifacts;
- ordered development actions that read, write, invalidate, or claim evidence;
- validation evidence and the exact artifact versions it covers;
- UI observed inventory, functional capability coverage, functional-chain,
  source-baseline, done-claim, and real-surface artifact-payload case revisions
  when evidence covers them;
- ContractExhaustionMesh interaction groups, generated combination case ids,
  coverage shard ids, and model coverage receipt ids when evidence covers them;
- verifier changes, such as tests or model files changing after evidence was
  produced;
- freshness rules that propagate upstream changes to downstream artifacts;
- AutoSplit, ModelMesh, or TestMesh evidence ids when split review is
  relevant to the process claim;
- whether done, release, archive, or publish claims have current evidence;
- independent freshness for the shadow workspace, formal repository, editable
  package installation, installed skill suite, and local Git version;
- peer-write observations and post-write revalidation so synchronization
  preserves concurrent work instead of overwriting or rolling it back;
- the coverage-complete revalidation needed when evidence is stale or missing.
  Revalidation recommendations include the route that produced prior evidence,
  proof-artifact requirement, freshness gap codes, and claim scopes blocked
  until rerun. A measured finite candidate set may support a minimum claim;
  estimated inputs support only a preferred set.
- a conditional internal process optimization only when explicitly requested,
  several equivalent routes exist, rework risk is material, or a diagnostic
  boundary choice matters;
- a diagnostic boundary (`targeted`, `declared_complete`, or `budgeted`) and
  execution mode (`sequential` or `safe_parallel`) without prescribing one
  universal order;
- stable Finding Ledger references, relation-backed root-cause repair groups,
  visible hard blockers, and current affected-obligation revalidation.

For field-bearing work, add `PROCESS_ARTIFACT_FIELD_LIFECYCLE`,
`PROCESS_ARTIFACT_FIELD_PROJECTION`, `PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION`,
or `PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE` artifacts when those rows change. Pair
them with `PROCESS_EVIDENCE_FIELD_LIFECYCLE`,
`PROCESS_EVIDENCE_FIELD_PROJECTION`, `PROCESS_EVIDENCE_MODEL_MISS_REVIEW`, or
`PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE` evidence so later done/release claims can
see when field evidence became stale.

For UI work that claims user-visible functions are implemented or runnable,
track capability inventories or output-contract/binding rows with
`PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE` and pair them with
`PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE`. A later UI model,
feature-contract, task, output, or implementation change should stale that
evidence before release confidence.

## Route Owner Boundary

This is the development-process simulator front door and execution-freshness
owner. It can reference evidence produced by ModelMesh, TestMesh, StructureMesh,
Model-Test Alignment, LongCheck, or Conformance Adoption through evidence ids
and freshness metadata. It does not inspect, supervise, replace, or repair
those routes. If route-owner evidence is failed, stale, skipped, missing, or
progress-only, this route keeps that lifecycle gap visible for the current
process claim.

The internal mode order is `plan_detailing` -> `strategy_selection` ->
`agent_workflow` -> `execution_freshness`. The optimization mode stays inactive
for ordinary work. When active, it first proves hard equivalence, then chooses
one diagnostic boundary and one execution mode. Hard blockers always stop
invalid downstream work, and material evidence always stales the decision.

When direct model/test evidence is large, incomplete, slow, broad,
progress-only, or release-only, run AutoSplit, ModelMesh, or TestMesh as its own
route and consume that route's evidence id or proof artifact here. Do not copy
AutoSplit metrics onto `ProcessEvidence`.

Use this route when development ordering, artifact overwrite, verification
freshness, or release readiness is the risk. It is not mandatory for every
small edit and it does not make FlowGuard a task orchestrator.
