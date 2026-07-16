# FlowGuard Plan Detailing Notes

Use this scaffold when the work starts as a rough idea or short AI-generated
plan. The detail rows are the bridge between prose and FlowGuard checks.

## What To Fill In

- goal and scope;
- current source evidence;
- risk surfaces and out-of-scope reasons;
- artifacts that may be read, written, validated, or invalidated;
- state and side-effect surfaces that the behavior model must see;
- ordered steps with receipts and evidence gates;
- validation requirements and expected evidence ids;
- for UI completion plans, explicit evidence kind
  `ui_functional_capability_coverage` plus the capability inventory, output
  contracts, implementation bindings, and scoped omissions it covers;
- failure/retry/rework branches;
- human-review questions;
- final claim boundary.

Passing this plan-detail review means the plan is structured enough to proceed.
It does not prove the implementation is complete; downstream FlowGuard routes,
tests, replay, and evidence ledgers still own their proof.
