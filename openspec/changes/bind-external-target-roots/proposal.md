## Why

`check-contract` and `check-skill` currently conflate the target member directory with the canonical repository root. A nested external skill can therefore resolve repository-relative contract paths from the wrong directory, while static reference checks remain bound to SkillGuard's own repository.

## What Changes

- Add one explicit `--repository-root` plus `--target` member binding to both commands.
- Compile and resolve repository-relative material only from that declared canonical root, while requiring the member target to remain inside it.
- Preserve the deterministic standalone `--target .` case where repository root and member root are the same directory.
- **BREAKING** Remove `check-contract --target-root` as a successful alias; missing or mismatched bindings block instead of guessing or falling back.
- Add a portable, privacy-safe binding projection schema, focused regressions, FlowGuard model-miss coverage, and synchronized command documentation.

## Capabilities

### New Capabilities

- `external-target-binding`: Defines canonical repository-root/member-root binding for read-only target contract and static checks.

### Modified Capabilities

None.

## Impact

- `check-contract` and `check-skill` CLI arguments and JSON reports.
- Shared target/reference resolution inside `checker_engine.py`.
- One new binding schema, focused tests, README/workflow examples, OpenSpec artifacts, and the existing executable-contract FlowGuard owner model.
- No portfolio replacement, frozen validation runner, installation, router refresh, publication, or release behavior.
