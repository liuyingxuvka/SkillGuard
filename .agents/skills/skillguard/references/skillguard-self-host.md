# SkillGuard current self-host run

SkillGuard uses a two-stage bootstrap so the verifier does not silently certify itself.

1. The current compiler checks or regenerates only `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` from the FlowGuard model plus confirmed binding source. There is no frozen-old verifier, compatibility reader, or parallel bootstrap stage.
2. Before a run is claimed, the boundary preflight requires exactly one native TestMesh test owner and rejects every nested `skillguard_test_mesh.py` execution wrapper; the parent later performs only plan/aggregation receipt work. It separately validates every registered ordinary long-check policy. The current installation-safety command measured 352.834 seconds in isolated qualification and 563.984 seconds inside complete self-host. Its policy binds both samples, uses their maximum with a rounded 600-second ceiling plus 120 seconds of runtime-variance grace, and the manifest declares 900 seconds. Missing, duplicate, retargeted, invalid, or `<= 720`-second declarations block before execution. A successful self-host result preserves the native-owner boundary record plus the samples, exact declaration, and hash-bound long-check budget record.
3. The current runtime selects the declared maintenance composition, claims a target-local run, locks write targets, and executes only checks bound to ready steps.
4. Every native check result is stored immutably before it can become hard evidence. The receipt verifier confirms run, contract, step, check, execution status, proof fingerprint, and record hash.
5. The single `enforced` closure consumes exact current receipts and is replay-verified. A missing, duplicate, or mismatched closure projection fails closed. A former-format result cannot become an alternate success after a current-format failure.
6. The enforced self-host depth profile freezes SkillGuard's exact declared checks and requires one current immutable terminal-success owner receipt for every check under the same request. Missing, duplicate, stale, skipped, failed, timed-out, cancelled, or cleanup-unconfirmed results cannot satisfy closure; capability validation cannot be relabeled as scheduled production.
7. Run TestMesh `plan_only` once against the frozen source/toolchain snapshot. Pass that immutable plan to the public `owner_execution_only` runner, which validates exact identities/dependencies, verifies planned reuse read-only, and resolves only `will_execute_owner_ids` through the existing single-flight owner authority. Pass the same unchanged plan to `aggregation_only`. Reinvoking the runner may reuse receipts created after freeze but cannot replan, broaden, or repeat an owner process; later verification uses only the read-only aggregation reference and cannot execute or backfill owners.
8. After activation, the installation receipt records the committed transaction and exact installation projection. Portfolio impact accepts the same compiled graph plus changed component ids; caller-authored broad scope is rejected. The global router and managed prompt refresh only when their projection is affected. None of these receipts proves target release or publication.

Run the bootstrap during development and before release; it always uses the same fixed closure:

```powershell
python .agents/skills/skillguard/scripts/skillguard_self_host.py --repository-root .
```

Task runs, check records, receipts, reports, and closure receipts stay under the target project's ignored `.skillguard/` runtime directory. They are evidence for the exact local source and environment only; they are not published contract files.
