# SkillGuard Project Adoption Protocol

## Purpose

Project adoption makes SkillGuard maintenance portable with the repository. A future AI or another computer should be able to discover that the repository's skills are maintained through SkillGuard, locate the canonical SkillGuard source, preserve target-native authority, and fail visibly when maintenance governance is unavailable or stale.

Canonical repository: <https://github.com/liuyingxuvka/SkillGuard>

## Managed artifacts

Project adoption owns exactly two repository-root artifacts:

- `.skillguard/project.json`: deterministic adoption manifest.
- the text between `<!-- BEGIN MANAGED SKILLGUARD PROJECT RULES -->` and `<!-- END MANAGED SKILLGUARD PROJECT RULES -->` in `AGENTS.md`.

Everything outside those markers belongs to the project and must be preserved byte-for-byte except for the minimum newline needed to insert the block.

The manifest records the project id, canonical repository URL, SkillGuard version, managed skill paths, skill ids, the fixed `native-integrated` marker, native owner ids, route status, native-route evidence path, managed block hash, manifest hash, and claim boundary.

## Lifecycle

### Adopt or directly rewrite current state

Run `project-adopt` with every managed skill supplied as `PATH|NATIVE_OWNER`. The command assigns the fixed `native-integrated` marker, validates those explicit current inputs, renders the sole current block and manifest, writes them atomically, detects an intervening peer write, and immediately audits the result. If a non-current block or manifest exists, it is replaced directly; its rows are never reused, converted, renewed, or treated as authority.

### Audit

Run `project-audit` before broad maintenance closure and after repository transfer, SkillGuard installation, route changes, managed prompt changes, or direct current rewrites. Audit fails closed when:

- the manifest or `AGENTS.md` is missing;
- marker count is not exactly one begin and one end;
- the canonical repository URL is absent or changed;
- manifest or block hashes do not match;
- the rendered block is stale;
- a managed `SKILL.md` entrypoint is missing;
- the fixed integration marker, native owner, route status, or skill rows are invalid or non-canonical.

## Native-route rule

- `native-integrated` is the only current marker: the target owns its native route and exact declared checks, and SkillGuard only supervises their execution and receipts.
- Any other marker is blocked; SkillGuard never creates, completes, or substitutes a target-domain route.

The project block routes maintenance to SkillGuard. It does not make SkillGuard the domain owner and does not prove that any skill ran deeply.

## Claim boundary

A passing project audit proves only that portable project-maintenance instructions and manifest integrity are current. It does not prove runtime execution, target semantics, simulation validity, source completeness, tests, installation parity, release readiness, publication, or future AI behavior. Those require their own current evidence, including a declared-check execution receipt.
