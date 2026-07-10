# SkillGuard V2 generic supervisor

The generic supervisor is the executable AI work contract entrypoint. It does not reimplement a target skill. It selects only routes already declared by the target FlowGuard model, claims a target-local run, invokes the bound native checks, validates the bound artifacts, and records the target skill's own action results as hard, witnessed, or judged receipts.

## Command

```text
python .agents/skills/skillguard/scripts/skillguard_v2_supervise.py <skill-root> <packet.json> --target-root <target-root> --repository-root <repository-root>
```

The target skill must already contain a confirmed `.skillguard/contract-source.json` and its declared FlowGuard model. Compilation regenerates `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` before the run claim.

## Packet

```json
{
  "request": {
    "route_ids": ["route:chosen-entry", "route:delivery"],
    "compose": true,
    "request": "the concrete target outcome",
    "claim_scope": "functional",
    "write_targets": ["."]
  },
  "profiles": ["functional"],
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

File, directory, JSON, image, document, and screenshot outputs are declared by the contract and validated from `target-root`. Witness artifacts may use the step witness or an `artifact_witnesses` entry. A screenshot witness must name the exact `surface_id`, `state_id`, and the prior interaction receipt step so a file from the wrong surface or state cannot close the obligation.

## Evidence authority

- `hard`: produced only from a stored, executed, passing declared check and any current artifact records attached to it.
- `witnessed`: requires a concrete executor, target, input fingerprint, output fingerprint, and limitations. The supervisor also retains the supporting hard check receipts.
- `judged`: requires a declared versioned rubric, evaluator identity, input fingerprint, conclusion, limitations, and a confidence boundary for self-review. Supporting hard checks do not promote the judgment to hard proof.
- `skip`: allowed only for a model-declared optional step and only after passed condition and verifier receipts already exist in the same run.

The runtime verifies that the receipt used to pass a step has the action's required evidence class. A caller cannot pass a judged or witnessed step using a generic model assertion.

## Closure boundary

The supervisor reports only selected routes and requested monotonic profiles. Unselected routes, missing browser states, skipped checks, stale fingerprints, external installation, Git history, GitHub publication, and future AI behavior remain outside the closure unless separately declared and proven.
