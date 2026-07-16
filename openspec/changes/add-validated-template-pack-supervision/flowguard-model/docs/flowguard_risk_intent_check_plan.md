# FlowGuard Risk Intent CheckPlan Notes

Use this scaffold when the main risk should be named before modeling.

## Risk Intent

Record:

- failure modes;
- protected error classes;
- protected harms;
- state and side effects that must be visible;
- completion evidence;
- known-bad cases that should fail on broken models, with current proof;
- public/local template ids used, or a no-match reason;
- template harvest closure: written, merged, duplicate-linked, or an accepted not-harvestable reason;
- adversarial inputs or retries;
- hard invariants;
- blindspots.

## Calibration

This template reports model-level confidence only. Add conformance replay or
equivalent real-code evidence before claiming production confidence.
The run script also shows how to bridge the summary report into MaintenanceScan
so route-owned gaps remain visible as scoped or required follow-up actions.
