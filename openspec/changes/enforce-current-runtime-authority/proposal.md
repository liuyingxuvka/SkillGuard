## Why

SkillGuard already has one complete current contract path, but daily authority resolution, CLI routing, installation, and global routing still retain former lifecycle branches and retirement tooling. Those extra surfaces can turn an ordinary current implementation change into unrelated history maintenance. That is the same over-broad freshness defect this repository is removing from validation.

The user clarified the desired end state: one daily current authority, one current receipt/impact/TestMesh path, and no compatibility or migration route. Historical shapes may remain only as exact rejection fixtures; version-control history is not a runtime surface.

## What Changes

- Make `.skillguard/contract-source.json`, `.skillguard/compiled-contract.json`, and `.skillguard/check-manifest.json` the only daily runtime-contract authority.
- Replace the public daily authority states with exactly `current` or `blocked`. A target without a complete current trio is blocked until its maintained source is rewritten directly to the current shape.
- Remove `v1_runtime_authority` and `legacy_v1_authority` from the current source and compiled contract shape. Remove live retirement receipts, validators, schemas, renewal chains, and conversion commands from the maintained and installed surface.
- Remove legacy compile/route/run handlers and their route entries from the daily CLI. Old commands and old contract/run shapes are accepted only by explicit negative fixtures and can never execute or close work.
- Remove maintenance refresh and project-upgrade paths that read stale or former records to produce current output. Project adoption accepts complete explicit current inputs and writes the current shape directly.
- Detect former runtime-authority files in a current target as `former_runtime_residual`; never reinterpret them as fallback authority.
- Make compiler, project adoption, provenance, installation, installed parity, global discovery, managed prompt projection, and Portfolio consumers require the same current decision.
- Make exact functional source components the only freshness inputs. Receipts, reports, logs, caches, timestamps, generated status, and other execution outputs stay outside maintained source and cannot invalidate their own evidence.
- Add the existing FlowGuard compatibility-admission gate: covered skill maintenance always uses direct current replacement; ordinary software may model a compatibility reader only when an explicit requirement names the historical document/data/interface and its bounded owner.
- Keep stable current protocols whose schema identifiers happen to end in `.v1` unless they are explicitly named former runtime-authority surfaces. A schema suffix alone does not create a compatibility route.
- Replace the affected canonical SkillGuard and `skillguard-global-router` roots directly with the current trio, remove their live former runtime-authority files, regenerate their current authorities, and install them transactionally.
- Require every other covered skill to be maintained directly in the current shape before it can be reported as current by the global router. Missing current authority remains visible and blocked rather than silently using an old path.

## Capabilities

### New Capabilities

- `current-runtime-authority`: Defines the single current daily authority, former-shape rejection, direct current replacement, current-only consumers, and claim boundary.

### Modified Capabilities

- `universal-execution-depth`: Current execution depth and installation parity no longer depend on retirement history or any former runtime-authority artifact.

## Impact

- SkillGuard contract schemas/compiler, runtime-authority resolver, CLI dispatcher/route index, field-lifecycle records, project adoption, provenance, installation, installed parity, global router, prompt projection, fixtures, and tests.
- SkillGuard and `skillguard-global-router` canonical and installed roots.
- The existing validation-composition and DevelopmentProcessFlow owners plus the TestMesh ownership graph; no new parallel validation framework is introduced.
- Old shapes remain bounded negative-fixture material only. This replacement does not prove target-domain correctness, future AI behavior, publication, or release readiness.
