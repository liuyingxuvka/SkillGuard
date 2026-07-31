## Context

The v0.4.2 tag and installed source are current, but branch CI proves a documentation/release-evidence defect. FlowGuard adoption and CI pins also lag the available governed toolchain.

## Goals / Non-Goals

**Goals**

- Make the exact v0.4.2 feature baseline green before new behavior.
- Bring FlowGuard adoption and CI pins to 0.65.1.
- Establish observed model authority and publish a patch baseline.

**Non-Goals**

- No assurance diagnostics or contract semantic change.
- No rewrite of historical tags.

## Decisions

1. Treat the existing branch failure as baseline evidence, not as a feature regression.
2. Correct README/CHANGELOG currentness and CI pins directly.
3. Bootstrap observed authority only from passing current model evidence.
4. Publish v0.4.3 as the repaired patch baseline.

## Risks / Trade-offs

- Current FlowGuard can reveal legacy artifacts; explicit upgrades are required and failures remain visible.

## Migration Plan

Repair documentation/version evidence, upgrade FlowGuard records/CI, validate, activate observed authority, and release v0.4.3 before diagnostics are applied.
