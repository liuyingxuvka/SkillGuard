# SkillGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="SkillGuard concept hero image showing native skill lanes passing through contract, evidence, check, and closure gates" width="100%" />
</p>

<p align="center">
  <strong>A local runtime-contract system for keeping Codex skills on the right path.</strong>
</p>
<!-- README HERO END -->

Current release: `v0.2.0`

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

## What It Can Do

| Area | Current capability |
| --- | --- |
| Skill audit | Check `SKILL.md`, activation boundaries, maintained records, unsafe claims, and stale evidence. |
| Runtime contract | Keep legacy target contracts checkable and compile V2 contracts from a FlowGuard model plus a confirmed target binding. |
| Executable V2 run | Select typed routes, claim and lock a target-local run, execute exact checks, validate artifacts, issue immutable receipts, replay state, and derive scoped closure. |
| Deep coverage | Run `check-depth` to verify target rules, routes, workflow stages, native checks, source requirements, acceptance obligations, closure blockers, runtime-owned run records, and non-parallel route proof. |
| Native-aware upgrade | Preserve existing target skill routes through `native-integrated` or `hybrid-extension` contracts. |
| SkillGuard-owned runtime | Use `skillguard-runtime` only when the target skill has no native route/check owner. |
| Run governance | Select a route, start a run, advance phases, check evidence, and block unsupported closure. |
| Global router | Maintain a registry that helps choose a skill, without becoming a mandatory pre-execution gate for every skill. |
| Generation | Create draft skill and suite scaffolds with visible review boundaries. |
| Release hygiene | Keep README, version, fixture, test, and publication claims tied to current evidence. |
| Lifecycle safety | Compare canonical and installed source, audit public-export privacy, stage complete installs, smoke-test them, activate atomically, retain a backup, and roll back on failure. |

## Current Status

SkillGuard currently ships as source plus a local Python script dispatcher inside this repository. It is not yet a packaged console command or hosted service.

| Item | Status |
| --- | --- |
| Codex skill entrypoint | `.agents/skills/skillguard/SKILL.md` |
| Local command dispatcher | `.agents/skills/skillguard/scripts/skillguard.py` |
| Public version | `0.2.0` |
| Release mode | Source-only GitHub release |
| Binary artifact | Not provided |
| Packaged CLI install | Not claimed |
| Local installed sync | Whole-tree staged copy with parity, smoke, backup, and rollback |
| Current local test profiles | `fast`, `focused`, and `full` TestMesh |
| Python runtime | Python 3.11+ (the current FlowGuard runtime imports the standard-library `tomllib`) |
| CI definition | Windows/Linux and Python 3.11/3.12 workflow included; remote execution is a separate release check |
| FlowGuard evidence | Executable V2 child model and governance checks; broad project adoption remains a separate boundary |

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
audit-installed-skills,
check-json-schema, compile-contract, check-contract, check-depth,
check-readme-release,
select-route, start-run, advance-run, check-run, close-run,
init-target, init-suite, mark,
check-skill, check-suite,
check-skill-contract, check-suite-map, check-suite-contract,
check-fixture-manifest, check-work-contract, check-run-record,
check-check-manifest, fixture-test,
detect-stale-evidence, refresh-maintenance, review-checker-change,
check-maintenance-record, check-ai-judgment, check-report,
check-workflow-report, make-closure, self-check, write-report
```

Machine-readable command keyword index:

`commands`, `route-task`, `inventory`, `plan-skill`, `generate-skill`, `generate-suite`, `scan-global-skills`, `build-global-registry`, `check-global-registry`, `resolve-global-skill`, `render-global-prompt`, `install-global-prompt`, `check-global-prompt`, `refresh-global-router`, `audit-installed-skills`, `check-json-schema`, `compile-contract`, `check-contract`, `check-depth`, `check-readme-release`, `select-route`, `start-run`, `advance-run`, `check-run`, `close-run`, `init-target`, `init-suite`, `mark`, `check-skill`, `check-suite`, `check-skill-contract`, `check-suite-map`, `check-suite-contract`, `check-fixture-manifest`, `check-work-contract`, `check-run-record`, `check-check-manifest`, `fixture-test`, `detect-stale-evidence`, `refresh-maintenance`, `review-checker-change`, `check-maintenance-record`, `check-ai-judgment`, `check-report`, `check-workflow-report`, `make-closure`, `self-check`, and `write-report`.

This is a local dispatch surface. It is not packaged CLI installation proof.

## Runtime Contract Executor

SkillGuard's runtime contract is the center of the system.

```powershell
python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target .agents/skills/skillguard --write
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
```

A work contract records:

- integration mode: `native-integrated`, `hybrid-extension`, or `skillguard-runtime`;
- native route/check owner when the target already has one;
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

`check-depth` verifies that the contract is not just a shallow entrypoint wrapper. It checks that target-specific rules, routes, stages, native checks, and source requirements are represented in the coverage matrix, obligations are tied to checks or native bindings, closure blockers exist, cleanup is not pending, and only `skillguard-runtime` contracts retain an accepted SkillGuard run record bound to the current contract hash.

## Executable Contract V2

V2 separates two authorities. The FlowGuard model owns functions, states, routes, terminals, invariants, loops, and behavior obligations. The confirmed target binding owns concrete commands, tools, API witnesses, artifacts, timeouts, and quality rubrics. Generated contract files are deterministic outputs and are not hand-edited authorities.

```powershell
python .agents/skills/skillguard/scripts/skillguard_v2_compile.py <target-skill> --repository-root .
python .agents/skills/skillguard/scripts/skillguard_v2_supervise.py <target-skill> <run-packet.json> --target-root <target-project> --repository-root .
```

Every non-trivial supervised task claims a target-local run before work. The run freezes the request, contract, selected routes, write targets, and Guard-runtime fingerprint; records each transition in a hash-chained event log; stores check, artifact, and receipt evidence immutably; and closes only from current exact receipts. AI-provided “complete” is evidence submission, not authoritative pass.

Overlapping live writers remain blocked. If a recorded writer process has exited, or a legacy lock has a verified failed/closed terminal event, the next claimant records `stale_locks_recovered` before releasing only that run's locks. Resuming the same run reacquires its declared locks before continuing.

For a complete local install, stage and verify the whole skill tree before activation:

```powershell
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --prepare
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --activate
```

Activation rechecks parity and the installed layout, preserves the previous active copy as a backup, and restores it automatically if post-activation checks fail. This is a local source-tree installation workflow, not a packaged console-command distribution.

## Native-First Integration

SkillGuard should not erase a target skill's original path.

Use `native-integrated` when the target already has a clear route/check owner. Use `hybrid-extension` when the target has a partial native workflow and SkillGuard is filling missing gates around it. Use `skillguard-runtime` only when SkillGuard really owns the route because the target skill has no native route/check system.

This matters for skills such as FlowPilot and FlowGuard-family skills. Their original routers, models, simulators, and checks are the work surface. SkillGuard should strengthen those surfaces with contracts, native bindings, evidence gates, and closure blockers, not replace them with a parallel route or a separate SkillGuard run record.

## Typical Workflows

The workflows form a progression: audit the target first, add or refresh its contract gates, supervise a real run, maintain global selection separately, and revisit evidence whenever source or Guard behavior changes.

### Audit A Skill

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-skill --target .agents/skills/skillguard
```

Use this when you need a static skill-maintenance report: entrypoint structure, activation boundary, unsafe claims, maintained records, and current evidence boundaries.

### Add Or Refresh Runtime Gates

```powershell
python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target <target-skill> --write
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target <target-skill>
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target <target-skill>
```

Use this when a target skill needs a checkable work contract. For native or hybrid skills, review the native bindings before accepting the contract.

### Govern One Skill Run

```powershell
python .agents/skills/skillguard/scripts/skillguard.py select-route --target <target-skill> --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py start-run --target <target-skill> --route <route-id> --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py advance-run --run <run-record> --phase evidence --status checked --evidence direct_evidence --check check_evidence
python .agents/skills/skillguard/scripts/skillguard.py check-run --run <run-record> --complete
python .agents/skills/skillguard/scripts/skillguard.py close-run --run <run-record> --decision checked
```

Use this when the agent should not skip phases or close work from prose alone.

### Maintain Global Skill Routing

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <skill-root> --codex-home <codex-home> --output-dir <router-output>
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry <router-output>/global_registry.json --codex-home <codex-home>
python .agents/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry <router-output>/global_registry.json --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
```

The global router is a registry and handoff layer. It helps choose a skill and points the agent to that skill's own `SKILL.md`, work contract, check manifest, or native route bindings. It is not a mandatory gate before every skill invocation.

Use `audit-installed-skills` when you need to verify that installed user-created skills have current deep SkillGuard contracts instead of shallow entrypoint wrappers.

### Review Stale Evidence

```powershell
python .agents/skills/skillguard/scripts/skillguard.py detect-stale-evidence --input <evidence-json>
python .agents/skills/skillguard/scripts/skillguard.py refresh-maintenance --input <evidence-json> --dry-run
```

Use this when a report may no longer match the file hashes, route registry, command surface, fixture manifest, or generated artifact it claims to support.

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
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
python .agents/skills/skillguard/scripts/skillguard_test_mesh.py --profile focused --repository-root .
python .agents/skills/skillguard/scripts/skillguard_test_mesh.py --profile full --repository-root .
python .agents/skills/skillguard/scripts/skillguard_v2_self_host.py --repository-root .
python .agents/skills/skillguard/scripts/skillguard_provenance.py --repository-root . --development
python .agents/skills/skillguard/scripts/skillguard_privacy.py --repository-root .
python -m flowguard project-audit --root .
```

The focused/full TestMesh results, installed-source parity, privacy audit, and two-stage self-host are current local release evidence only when their source fingerprints still match. They do not prove future AI behavior, external service behavior, legal compliance, packaged CLI distribution, remote CI execution, or GitHub publication.

They also do not prove broad fixture coverage, suite automation, package publication, or code-contract validation beyond the exact files and commands checked.

## What SkillGuard Is Not

SkillGuard does not guarantee that Codex will always choose the right skill.

SkillGuard does not prove AI correctness. It can require evidence, expose skipped work, and block unsupported closure, but it does not replace maintainer judgment.

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

当前版本：`v0.2.0`

SkillGuard 是一个面向 Codex 技能的本地运行合同和维护框架。它帮助一个技能先选对路线，再把要完成的工作写进可检查的合同，记录运行证据，在关闭任务前运行检查，并明确报告哪些已经检查、哪些跳过、哪些过期、哪些被阻塞、哪些不在本次证据边界内。

最重要的原则是：优先接入原技能自己的路线。如果目标技能已经有自己的 router、controller、simulator、checker 或 release flow，SkillGuard 必须接到这套系统上，而不是在旁边再创建一条平行执行路线。

## 为什么需要它

AI 维护技能时，很容易只做浅层更新。一个技能可能有了好看的入口，却没有可运行检查；README 可能暗示已经可以发布，但没有当前证据；一个 suite 可能把失败的子技能藏起来；一个目标技能本来已经有原生路线，如果再加一套 SkillGuard 路线，反而会让执行路径更混乱。

SkillGuard 的目标就是阻止这种漂移。它把技能维护变成一份看得见的合同：

- 来自目标技能的源要求；
- 说明必须满足什么的验收义务；
- 技能专属检查和原生检查绑定；
- 只有 `skillguard-runtime` 合同才需要绑定当前合同哈希的 SkillGuard 运行记录；
- 针对浅层、过期、跳步或无证据工作的关闭阻塞；
- 明确说明本次到底证明了什么、没有证明什么的 claim boundary。

## 它现在能做什么

| 领域 | 当前能力 |
| --- | --- |
| 技能审计 | 检查 `SKILL.md`、激活边界、维护记录、不安全声明和过期证据。 |
| 运行合同 | 继续检查旧目标合同，并从 FlowGuard 模型和已确认目标绑定中编译 V2 合同。 |
| V2 可执行运行 | 选择有类型路线、认领并锁定目标本地运行、执行精确检查、验证产物、签发不可变收据、回放状态并推导有边界的闭环。 |
| 深度覆盖 | 用 `check-depth` 检查目标规则、路线、工作阶段、原生检查、源要求、验收义务、关闭阻塞、SkillGuard 自己负责执行时的运行记录和非平行路线证明。 |
| 原生路线增强 | 通过 `native-integrated` 或 `hybrid-extension` 保留目标技能原来的路线。 |
| SkillGuard 自有路线 | 只有当目标技能没有原生路线或检查系统时，才使用 `skillguard-runtime`。 |
| 运行治理 | 选择路线、开始运行、推进阶段、检查证据，并阻止无依据关闭。 |
| 全局路由 | 维护一个帮助选择技能的注册表，但它不是每次使用技能前都必须经过的总入口。 |
| 技能生成 | 生成带可见评审边界的技能和 suite 草稿。 |
| 发布卫生 | 让 README、版本、夹具、测试和发布声明都绑定到当前证据。 |
| 生命周期安全 | 比较原始仓库和安装副本、审计公开导出隐私、完整暂存安装、执行 smoke、原子切换、保留备份并在失败时回滚。 |

## 当前状态

SkillGuard 现在以源码加本地 Python 脚本分发，还不是一个打包好的 console command，也不是托管服务。

| 项目 | 状态 |
| --- | --- |
| Codex 技能入口 | `.agents/skills/skillguard/SKILL.md` |
| 本地命令分发器 | `.agents/skills/skillguard/scripts/skillguard.py` |
| 公开版本 | `0.2.0` |
| 发布方式 | 只发布源码 |
| 二进制文件 | 不提供 |
| 打包 CLI 安装 | 不声明 |
| 本地安装同步 | 完整目录暂存、逐文件一致性、smoke、备份和自动回滚 |
| 当前本地测试档位 | `fast`、`focused` 和 `full` TestMesh |
| Python 运行时 | Python 3.11+（当前 FlowGuard 运行时使用标准库 `tomllib`） |
| CI 定义 | 已包含 Windows/Linux、Python 3.11/3.12 工作流；远端执行仍是独立发布检查 |
| FlowGuard 证据 | 可执行 V2 子模型和治理检查；广义项目接入仍是独立边界 |

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
audit-installed-skills,
check-json-schema, compile-contract, check-contract, check-depth,
check-readme-release,
select-route, start-run, advance-run, check-run, close-run,
init-target, init-suite, mark,
check-skill, check-suite,
check-skill-contract, check-suite-map, check-suite-contract,
check-fixture-manifest, check-work-contract, check-run-record,
check-check-manifest, fixture-test,
detect-stale-evidence, refresh-maintenance, review-checker-change,
check-maintenance-record, check-ai-judgment, check-report,
check-workflow-report, make-closure, self-check, write-report
```

这只是本地脚本命令面，不代表已经有打包 CLI 安装能力。

## 运行合同执行器

SkillGuard 的核心是运行合同。

```powershell
python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target .agents/skills/skillguard --write
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
```

一份 work contract 会记录：

- 集成模式：`native-integrated`、`hybrid-extension` 或 `skillguard-runtime`；
- 目标技能已有原生路线时的 native route/check owner；
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

`check-depth` 用来判断合同是不是只包了一层浅入口。它会检查目标技能自己的规则、路线、阶段、原生检查和源要求是否进入覆盖矩阵，义务是否绑定检查或原生检查，是否存在关闭阻塞，是否还有未完成清理项，以及只有 `skillguard-runtime` 合同才保留已收口并绑定当前合同哈希的 SkillGuard 运行记录。

## V2 可执行合同

V2 明确分开两种权威。FlowGuard 模型负责函数、状态、路线、终点、不变量、循环和行为义务；已确认的目标绑定负责具体命令、工具、API 见证、产物、超时和质量量表。生成出来的合同文件是确定性输出，不是人工编辑的权威来源。

```powershell
python .agents/skills/skillguard/scripts/skillguard_v2_compile.py <target-skill> --repository-root .
python .agents/skills/skillguard/scripts/skillguard_v2_supervise.py <target-skill> <run-packet.json> --target-root <target-project> --repository-root .
```

每个非轻量受监督任务都要先认领一个目标本地运行。运行会冻结请求、合同、所选路线、写入目标和 Guard 运行时指纹；把每次转换写入哈希链事件日志；不可变地保存检查、产物和收据证据；并且只用当前、精确的收据闭环。AI 写“完成”只是提交证据，不等于权威通过。

仍然活着的重叠写入者会继续阻断。只有记录的进程已经退出，或者旧格式锁的事件链已经明确失败/关闭时，下一次认领才会先写入 `stale_locks_recovered`，然后只释放该运行自己的锁。同一运行恢复时，也必须先重新取得声明的锁再继续。

本地安装必须先完整暂存和验证整个技能目录，再激活：

```powershell
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --prepare
python .agents/skills/skillguard/scripts/skillguard_install.py --canonical-skill-root .agents/skills/skillguard --stage-root <staged-codex-home>/.codex/skills/skillguard --codex-home <codex-home> --activate
```

激活前会再次检查逐文件一致性和安装布局，旧活动副本会被保留为备份；激活后的检查失败时会自动恢复旧副本。这是本地源码目录安装流程，不代表已经提供打包 console command。

## 原生路线优先

SkillGuard 不应该抹掉目标技能原本的工作路线。

当目标技能已经有清楚的路线或检查系统时，用 `native-integrated`。当目标技能有一部分原生流程，但缺少证据、阶段或关闭门时，用 `hybrid-extension`。只有当目标技能真的没有原生路线或检查 owner 时，才用 `skillguard-runtime`。

这对 FlowPilot 和 FlowGuard 系列技能尤其重要。它们原本的 router、model、simulator 和 checks 才是工作表面。SkillGuard 应该把合同、原生绑定、证据门和关闭阻塞接到这些表面上，而不是替它们另起一条路线或留下单独的 SkillGuard 运行记录。

## 常见工作流

这些流程有明确顺序：先审计目标，再添加或刷新合同门，然后监督真实运行；全局选择单独维护；源码或 Guard 行为变化后重新检查证据。

### 审计一个技能

```powershell
python .agents/skills/skillguard/scripts/skillguard.py check-skill --target .agents/skills/skillguard
```

适合检查静态技能维护状态：入口结构、激活边界、不安全声明、维护记录和当前证据边界。

### 添加或刷新运行门

```powershell
python .agents/skills/skillguard/scripts/skillguard.py compile-contract --target <target-skill> --write
python .agents/skills/skillguard/scripts/skillguard.py check-contract --target <target-skill>
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target <target-skill>
```

适合给目标技能加一份可检查的工作合同。对于 native 或 hybrid 技能，接受合同前要检查 native bindings 是否真的接到了原路线。

### 管理一次技能运行

```powershell
python .agents/skills/skillguard/scripts/skillguard.py select-route --target <target-skill> --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py start-run --target <target-skill> --route <route-id> --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py advance-run --run <run-record> --phase evidence --status checked --evidence direct_evidence --check check_evidence
python .agents/skills/skillguard/scripts/skillguard.py check-run --run <run-record> --complete
python .agents/skills/skillguard/scripts/skillguard.py close-run --run <run-record> --decision checked
```

适合防止 AI 跳阶段，或者只靠文字说明就把工作关掉。

### 维护全局技能路由

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <skill-root> --codex-home <codex-home> --output-dir <router-output>
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry <router-output>/global_registry.json --codex-home <codex-home>
python .agents/skills/skillguard/scripts/skillguard.py resolve-global-skill --registry <router-output>/global_registry.json --task "<task>"
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
```

全局路由是注册表和交接层。它帮助选择技能，并把 agent 指向该技能自己的 `SKILL.md`、work contract、check manifest 或 native route bindings。它不是每次使用技能前都必须经过的总闸门。

当你需要确认已安装的自制技能是否都有当前的深度 SkillGuard 合同时，用 `audit-installed-skills`。它会找出浅入口包装、旧运行证据、缺少原生绑定或平行路线风险。

### 检查过期证据

```powershell
python .agents/skills/skillguard/scripts/skillguard.py detect-stale-evidence --input <evidence-json>
python .agents/skills/skillguard/scripts/skillguard.py refresh-maintenance --input <evidence-json> --dry-run
```

适合检查一份报告是否还匹配它声称覆盖的文件哈希、路线注册表、命令面、夹具清单或生成产物。

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
python .agents/skills/skillguard/scripts/skillguard.py check-depth --target .agents/skills/skillguard
python .agents/skills/skillguard/scripts/skillguard.py check-readme-release --repo .
python .agents/skills/skillguard/scripts/skillguard.py audit-installed-skills --root <skill-root>
python .agents/skills/skillguard/scripts/skillguard_test_mesh.py --profile focused --repository-root .
python .agents/skills/skillguard/scripts/skillguard_test_mesh.py --profile full --repository-root .
python .agents/skills/skillguard/scripts/skillguard_v2_self_host.py --repository-root .
python .agents/skills/skillguard/scripts/skillguard_provenance.py --repository-root . --development
python .agents/skills/skillguard/scripts/skillguard_privacy.py --repository-root .
python -m flowguard project-audit --root .
```

聚焦/完整 TestMesh、安装来源一致性、隐私审计和双层自托管只有在源码指纹仍匹配时，才是当前本地发布证据。它们不证明未来 AI 行为、外部服务行为、法律合规、打包 CLI 分发、远端 CI 执行或 GitHub 发布。

## SkillGuard 不是什么

SkillGuard 不能保证 Codex 永远选对技能。

SkillGuard 不证明 AI 正确。它能要求证据、暴露跳步、阻止无依据关闭，但不能替代维护者判断。

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
