# SkillGuard current self-host run

SkillGuard uses one ordered claim-plan-execute-aggregate path so the verifier
does not silently certify itself or run every check before impact planning.

1. The current compiler checks or regenerates only `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` from the FlowGuard model plus confirmed binding source. There is no frozen-old verifier, compatibility reader, or parallel bootstrap stage.
2. Before a run is claimed, the boundary preflight requires exactly one native TestMesh test owner and rejects every nested `skillguard_test_mesh.py` execution wrapper; the parent later performs only plan/aggregation receipt work. It separately validates every registered ordinary long-check policy. The installation-safety history includes 352.834-second and 563.984-second terminal samples plus a later 900.157-second censored lower bound after formerly early-failing installation paths began completing. The policy therefore uses a conservative 2400-second ceiling plus 300 seconds of runtime-variance grace, and the manifest declares 3000 seconds. Missing, duplicate, retargeted, invalid, or `<= 2700`-second declarations block before execution. A successful self-host result preserves the native-owner boundary record plus the samples, exact declaration, and hash-bound long-check budget record.
3. The current runtime selects the declared maintenance composition and claims
   a target-local run while launching zero checks. The public self-host CLI
   ends here and hands the exact run root to TestMesh.
4. Every native check result is stored immutably before it can become hard evidence. The receipt verifier confirms run, contract, step, check, execution status, proof fingerprint, and record hash.
5. The single `enforced` closure consumes exact current receipts and is replay-verified. A missing, duplicate, or mismatched closure projection fails closed. A former-format result cannot become an alternate success after a current-format failure.
6. The enforced self-host depth profile freezes SkillGuard's exact declared checks and requires one current immutable terminal-success owner receipt for every check under the same request. Missing, duplicate, stale, skipped, failed, timed-out, cancelled, or cleanup-unconfirmed results cannot satisfy closure; capability validation cannot be relabeled as scheduled production.
7. Run TestMesh `plan_only` once against the frozen source/toolchain snapshot. Planning must preflight every selected owner's selectors, declared target-input roles, toolchain, and semantic launch identity before any process can start. Run-local paths and attempt ids stay outside semantic identity, and order-only relationships are not receipt dependencies. Pass that immutable plan to the public `owner_execution_only` runner, which validates exact identities/dependencies, verifies planned reuse read-only, and resolves only `will_execute_owner_ids` through the existing single-flight owner authority. Pass the same unchanged plan to `aggregation_only`. Reinvoking the runner may reuse receipts created after freeze but cannot replan, broaden, or repeat an owner process; later verification uses only the read-only aggregation reference and cannot execute or backfill owners.
8. After activation, the installation receipt records the committed author installation or clean consumer transaction and its exact projection. Portfolio impact accepts the same compiled graph plus changed component ids; caller-authored broad scope is rejected. The private author router refreshes only when its projection is affected and never becomes consumer proof. None of these receipts proves target release or publication.

Claim the current run during development and before release. This command
always reports `execution_count: 0`; owner execution is accepted only from the
subsequent frozen TestMesh plan:

```powershell
python .agents/skills/skillguard/scripts/skillguard_self_host.py --repository-root . --claim-only
```

Task runs, check records, receipts, reports, and closure receipts stay under the explicit SkillGuard author repository's private evidence roots. They are evidence for the exact local source and environment only; they are not consumer or published contract files.
