# SkillGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="SkillGuard concept hero image showing native skill lanes passing through contract, evidence, check, and closure gates" width="100%" />
</p>

<p align="center">
  <strong>A local runtime-contract system for keeping Codex skills on the right path.</strong>
</p>
<!-- README HERO END -->

Current release: `v0.3.3` (source-only; validation evidence and publication status remain separate claims)

English comes first; the second half is a full Chinese mirror.

SkillGuard is a local runtime-contract and maintenance framework for Codex skills. It helps a skill choose the right route, lock the work into a checkable contract, record run evidence, run validation before closure, and report what is checked, skipped, stale, blocked, or outside the claim boundary.

The core rule is native-first integration: if a target skill already has its own router, controller, simulator, checker, or release flow, SkillGuard must attach to that system. It must not create a second parallel execution route beside the original workflow.

## Why It Exists

AI-maintained skills can look complete while still being shallow. A skill may gain a nice entrypoint but no runnable checks. A README may claim release readiness without current evidence. A suite may hide a failing child. A target skill may already have a native route, and adding a separate SkillGuard route can make the workflow less clear instead of safer.

SkillGuard is built to prevent that drift. It turns skill maintenance into a visible contract:

- source requirements from the target skill;
- acceptance obligations that explain what must be true;
- skill-specific checks and native check bindings;
- run records tied to the current contract hash;
- closure blockers for shallow, stale, skipped, or unsupported work;
- explicit claim boundaries for what was and was not proven.

## Contract Depth Is Not Execution Depth

SkillGuard separates two questions:

- `CONTRACT_DEPTH_PASS`: the target skill's exact native owner, routes, and required check ids are structurally declared and bound to the current contract.
- `EXECUTION_DEPTH_PASS`: every check in that frozen inventory has exactly one current immutable terminal-success receipt for the same request and runtime, no declared check is unresolved, and closure consumed the exact depth receipt.

There is one fixed supervision workflow and no optional mode. SkillGuard does not classify targets, branch on a skill family, infer domain meaning from check names, invent a model purpose, or mandate a positive/negative pair. A target with one declared check is supervised by the same inventory-and-receipt rules as a target with several checks. The target owns its domain actions, depth standard, fixtures, oracles, and claim boundary; SkillGuard owns inventory equality, single execution ownership, freshness, receipt completeness, provider enrollment, and closure consumption.

Loading a skill, checking a schema, seeing a zero exit code without the immutable owner receipt, or omitting one declared check does not establish execution depth. Missing, duplicate, failed, skipped, stale, timed-out, cancelled, cleanup-unconfirmed, and not-run results remain explicit blockers. Capability validation cannot authorize scheduled production; production also binds the current installation receipt and installed runtime identity.

Conditional workflows retain target-owned branch contracts. An intermediate authorization remains non-terminal, while the fixed `enforced` completion consumes its own current native terminal and declared-check receipts plus verifier-owned applicability evidence where the target contract permits it.

Repository adoption is separate again. `project-adopt` writes or directly rewrites the sole current marker-bounded SkillGuard maintenance block in `AGENTS.md` plus a hash-bound `.skillguard/project.json`; `project-audit` checks that exact current shape. Neither command converts or reuses an older shape. The block names the canonical repository—<https://github.com/liuyingxuvka/SkillGuard>—so another AI or computer can discover the maintenance rule. It does not make SkillGuard the target-domain owner or prove that the target ran deeply.

Validation execution has one explicit ownership policy. Before multi-skill validation, the existing verification contract or TestMesh freezes every exact check, covered obligation/evidence domain, dependency order, persistent receipt root, and one primary execution owner. Consumers resolve the exact current immutable success receipt and never carry or rerun the owner's command; maintained inputs stale only affected receipts, while reports, receipts, progress logs, and runtime outputs cannot retrigger their producer.

## What It Can Do

| Area | Current capability |
| --- | --- |
| Skill audit | Check `SKILL.md`, activation boundaries, maintained records, unsafe claims, and stale evidence. |
| Runtime authority | Resolve each target as exactly `current` or `blocked`; current means one complete source/compiled/manifest trio and no former surface. There is no compatibility, conversion, retirement, renewal, or fallback route. |
| Current executable run | Select typed routes, claim and lock a target-local run, execute exact checks, validate artifacts, issue immutable receipts, replay state, and derive scoped closure. |
| Contract integrity | Run `check-depth` to verify that the compiled contract preserves the target's exact declared checks, owners, dependencies, evidence domains, and closure bindings without adding target-domain semantics. |
| Execution depth | Freeze the target's exact declared-check inventory and require one current immutable terminal-success receipt per check under the same owner, request, inputs, and runtime. |
| Target-neutral supervision | Apply the same inventory, ownership, freshness, and receipt rules to every target without classifying its family or interpreting its domain semantics. |
| Conditional branch closure | Keep target-owned branch obligations explicit, let a verifier mark only contract-authorized obligations `not_applicable`, and require exact native terminal and declared-check receipts for the fixed `enforced` closure. |
| Root and request binding | Keep maintained `repository_root` inputs separate from task-data `target_root`, and bind every receipt to the current request and input identities without persisting machine-local absolute paths. |
| Provider readiness | Compare the active provider's runtime contract, capabilities, enrollment, and native readiness receipts so a new prompt cannot silently overclaim an old runtime. |
| Portable project adoption | Generate and audit one bounded repository prompt block and project manifest with the public SkillGuard URL, managed paths, fixed integration marker, native-route evidence, hashes, and claim boundary. |
| Native-owned current contract | Preserve the target-owned route and checks under the sole current `native-integrated` marker; SkillGuard never supplies a target-domain route. |
| Run governance | Let the one current supervisor select the declared route, execute ordered phases, check exact evidence, and block unsupported closure. |
| Global router | Maintain a registry that helps choose a skill, without becoming a mandatory pre-execution gate for every skill. |
| Generation | Create draft skill and suite scaffolds with visible review boundaries. |
| Release hygiene | Keep README, version, fixture, test, and publication claims tied to current evidence. |
| Lifecycle safety | Compare canonical and installed source, audit public-export privacy, stage complete installs, smoke-test them, activate atomically, retain a backup, and roll back on failure. |
| Receipt handoff | Publish hash-bound TestMesh parent closure, installation-parity, and portfolio-impact receipts so later layers consume exact current evidence instead of rerunning, relabeling, or silently preserving stale green status. |

## Current Status

SkillGuard currently ships as source plus a local Python script dispatcher inside this repository. It is not yet a packaged console command or hosted service.

| Item | Status |
| --- | --- |
| Codex skill entrypoint | `.agents/skills/skillguard/SKILL.md` |
| Local command dispatcher | `.agents/skills/skillguard/scripts/skillguard.py` |
| Public source version | `0.3.3` |
| Release mode | Source development; tag and GitHub Release require separate verification |
| Binary artifact | Not provided |
| Packaged CLI install | Not claimed |
| Local installed sync | Whole-tree staged copy with parity, smoke, backup, and rollback |
| Current local test profiles | `fast`, `focused`, and `full` TestMesh |
| Python runtime | Python 3.11+ (the current FlowGuard runtime imports the standard-library `tomllib`) |
| CI definition | Windows/Linux and Python 3.11/3.12 workflow included; remote execution is a separate release check |
| FlowGuard evidence | Executable current child model and governance checks; broad project adoption remains a separate boundary |

## Command Surface

Run commands from the repository root.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py commands
```

Current local command families include:

```text
commands, route-task, inventory,
plan-skill, generate-skill, generate-suite,
scan-global-skills, build-global-registry, check-global-registry,
resolve-global-skill, render-global-prompt, install-global-prompt,
check-global-prompt, refresh-global-router,
audit-installed-skills, project-adopt, project-audit,
audit-portfolio, mark-portfolio-impact,
verify-portfolio-impact-receipt, capture-installation-receipt, verify-installation-receipt,
issue-portfolio-reuse-ticket, prepare-portfolio-run, execute-portfolio-run,
capture-portfolio-production-revalidation, assemble-portfolio-run, graduate-portfolio,
check-json-schema, check-runtime-authority, check-contract, check-depth,
check-readme-release,
init-target, init-suite, mark,
check-skill, check-suite,
check-suite-map, check-suite-contract,
check-fixture-manifest, fixture-test,
detect-stale-evidence, review-checker-change,
check-maintenance-record, check-ai-judgment, check-report,
check-workflow-report, make-closure, self-check, write-report
```

Machine-readable command keyword index:

`commands`, `route-task`, `inventory`, `plan-skill`, `generate-skill`, `generate-suite`, `scan-global-skills`, `build-global-registry`, `check-global-registry`, `resolve-global-skill`, `render-global-prompt`, `install-global-prompt`, `check-global-prompt`, `refresh-global-router`, `audit-installed-skills`, `project-adopt`, `project-audit`, `build-current-portfolio-registry`, `audit-portfolio`, `mark-portfolio-impact`, `verify-portfolio-impact-receipt`, `capture-installation-receipt`, `verify-installation-receipt`, `issue-portfolio-reuse-ticket`, `prepare-portfolio-run`, `execute-portfolio-run`, `capture-portfolio-production-revalidation`, `assemble-portfolio-run`, `graduate-portfolio`, `check-json-schema`, `check-runtime-authority`, `check-contract`, `check-depth`, `check-readme-release`, `init-target`, `init-suite`, `mark`, `check-skill`, `check-suite`, `check-suite-map`, `check-suite-contract`, `check-fixture-manifest`, `fixture-test`, `detect-stale-evidence`, `review-checker-change`, `check-maintenance-record`, `check-ai-judgment`, `check-report`, `check-workflow-report`, `make-closure`, `self-check`, and `write-report`.

This is a local dispatch surface. It is not packaged CLI installation proof.

## Runtime Contract Executor

SkillGuard's runtime contract is the center of the system.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-runtime-authority --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard_compile.py .agents/skills/skillguard --repository-root .agents/skills/skillguard --check
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
```

The selected authority contract records:

- fixed integration marker: `native-integrated`;
- target-owned native route/check owner;
- route choices and phase order;
- target rule inventory, route inventory, workflow stage inventory, and native check inventory;
- required evidence and required check ids;
- source requirements inferred from the target skill;
- acceptance obligations;
- coverage matrix, test gap plan, and runtime lock policy;
- skill-specific checks;
- closure blockers;
- non-parallel route proof;
- current contract hash;
- freshness and closure boundaries.

`check-contract` verifies the contract shape, references, hash, scripts, and semantic links.

For an external nested skill, both `check-contract` and `check-skill` require one canonical repository/member binding: pass `--repository-root <repository>` and a repository-relative or contained absolute `--target <member>`. Repository-relative contract and reference paths resolve only from that root. A member outside the root blocks, the removed `check-contract --target-root` spelling is not an alias, and a standalone skill may still use `--target .` from its own directory.

`check-depth` verifies that the contract is not just a shallow entrypoint wrapper. It checks exact equality between target-declared checks and the compiled inventory, validates owners and dependencies, and blocks missing, duplicate, stale, non-terminal, skipped, failed, or not-run receipts. It does not judge what the target checks mean.

`check-runtime-authority` is the first consumer gate. It returns only `current` or `blocked`. A current target has the complete source/compiled/manifest trio and no former files, fields, receipts, schemas, commands, conversion scripts, or history directories. Any other shape is blocked. Ordinary maintenance writes the current trio directly and deletes the named former files; product code never reads or converts the old payload.

## Current Executable Contract

The current executable contract separates two authorities. The FlowGuard model owns functions, states, routes, terminals, invariants, loops, and behavior obligations. The confirmed target binding owns concrete commands, tools, API witnesses, artifacts, timeouts, and quality rubrics. Generated contract files are deterministic outputs and are not hand-edited authorities.

```powershell
python .agents/skills/skillguard/scripts/skillguard_compile.py <target-skill> --repository-root .
python .agents/skills/skillguard/scripts/skillguard_supervise.py <target-skill> <run-packet.json> --target-root <target-project> --repository-root .
```

Every non-trivial supervised task claims a target-local run before work. The run freezes the request, contract, selected routes, write targets, and SkillGuard runtime fingerprint; records transitions in a hash-chained event log; stores check, artifact, and receipt evidence immutably; and closes only from current exact receipts.

When a `depth_profile` is enforced, the supervisor freezes the target's exact `native_check_ids` inventory. Each check has exactly one execution owner and dependency set. The supervisor executes or reuses one immutable current terminal-success owner receipt per check, then reconciles check id, owner id, request fingerprint, freshness, disposition, receipt id, and receipt hash. Any missing, duplicate, failed, skipped, stale, timed-out, cancelled, cleanup-unconfirmed, or request-mismatched result blocks.

SkillGuard does not inspect a target name to decide what checks it should have and does not interpret a target's fixtures or oracle. Those remain target-owned. It verifies active provider/runtime enrollment and capabilities, issues one immutable target execution-depth receipt only when the unresolved set is empty, and requires closure to consume it. For scheduled production it also verifies the exact current installation receipt and installed runtime identity.

Source-only capability validation and scheduled production are different contracts. A capability result cannot be renamed into production authority. Conditional targets must project their own branch contract; terminal receipts bind exact `closure_profile` and `closure_disposition`, so an intermediate authorization cannot be promoted into the fixed `enforced` terminal completion.

Overlapping live writers remain blocked. A current lock with an explicit writer process may be recovered only after that process has exited; a lock missing its current owner identity remains blocked and is never inferred from older event shapes. The next claimant records `stale_locks_recovered` before releasing only the proven-dead run's locks. Resuming the same run reacquires its declared locks before continuing.

For a complete local install, stage and verify the whole skill tree before activation:

```powershell
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --prepare
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --activate
python .agents/skills/skillguard/scripts/skillguard.py capture-installation-receipt --repository-root . --receipt-root <receipt-root>
python .agents/skills/skillguard/scripts/skillguard.py verify-installation-receipt --repository-root . --receipt-root <receipt-root> --require-current-installed-parity
```

Activation rechecks parity and the installed layout, preserves the previous active copy as a backup, and restores it automatically if post-activation checks fail. The installation receipt then binds the committed transaction and activation receipt to current canonical/installed source identities and runtime fingerprints. This is a local source-tree installation workflow, not a packaged console-command distribution or release proof.

## Native-Owned Integration

SkillGuard should not erase a target skill's original path.

`native-integrated` is the only current integration marker. The target skill must own its route and exact checks. If that native contract is incomplete, repair it in the target skill; SkillGuard may supervise the repaired declarations but never fills in or substitutes a target-domain route.

This applies equally to every skill. Its original router, model, simulator, checker, or other native work surface remains authoritative. SkillGuard adds inventory, ownership, receipt, freshness, and closure supervision around those surfaces; it does not replace them with a parallel route.

## Typical Workflows

The workflows form a progression: audit the target first, write its sole current contract gates, supervise a real run, maintain global selection separately, and revisit only affected owner evidence when declared functional inputs change.

### Audit A Skill

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-skill --target .agents/skills/skillguard
```

Use this when you need a static skill-maintenance report: entrypoint structure, activation boundary, unsafe claims, maintained records, and current evidence boundaries.

### Write Current Runtime Gates

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-runtime-authority --target <target-skill>
python .agents/skills/skillguard/scripts/skillguard_compile.py <repository>/<member> --repository-root <repository>
python .agents/skills/skillguard/scripts/skillguard.py check-contract --repository-root <repository> --target <member>
python .agents/skills/skillguard/scripts/skillguard.py check-skill --repository-root <repository> --target <member>
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target <target-skill>
```

Use this when a target skill needs a checkable work contract. For native or hybrid skills, review the native bindings before accepting the contract.

### Govern One Current Skill Run

```powershell
python .agents/skills/skillguard/scripts/skillguard_supervise.py <target-skill> <run-packet.json> --target-root <target-project> --repository-root .
```

Use this single current supervisor when the agent must not skip phases or close work from prose alone. Removed route/run commands are rejected and have no compatibility dispatcher.

### Maintain Global Skill Routing

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <skill-root> --codex-home <codex-home> --output-dir <router-output>
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry <router-output>/global_registry.json --codex-home <codex-home>
python .agents/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry <router-output>/global_registry.json --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
```

The global router is a registry and handoff layer. It helps choose a skill and points the agent to that skill's own `SKILL.md`, work contract, check manifest, or native route bindings. It is not a mandatory gate before every skill invocation.

Use `audit-installed-skills` when you need to verify that installed user-created skills have current deep SkillGuard contracts instead of shallow entrypoint wrappers.

### Validate And Revalidate A Skill Portfolio

The portfolio commands keep broad SkillGuard changes honest across previously accepted targets. When a reviewed scope replaces stale registry authority, `build-current-portfolio-registry` constructs revision one directly from that exact scope and carries no prior green evidence; it is not a migration or fallback. File output uses the sole portfolio-registry writer lock, so a live impact, reuse, graduation, or replacement writer blocks the command without being overwritten. Use `audit-portfolio` first and pass `--target-repository-root SKILL_ID=PATH` for every active target whose currentness is claimed; stored green state alone is never enough. The registry must already use the one current shape; any other schema is blocked and ordinary maintenance rewrites it directly. A superseded target must be retired, name one distinct active replacement, declare installation absent and router authority blocked, and be confirmed absent from the installed root and current router registry before that zero-authority claim is made. `mark-portfolio-impact --write --receipt-root ...` invalidates old green evidence after a Guard change and publishes an immutable handoff, while `issue-portfolio-reuse-ticket` permits reuse only for an unchanged, explicitly bound target. A representative batch then moves through `prepare-portfolio-run`, `execute-portfolio-run`, one `capture-portfolio-production-revalidation` per target member, and `assemble-portfolio-run` before `graduate-portfolio` can update portfolio status. Source-only capability self-checks cannot replace these installed scheduled-production bindings.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py build-current-portfolio-registry --help
python .agents/skills/skillguard/scripts/skillguard.py audit-portfolio --help
python .agents/skills/skillguard/scripts/skillguard.py mark-portfolio-impact --help
python .agents/skills/skillguard/scripts/skillguard.py verify-portfolio-impact-receipt --help
python .agents/skills/skillguard/scripts/skillguard.py prepare-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py execute-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py capture-portfolio-production-revalidation --help
python .agents/skills/skillguard/scripts/skillguard.py assemble-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py graduate-portfolio --help
```

Portfolio status is private, hash-bound maintenance evidence. The impact receipt proves that the exact named target set was moved to `revalidation_required`; it does not itself revalidate those targets, permit evidence reuse, or make one representative run proof for every skill or every future task.

### Adopt Or Audit A Skill Repository

```powershell
python .agents/skills/skillguard/scripts/skillguard.py project-adopt --root <repository> --managed-skill "<skill-path>|<native-owner>" --skillguard-version 0.3.3
python .agents/skills/skillguard/scripts/skillguard.py project-audit --root <repository>
```

Adoption preserves all text outside the managed markers. Audit blocks missing, duplicate, tampered, stale, or incomplete project guidance. Every managed target keeps its own native route and declared checks under the fixed `native-integrated` marker.

### Review Stale Evidence

```powershell
python .agents/skills/skillguard/scripts/skillguard.py detect-stale-evidence --input <evidence-json>
```

Use this read-only check when a report may no longer match the exact functional inputs it claims to support. A stale result names the exact owner that must run again; it never rewrites evidence.

## README And Release Gates

README work is part of the SkillGuard contract surface. A release-facing README must not claim what current files do not prove.

For this repository, README maintenance requires:

- English-first structure with a full Chinese mirror when bilingual presentation is used;
- one text-to-image concept hero block near the top;
- a project-specific hero prompt and design note under `assets/readme-hero/`;
- current-version README model evidence under `assets/readme-hero/readme_model_evidence.md`;
- README Showcase Writer model artifacts: repository fact ledger, capability claim matrix, narrative structure plan, and gap ledger;
- current version consistency across `VERSION`, `pyproject.toml`, README, and changelog;
- public/private boundary checks;
- command examples that match the real local script surface;
- release wording that stays source-only unless a packaged artifact is actually built and verified.

The dedicated gate is:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .
```

## Validation

Recommended local checks:

```powershell
python -m py_compile .agents/skills/skillguard/scripts/checker_engine.py .agents/skills/skillguard/scripts/skillguard.py
python tests/test_skillguard_local.py
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/deep_contract/fixture-manifest.json
python .agents/skills/skillguard/scripts/skillguard.py self-check --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py project-audit --root .
python -m pytest tests/test_execution_depth.py tests/test_skillguard_generic_supervision.py tests/test_skillguard_project_adoption.py -q
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
python -m pytest -q
python .agents/skills/skillguard/scripts/skillguard_test_mesh.py --profile focused --mode plan_only --repository-root . --run-root <run-root> --skill-root .agents/skills/skillguard --target-root .agents/skills/skillguard --owner-evidence-root <owner-evidence-root>
python .agents/skills/skillguard/scripts/skillguard_self_host.py --repository-root .
python .agents/skills/skillguard/scripts/skillguard_provenance.py --repository-root . --development
python .agents/skills/skillguard/scripts/skillguard_privacy.py --repository-root .
python -m flowguard project-audit --root .
```

Run the full test suite after source freeze. For receipt-governed TestMesh work, first create the immutable plan with `plan_only`, then pass that exact saved plan to `owner_execution_only`, and finally to `aggregation_only`; replay consumes the returned aggregation reference through `--replay-aggregation-ref`. Full aggregation additionally requires the exact current installation receipt and global-prompt binding. A copied or bare child result is not reusable proof. The target skill's current `SKILL.md` is authoritative for this three-stage lifecycle.

The focused/full TestMesh results, installed-source parity, privacy audit, and two-stage self-host are current local release evidence only when their source fingerprints still match. They do not prove future AI behavior, external service behavior, legal compliance, packaged CLI distribution, remote CI execution, or GitHub publication.

They also do not prove broad fixture coverage, suite automation, package publication, or code-contract validation beyond the exact files and commands checked.

## What SkillGuard Is Not

SkillGuard does not guarantee that Codex will always choose the right skill.

SkillGuard does not prove AI correctness. It can require evidence, expose skipped work, and block unsupported closure, but it does not replace maintainer judgment.

SkillGuard does not perform the target skill's physics simulation, logic modeling, source search, storyline reasoning, world rollout, document rendering, or other domain work. It verifies target-owned receipts and closure boundaries around that work.

SkillGuard is not a hosted service, a packaged CLI, a GitHub automation platform, or a binary release artifact.

SkillGuard should not become a universal pre-execution gate for every skill call. It should govern skill selection and skill maintenance when routing help or contract evidence is needed, then hand off to the selected skill's own workflow.

## Public Boundary

Public files in this repository should not contain:

- credentials, tokens, private keys, or environment secrets;
- private task text, private transcripts, or internal coordination notes;
- local absolute paths or user-specific machine details;
- runtime logs, caches, exports, backups, or local generated state;
- screenshots or examples with private data;
- release, package, test, or external-service claims that current files do not prove.

When a capability is absent, the README should say it is absent rather than implying it is already shipped.

## Repository Layout

```text
SkillGuard/
  README.md
  CHANGELOG.md
  VERSION
  pyproject.toml
  LICENSE
  AGENTS.md
  assets/readme-hero/
    readme_model_evidence.md
  references/
  examples/
  tests/
  .agents/
    skills/
      skillguard/
        SKILL.md
        assets/
          schemas/
          templates/
        scripts/
        fixtures/
        .skillguard/
      skillguard-global-router/
        SKILL.md
        .skillguard/
  .flowguard/
```

## Release History

See [CHANGELOG.md](CHANGELOG.md).

## License

SkillGuard is licensed under the MIT License. See [LICENSE](LICENSE).

---

# SkillGuard 中文说明

当前发布版本：`v0.3.3`（仅源码；验证证据和发布状态仍是彼此独立的声明）

SkillGuard 是一个面向 Codex 技能的本地运行合同和维护框架。它帮助一个技能先选对路线，再把要完成的工作写进可检查的合同，记录运行证据，在关闭任务前运行检查，并明确报告哪些已经检查、哪些跳过、哪些过期、哪些被阻塞、哪些不在本次证据边界内。

最重要的原则是：优先接入原技能自己的路线。如果目标技能已经有自己的 router、controller、simulator、checker 或 release flow，SkillGuard 必须接到这套系统上，而不是在旁边再创建一条平行执行路线。

## 为什么需要它

AI 维护技能时，很容易只做浅层更新。一个技能可能有了好看的入口，却没有可运行检查；README 可能暗示已经可以发布，但没有当前证据；一个 suite 可能把失败的子技能藏起来；一个目标技能本来已经有原生路线，如果再加一套 SkillGuard 路线，反而会让执行路径更混乱。

SkillGuard 的目标就是阻止这种漂移。它把技能维护变成一份看得见的合同：

- 来自目标技能的源要求；
- 说明必须满足什么的验收义务；
- 技能专属检查和原生检查绑定；
- 每项目标自声明检查都必须绑定精确 owner、当前请求和不可变终局收据；
- 针对浅层、过期、跳步或无证据工作的关闭阻塞；
- 明确说明本次到底证明了什么、没有证明什么的 claim boundary。

## 合同深度不等于执行深度

SkillGuard 把两个问题分开：

- `CONTRACT_DEPTH_PASS`：目标技能已经把自己的原生 owner、路线和必需检查 id 精确写进当前合同。
- `EXECUTION_DEPTH_PASS`：冻结清单中的每一项检查，都在同一个请求和运行时下拥有且仅拥有一份当前、不可变、终局成功的 owner 收据；没有未解决检查；关闭流程消费了这份精确深度收据。

这里只有一套固定监督流程，没有可选模式。SkillGuard 不给目标分类，不根据技能家族分支，不从检查名猜领域含义，不替目标发明模型目的，也不强制正反成对。只声明一项检查的目标，与声明多项检查的目标，接受完全相同的“冻结清单—执行 owner—核对收据—关闭消费”规则。目标技能负责领域动作、深度标准、夹具、判定器和声明边界；SkillGuard 只负责清单相等、唯一执行 owner、新鲜度、收据完整性、provider 注册状态和关闭消费。

仅仅加载技能、检查 schema、看到退出码为零却没有不可变 owner 收据，或者漏跑一项已声明检查，都不算执行深度。缺失、重复、失败、跳过、过期、超时、取消、清理未确认和未运行都会保留为明确阻塞。能力验证不能冒充计划生产；生产收据还必须绑定当前安装收据和已安装运行时身份。

条件工作流继续使用目标自己声明的分支合同。中间授权不是终局；固定的 `enforced` 闭环必须消费当前原生终点收据、完整声明检查收据，以及目标合同允许范围内由 verifier 签发的 applicability 证据。

仓库接管是独立的一层。`project-adopt` 只按唯一当前格式写入或直接重写 `AGENTS.md` 中的受控提示块与带哈希的 `.skillguard/project.json`；`project-audit` 只检查这一当前格式。提示块不会把目标领域权交给 SkillGuard，也不能证明目标已经深度运行。

## 它现在能做什么

| 领域 | 当前能力 |
| --- | --- |
| 技能审计 | 检查 `SKILL.md`、激活边界、维护记录、不安全声明和过期证据。 |
| 运行时权威 | 每个目标只会解析成 `current` 或 `blocked`；当前状态必须有完整的源码/编译/清单三件套且没有任何旧表面，不提供兼容、转换、退休、续期或备用路线。 |
| 当前可执行运行 | 选择有类型路线、认领并锁定目标本地运行、执行精确检查、验证产物、签发不可变收据、回放状态并推导有边界的闭环。 |
| 合同完整性 | 用 `check-depth` 检查编译合同是否精确保留目标自己声明的检查、owner、依赖、证据域和关闭绑定，而且没有加入 SkillGuard 自己发明的领域语义。 |
| 执行深度 | 冻结目标技能精确声明的检查清单，并要求每项检查在同一 owner、请求、输入和运行时下都有一份当前不可变的终局成功收据。 |
| 目标中立监督 | 对所有目标使用相同的清单、owner、新鲜度和收据规则，不识别技能家族，也不解释领域语义。 |
| 条件分支闭环 | 继续要求目标自己的分支义务显式化，只允许 verifier 将合同明确允许的义务标成 `not_applicable`，并让固定的 `enforced` 闭环消费精确终点与声明检查收据。 |
| 双目录与请求绑定 | 区分维护源码 `repository_root` 与任务数据 `target_root`，把收据绑定到当前请求和输入身份，同时不写入机器本地绝对路径。 |
| 可移植项目接管 | 生成并审计一个有边界的仓库提示块和项目清单，包含公开 SkillGuard 地址、受管技能路径、固定集成标记、原生路线证据、哈希和声明边界。 |
| 目标原生合同 | 只使用唯一当前标记 `native-integrated`，保留目标自己的路线和检查；SkillGuard 永远不提供目标领域路线。 |
| 运行治理 | 选择路线、开始运行、推进阶段、检查证据，并阻止无依据关闭。 |
| 全局路由 | 维护一个帮助选择技能的注册表，但它不是每次使用技能前都必须经过的总入口。 |
| 技能生成 | 生成带可见评审边界的技能和 suite 草稿。 |
| 发布卫生 | 让 README、版本、夹具、测试和发布声明都绑定到当前证据。 |
| 生命周期安全 | 比较原始仓库和安装副本、审计公开导出隐私、完整暂存安装、执行 smoke、原子切换、保留备份并在失败时回滚。 |
| 收据交接 | 生成带哈希的 TestMesh 父闭环、安装一致性和组合影响收据，让后续层消费精确当前证据，而不是重复运行、改标签或静默保留过期绿色状态。 |

## 当前状态

SkillGuard 现在以源码加本地 Python 脚本分发，还不是一个打包好的 console command，也不是托管服务。

| 项目 | 状态 |
| --- | --- |
| Codex 技能入口 | `.agents/skills/skillguard/SKILL.md` |
| 本地命令分发器 | `.agents/skills/skillguard/scripts/skillguard.py` |
| 公开源码版本 | `0.3.3` |
| 发布方式 | 源码开发版；标签和 GitHub Release 需要独立验证 |
| 二进制文件 | 不提供 |
| 打包 CLI 安装 | 不声明 |
| 本地安装同步 | 完整目录暂存、逐文件一致性、smoke、备份和自动回滚 |
| 当前本地测试档位 | `fast`、`focused` 和 `full` TestMesh |
| Python 运行时 | Python 3.11+（当前 FlowGuard 运行时使用标准库 `tomllib`） |
| CI 定义 | 已包含 Windows/Linux、Python 3.11/3.12 工作流；远端执行仍是独立发布检查 |
| FlowGuard 证据 | 可执行的当前子模型和治理检查；广义项目接入仍是独立边界 |

## 命令面

从仓库根目录运行命令。

```powershell
python .agents/skills/skillguard/scripts/skillguard.py commands
```

当前本地命令族包括：

```text
commands, route-task, inventory,
plan-skill, generate-skill, generate-suite,
scan-global-skills, build-global-registry, check-global-registry,
resolve-global-skill, render-global-prompt, install-global-prompt,
check-global-prompt, refresh-global-router,
audit-installed-skills, project-adopt, project-audit,
audit-portfolio, mark-portfolio-impact,
verify-portfolio-impact-receipt, capture-installation-receipt, verify-installation-receipt,
issue-portfolio-reuse-ticket, prepare-portfolio-run, execute-portfolio-run,
capture-portfolio-production-revalidation, assemble-portfolio-run, graduate-portfolio,
check-json-schema, check-runtime-authority, check-contract, check-depth,
check-readme-release,
init-target, init-suite, mark,
check-skill, check-suite,
check-suite-map, check-suite-contract,
check-fixture-manifest, fixture-test,
detect-stale-evidence, review-checker-change,
check-maintenance-record, check-ai-judgment, check-report,
check-workflow-report, make-closure, self-check, write-report
```

这只是本地脚本命令面，不代表已经有打包 CLI 安装能力。

## 运行合同执行器

SkillGuard 的核心是运行合同。

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-runtime-authority --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard_compile.py .agents/skills/skillguard --repository-root .agents/skills/skillguard --check
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
```

被选中的权威合同会记录：

- 固定集成标记：`native-integrated`；
- 目标技能自己拥有的 native route/check owner；
- 路线选择和阶段顺序；
- 目标规则清单、路线清单、工作阶段清单和原生检查清单；
- 每个阶段需要的证据和检查 id；
- 从目标技能推断出的源要求；
- 验收义务；
- 覆盖矩阵、测试缺口计划和运行锁定规则；
- 技能专属检查；
- 关闭阻塞；
- 非平行路线证明；
- 当前合同哈希；
- 新鲜度和关闭边界。

`check-contract` 检查合同结构、引用、哈希、脚本和语义链接。

检查外部仓库里的嵌套技能时，`check-contract` 与 `check-skill` 都必须显式绑定一组 canonical repository/member：传入 `--repository-root <repository>`，再用仓库相对路径或位于该根目录内的绝对路径传入 `--target <member>`。合同和引用里的仓库相对路径只从该 root 解析；member 越界就阻断，已删除的 `check-contract --target-root` 不作为别名保留。独立技能仍可在自身目录使用 `--target .`。

`check-depth` 用来判断合同是不是只包了一层浅入口。它会精确比较目标声明检查与编译清单，核对 owner 和依赖，并阻止缺失、重复、过期、非终局、跳过、失败或未运行的收据；它不判断这些目标检查在领域上是什么意思。

`check-runtime-authority` 是所有消费者的第一道门，而且只返回 `current` 或 `blocked`。当前目标必须具备完整的源码/编译/清单三件套，并且没有旧文件、旧字段、旧收据、旧 schema、旧命令、转换脚本或历史目录。其他形状全部阻断。普通维护直接写成当前三件套并删除点名的旧文件；产品代码不会读取或转换旧内容。

## 当前可执行合同

当前合同明确分开两种权威。FlowGuard 模型负责函数、状态、路线、终点、不变量、循环和行为义务；已确认的目标绑定负责具体命令、工具、API 见证、产物、超时和质量量表。生成出来的合同文件是确定性输出，不是人工编辑的权威来源。

```powershell
python .agents/skills/skillguard/scripts/skillguard_compile.py <target-skill> --repository-root .
python .agents/skills/skillguard/scripts/skillguard_supervise.py <target-skill> <run-packet.json> --target-root <target-project> --repository-root .
```

每个非轻量受监督任务都要先认领一个目标本地运行。运行会冻结请求、合同、所选路线、写入目标和 SkillGuard 运行时指纹；把转换写入哈希链事件日志；不可变地保存检查、产物和收据；并且只用当前精确收据闭环。

当 `depth_profile` 处于强制状态时，监督器冻结目标技能自己的 `native_check_ids` 清单。每项检查只有一个执行 owner 和一组显式依赖。监督器执行该 owner，或者复用一份身份完全一致的当前不可变终局成功收据，然后逐项核对 check id、owner id、请求指纹、新鲜度、终局状态、收据 id 和收据哈希。任何缺失、重复、失败、跳过、过期、超时、取消、清理未确认或请求不一致都会阻断。

SkillGuard 不会查看目标名字来决定它应该有哪些检查，也不解释目标的夹具或判定器。这些全部由目标技能负责。SkillGuard 只核对活动 provider/runtime 的注册和能力；未解决清单为空时才签发不可变目标执行深度收据，并要求关闭流程消费它。计划生产还必须核对精确当前安装收据和已安装运行时身份。

源码能力验证与计划生产是不同合同，前者不能改名冒充后者。条件目标必须投影自己的分支合同；终点收据绑定精确 `closure_profile` 与 `closure_disposition`，所以中间授权不能被提升为固定 `enforced` 的终局完成。

仍然活着的重叠写入者会继续阻断。只有记录的进程已经退出，或者旧格式锁的事件链已经明确失败/关闭时，下一次认领才会先写入 `stale_locks_recovered`，然后只释放该运行自己的锁。同一运行恢复时，也必须先重新取得声明的锁再继续。

本地安装必须先完整暂存和验证整个技能目录，再激活：

```powershell
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --prepare
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --activate
python .agents/skills/skillguard/scripts/skillguard.py capture-installation-receipt --repository-root . --receipt-root <receipt-root>
python .agents/skills/skillguard/scripts/skillguard.py verify-installation-receipt --repository-root . --receipt-root <receipt-root> --require-current-installed-parity
```

激活前会再次检查逐文件一致性和安装布局，旧活动副本会被保留为备份；激活后的检查失败时会自动恢复旧副本。安装收据随后把已提交事务与激活收据绑定到当前 canonical/installed 源身份和运行时指纹。这是本地源码目录安装流程，不代表已经提供打包 console command，也不是发布证明。

## 目标原生路线

SkillGuard 不应该抹掉目标技能原本的工作路线。

`native-integrated` 是唯一当前集成标记。目标技能必须自己拥有路线和精确检查；如果它的原生合同不完整，就在目标技能中修好。SkillGuard 可以监督修好后的声明，但不会补写或替代目标领域路线。

这对所有技能一视同仁。它们原本的 router、model、simulator、checker 或其他原生工作表面继续拥有权威；SkillGuard 只在外围增加清单、owner、收据、新鲜度和闭环监督，不另起一条平行路线。

## 常见工作流

这些流程有明确顺序：先审计目标，再直接写入唯一当前合同门，然后监督真实运行；全局选择单独维护；只有声明过的功能输入发生变化，才重查受影响 owner 的证据。

### 审计一个技能

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-skill --target .agents/skills/skillguard
```

适合检查静态技能维护状态：入口结构、激活边界、不安全声明、维护记录和当前证据边界。

### 写入当前运行门

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-runtime-authority --target <target-skill>
python .agents/skills/skillguard/scripts/skillguard_compile.py <repository>/<member> --repository-root <repository>
python .agents/skills/skillguard/scripts/skillguard.py check-contract --repository-root <repository> --target <member>
python .agents/skills/skillguard/scripts/skillguard.py check-skill --repository-root <repository> --target <member>
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target <target-skill>
```

适合给目标技能加一份可检查的工作合同。对于 native 或 hybrid 技能，接受合同前要检查 native bindings 是否真的接到了原路线。

### 管理一次当前技能运行

```powershell
python .agents/skills/skillguard/scripts/skillguard_supervise.py <target-skill> <run-packet.json> --target-root <target-project> --repository-root .
```

只使用这一当前 supervisor，防止 AI 跳阶段或只靠文字说明关单。已删除的 route/run 命令必须被拒绝，不存在兼容分发器。

### 维护全局技能路由

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <skill-root> --codex-home <codex-home> --output-dir <router-output>
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry <router-output>/global_registry.json --codex-home <codex-home>
python .agents/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry <router-output>/global_registry.json --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
```

全局路由是注册表和交接层。它帮助选择技能，并把 agent 指向该技能自己的 `SKILL.md`、work contract、check manifest 或 native route bindings。它不是每次使用技能前都必须经过的总闸门。

当你需要确认已安装的自制技能是否都有当前的深度 SkillGuard 合同时，用 `audit-installed-skills`。它会找出浅入口包装、旧运行证据、缺少原生绑定或平行路线风险。

### 验证并重新验证技能组合

组合命令用于防止 SkillGuard 自身变化后，旧的绿色结论被直接沿用。先运行 `audit-portfolio`，并为每个要声称仍然有效的活动目标传入 `--target-repository-root SKILL_ID=PATH`；登记表里存着旧绿色并不算当前证据。注册表必须已经是唯一当前形状；其他 schema 一律阻断，并由普通维护直接重写。被替代的目标必须退役、指向一个不同且仍活跃的替代目标，并声明安装不存在、路由权威被阻断；在声称零权威前，还要只读确认旧技能不在安装目录和当前路由注册表中。`mark-portfolio-impact --write --receipt-root ...` 在 Guard 行为变化后作废旧证据并生成不可变交接；`issue-portfolio-reuse-ticket` 只允许未变化且明确绑定的目标复用证据。代表性批次必须依次经过 `prepare-portfolio-run`、`execute-portfolio-run`、为每个成员执行一次 `capture-portfolio-production-revalidation`，再进入 `assemble-portfolio-run`，最后才能由 `graduate-portfolio` 更新组合状态。仅有源码能力自检不能替代安装后的定时生产收据。

```powershell
python .agents/skills/skillguard/scripts/skillguard.py audit-portfolio --help
python .agents/skills/skillguard/scripts/skillguard.py mark-portfolio-impact --help
python .agents/skills/skillguard/scripts/skillguard.py verify-portfolio-impact-receipt --help
python .agents/skills/skillguard/scripts/skillguard.py prepare-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py execute-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py capture-portfolio-production-revalidation --help
python .agents/skills/skillguard/scripts/skillguard.py assemble-portfolio-run --help
python .agents/skills/skillguard/scripts/skillguard.py graduate-portfolio --help
```

组合状态只是私有、带哈希的维护证据。影响收据只证明精确命名的目标集合已经变成 `revalidation_required`；它不会自行重新验证目标、允许证据复用，也不能让一个代表性运行替所有技能或所有未来任务作证。

### 接管或审计技能仓库

```powershell
python .agents/skills/skillguard/scripts/skillguard.py project-adopt --root <repository> --managed-skill "<skill-path>|<native-owner>" --skillguard-version 0.3.3
python .agents/skills/skillguard/scripts/skillguard.py project-audit --root <repository>
```

接管只替换受控标记之间的内容，其他项目提示会保留。审计会阻止缺失、重复、被篡改、过期或不完整的项目提示。每个受管目标都在固定 `native-integrated` 标记下保留自己的原生路线和声明检查。

### 检查过期证据

```powershell
python .agents/skills/skillguard/scripts/skillguard.py detect-stale-evidence --input <evidence-json>
```

这是一项只读检查，用来确认报告是否仍匹配它声称覆盖的精确功能输入。若已失效，只指出应由哪个 owner 重新执行，绝不改写旧证据。

## README 和发布门禁

README 也是 SkillGuard 合同的一部分。面向发布的 README 不能声明当前文件无法证明的能力。

这个仓库的 README 维护要求包括：

- 使用双语展示时，英文在前，中文是完整镜像；
- 顶部只保留一个文生图概念 hero；
- `assets/readme-hero/` 下要有项目专属 hero prompt 和设计说明；
- `assets/readme-hero/readme_model_evidence.md` 下要有绑定当前版本的 README 模型证据；
- README Showcase Writer 要求的模型产物必须完整：仓库事实台账、能力声明矩阵、叙事结构计划和缺口台账；
- `VERSION`、`pyproject.toml`、README 和 changelog 的版本一致；
- 检查公开/私有边界；
- 命令示例必须匹配真实本地脚本命令面；
- 除非真的构建并验证了打包产物，否则发布说明保持源码发布。

专门门禁是：

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .
```

## 验证

推荐本地检查：

```powershell
python -m py_compile .agents/skills/skillguard/scripts/checker_engine.py .agents/skills/skillguard/scripts/skillguard.py
python tests/test_skillguard_local.py
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/runtime_contract/fixture-manifest.json
python .agents/skills/skillguard/scripts/skillguard.py fixture-test --manifest .agents/skills/skillguard/fixtures/deep_contract/fixture-manifest.json
python .agents/skills/skillguard/scripts/skillguard.py self-check --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py project-audit --root .
python -m pytest tests/test_execution_depth.py tests/test_skillguard_generic_supervision.py tests/test_skillguard_project_adoption.py -q
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
python -m pytest -q
python .agents/skills/skillguard/scripts/skillguard_test_mesh.py --profile focused --mode plan_only --repository-root . --run-root <run-root> --skill-root .agents/skills/skillguard --target-root .agents/skills/skillguard --owner-evidence-root <owner-evidence-root>
python .agents/skills/skillguard/scripts/skillguard_self_host.py --repository-root .
python .agents/skills/skillguard/scripts/skillguard_provenance.py --repository-root . --development
python .agents/skills/skillguard/scripts/skillguard_privacy.py --repository-root .
python -m flowguard project-audit --root .
```

源码冻结后运行完整测试套件。需要收据治理的 TestMesh 工作先用 `plan_only` 生成不可变计划，再把同一份计划依次交给 `owner_execution_only` 和 `aggregation_only`；回放只用 `--replay-aggregation-ref` 消费聚合引用。完整聚合还必须绑定当前安装收据和全局提示身份。复制出来的或裸露的 child result 没有复用权威；三阶段生命周期以目标技能当前 `SKILL.md` 为准。

聚焦/完整 TestMesh、安装来源一致性、隐私审计和双层自托管只有在源码指纹仍匹配时，才是当前本地发布证据。它们不证明未来 AI 行为、外部服务行为、法律合规、打包 CLI 分发、远端 CI 执行或 GitHub 发布。

## SkillGuard 不是什么

SkillGuard 不能保证 Codex 永远选对技能。

SkillGuard 不证明 AI 正确。它能要求证据、暴露跳步、阻止无依据关闭，但不能替代维护者判断。

SkillGuard 不执行目标技能自己的物理仿真、逻辑建模、来源搜索、故事线推演、世界状态 rollout、文档渲染或其他领域工作。它只围绕这些目标自有工作验证收据与关闭边界。

SkillGuard 不是托管服务，不是打包 CLI，不是 GitHub 自动化平台，也不是二进制发布产物。

SkillGuard 不应该变成每次调用技能前都必须经过的统一总闸门。它应该在需要路线帮助或合同证据时治理技能选择和技能维护，然后交给被选中技能自己的工作流。

## 公开边界

这个仓库的公开文件不应该包含：

- 凭证、token、私钥或环境 secret；
- 私有任务文本、私有对话或内部协作记录；
- 本地绝对路径或用户机器信息；
- 运行日志、缓存、导出、备份或本地生成状态；
- 带有私有数据的截图或示例；
- 当前文件不能证明的发布、打包、测试或外部服务声明。

如果某个能力还不存在，README 应该直接说不存在，而不是暗示它已经发布。

## 仓库结构

```text
SkillGuard/
  README.md
  CHANGELOG.md
  VERSION
  pyproject.toml
  LICENSE
  AGENTS.md
  assets/readme-hero/
    readme_model_evidence.md
  references/
  examples/
  tests/
  .agents/
    skills/
      skillguard/
        SKILL.md
        assets/
          schemas/
          templates/
        scripts/
        fixtures/
        .skillguard/
      skillguard-global-router/
        SKILL.md
        .skillguard/
  .flowguard/
```

## 发布历史

见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

SkillGuard 使用 MIT License。见 [LICENSE](LICENSE)。
