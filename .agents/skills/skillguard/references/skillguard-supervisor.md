# SkillGuard current generic supervisor

The generic supervisor is the executable AI work contract entrypoint. It does not reimplement a target skill. It selects only routes already declared by the target FlowGuard model, claims a target-local run, invokes the bound native checks, validates the bound artifacts, and records the target skill's own action results as hard, witnessed, or judged receipts.

## Command

```text
python .agents/skills/skillguard/scripts/skillguard_supervise.py <skill-root> <packet.json> --target-root <target-root> --repository-root <repository-root> --run-state-root <repository-level-run-state-root> --owner-evidence-root <repository-level-owner-evidence-root>
```

`--owner-evidence-root` names the one persistent authority for immutable check-owner receipts. Give every maintained target in one repository the same repository-level short path (for example `work/verification/owner-evidence`) when the skill itself is deeply nested. This is a storage binding, not a selectable supervision mode; it does not change declared checks, dependencies, execution owners, or closure rules. If it is omitted, the sole default remains `<repository-root>/work/verification/owner-evidence`.

`--run-state-root` names the one directory that owns the claimed run, progress, diagnostics, step receipts, and closure for this target invocation. Bind each deeply nested maintained skill to one repository-level path-budgeted short run root (for example `work/r/02`, with the skill id retained inside the contract and receipts rather than repeated in the directory name). Budget the complete descendant path, not only the supplied root. It cannot alter the contract, route, checks, evidence owner, or closure profile. If it is omitted, the existing target-local run root remains authoritative.

The target skill must already contain a confirmed `.skillguard/contract-source.json` and its declared FlowGuard model. Compilation regenerates `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` before the run claim.

## Packet

Use `supervision_mode: close` for ordinary one-stage contracts. Route-conditional scheduled production uses two calls with the same `request`: first `stage_depth`, then `close`.

```json
{
  "supervision_mode": "close",
  "request": {
    "route_ids": ["route:chosen-entry", "route:delivery"],
    "compose": true,
    "request": "the concrete target outcome",
    "claim_scope": "enforced",
    "write_targets": ["."]
  },
  "profiles": ["enforced"],
  "steps": {
    "step:runtime-witness": {
      "witness": {
        "witness_kind": "ui_interaction",
        "target_id": "surface-id",
        "executor_id": "browser-or-tool-id",
        "input": {},
        "output": {},
        "limitations": []
      }
    },
    "step:quality-review": {
      "judgment": {
        "rubric_id": "rubric:declared-id",
        "rubric_version": "1",
        "evaluator_id": "reviewer-id",
        "input": {},
        "conclusion": "bounded conclusion",
        "limitations": ["explicit limitation"],
        "self_review": true,
        "confidence_boundary": "why this cannot support a stronger claim"
      }
    },
    "step:conditional-work": {
      "skip": {
        "reason": "why the declared condition is not applicable",
        "condition_step_id": "step:prior-condition-proof",
        "verifier_step_id": "step:prior-verifier-proof"
      }
    }
  }
}
```

Stage 1 must use `"supervision_mode": "stage_depth"`, `"profiles": []`, and no `native_terminal`. Its `status` is `staged`, never passed, and its `target_execution_depth_receipt` is the only receipt the target terminal builder may bind.

Stage 2 must use `"supervision_mode": "close"`, exactly `"profiles": ["enforced"]`, and for a selected branch contract:

```json
{
  "native_terminal": {
    "receipt_ref": {
      "path_token": "run_root",
      "relative_path": "native-terminal/receipts/native-noop-....json"
    },
    "expected_route_id": "route:target-native-owner",
    "expected_branch_id": "no-update"
  }
}
```

Generate that receipt from the stage-1 run with `build_target_native_terminal_receipt(...)` and persist it with `write_target_native_terminal_receipt(...)`. Do not hand-author or pre-guess the depth id/hash. The builder binds the fixed `enforced` closure and derives `closure_disposition`. An intermediate authorization is `non_terminal_authorization`; it cannot be replayed as terminal completion. The later composed run produces its own `terminal_completion` receipt. A legitimate no-op is accepted only when the target's current branch contract supplies verifier-owned applicability evidence. The close phase resumes the same run, sees no ready completed steps, reuses the exact depth receipt, and performs closure only.

File, directory, JSON, image, document, and screenshot outputs are declared by the contract and validated from `target-root`. Witness artifacts may use the step witness or an `artifact_witnesses` entry. A screenshot witness must name the exact `surface_id`, `state_id`, and the prior interaction receipt step so a file from the wrong surface or state cannot close the obligation.

## Evidence authority

- `hard`: produced only from a stored, executed, passing declared check and any current artifact records attached to it.
- `witnessed`: requires a concrete executor, target, input fingerprint, output fingerprint, and limitations. The supervisor also retains the supporting hard check receipts.
- `judged`: requires a declared versioned rubric, evaluator identity, input fingerprint, conclusion, limitations, and a confidence boundary for self-review. Supporting hard checks do not promote the judgment to hard proof.
- `skip`: allowed only for a model-declared optional step and only after passed condition and verifier receipts already exist in the same run.

The runtime verifies that the receipt used to pass a step has the action's required evidence class. A caller cannot pass a judged or witnessed step using a generic model assertion.

When the compiled contract has an enforced `depth_profile`, the supervisor freezes the target's exact declared-check inventory. Each check must resolve to exactly one execution owner and one current terminal-success receipt for the same request. The packet cannot assert pass status, receipt identity, provider readiness, runtime identity, or final depth status.

The supervisor reconciles declared and observed check ids exactly. A missing, duplicate, failed, skipped, stale, timed-out, cancelled, cleanup-unconfirmed, owner-mismatched, or request-mismatched result blocks receipt issuance. SkillGuard does not classify the target or interpret check names, fixtures, or domain oracles. Those remain target-owned.

`--repository-root` and `--target-root` are not aliases. The former owns maintained skill and contract inputs; the latter owns this task's data and artifacts. The supervisor binds both through portable content identities. For scheduled production it additionally verifies the exact current installation receipt and installed-runtime identity.

## Closure boundary

The supervisor reports only selected routes and the fixed `enforced` closure. Unselected routes, missing browser states, skipped checks, stale fingerprints, external installation, Git history, GitHub publication, and future AI behavior remain outside the closure unless separately declared and proven.
