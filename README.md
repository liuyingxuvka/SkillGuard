# SkillGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="SkillGuard author-side graduation system separating maintenance evidence from independent consumer skills" width="100%" />
</p>

<p align="center">
  <strong>Train and verify skills on the maintainer computer; ship skills that work independently.</strong>
</p>
<!-- README HERO END -->

Current release: `v0.4.2` (source-only; validation evidence and publication status remain separate claims)

English comes first; the second half is a full Chinese mirror.

SkillGuard is an author-side maintenance and graduation system for Codex skills. It helps a maintainer state what a skill promises, freeze the skill's own checks, verify that those exact target-declared checks actually ran with current evidence, and build a clean consumer distribution. A graduated skill does not need SkillGuard to run. SkillGuard never decides that a target's declaration should be deeper or invents a domain check for it.

## Why It Exists

A skill can sound complete while its own declared verification is missing: instructions may exist without runnable checks, a declared check may never run, or a claim may exceed the target-declared evidence. SkillGuard makes those exact reconciliation gaps visible during skill maintenance; deciding what the skill ought to promise remains the target author's job.

The boundary is equally important. SkillGuard is the school and graduation exam, not equipment that every graduate must carry. Therefore:

- author contracts, models, receipts, run state, Portfolio state, and router state stay in an explicit maintainer repository;
- every maintenance unit owns its obligations, semantic checks, evidence subjects, and receipts;
- different maintenance units do not share or import proof, even when two commands look identical;
- semantic overlap is a design defect to split, merge, or retire;
- ordinary business projects receive no SkillGuard files or prompt blocks;
- official OpenSpec is external and unmanaged; FlowGuard may read its proposal, design, specs, tasks, and status only as read-only context.

## A Declared Contract Is Not Execution Evidence

`CONTRACT_DEPTH_PASS` means the author contract declares the target's exact native owner, routes, obligations, and checks. `EXECUTION_DEPTH_PASS` means every frozen required check has a current terminal-success receipt for the exact maintenance unit, member, evidence subject, semantic check, owner, request, inputs, dependencies, toolchain, and environment.

Contract presence alone is never execution proof. Missing, failed, skipped, stale, timed-out, cancelled, cleanup-unconfirmed, and not-run checks remain visible blockers.

Receipt reuse is narrowly local: the same maintenance unit may single-flight one exact identical check request. A different unit must execute and own its own evidence. Consumer skills carry neither those receipts nor a receipt lookup rule.

## What It Can Do

| Area | Current capability |
| --- | --- |
| Author adoption | Mark only an explicit skill-authoring repository with a private maintainer prompt and `.skillguard/author-project.json`. |
| Contract compilation | Compile one current author contract and exact check manifest from the maintained source. |
| Declared verification | Compare target-declared promises with target-owned checks, current execution evidence, and bounded closure claims without inventing domain criteria. |
| Maintenance-unit isolation | Bind checks and receipts to unit, member, subject, semantic responsibility, owner, inputs, dependencies, toolchain, and environment. |
| TestMesh | Freeze same-unit validation plans, order dependencies, preserve immutable evidence, and keep skipped/not-run gaps visible. |
| Portfolio | Aggregate independent maintenance-unit statuses and audit semantic overlap without transferring proof. |
| Consumer distribution | Build a clean skill tree that excludes `.skillguard`, SkillGuard prompts, commands, imports, receipts, Portfolio data, and router state. |
| Safe installation | Stage, verify, activate, back up, and roll back a consumer distribution while preserving modified conflicts. |
| Author router | Maintain a private registry of explicitly maintained sources on the maintainer computer. |
| External providers | Keep official OpenSpec outside SkillGuard authority and prevent cross-tool receipt or session bridges. |
| Release hygiene | Keep README, model, version, fixture, and publication claims separate and evidence-bounded. |

## Current Status

SkillGuard currently ships as source plus a local Python dispatcher. It is not a hosted service or a packaged console command.

| Item | Status |
| --- | --- |
| Skill entrypoint | `.agents/skills/skillguard/SKILL.md` |
| Local dispatcher | `.agents/skills/skillguard/scripts/skillguard.py` |
| Source version | `0.4.2` |
| Author control root | `.skillguard/**` inside explicit maintainer sources only |
| Consumer projection | Target-owned files plus `consumer-release.json`; no SkillGuard dependency |
| Ordinary project behavior | Zero SkillGuard writes |
| OpenSpec relationship | Official external provider; read-only context only |
| Publication | Not proven by local source or tests |

## Command Surface

Run the dispatcher from the repository root:

```powershell
python .agents/skills/skillguard/scripts/skillguard.py commands
```

The current public commands are:

- discovery and author routing: `commands`, `route-task`, `inventory`, `scan-global-skills`, `build-global-registry`, `check-global-registry`, `refresh-global-router`;
- planning and generation: `plan-skill`, `generate-skill`, `generate-suite`;
- author repository and contract work: `maintainer-adopt`, `maintainer-audit`, `check-runtime-authority`, `check-json-schema`, `check-contract`, `check-depth`, `init-target`, `init-suite`, `mark`, `check-skill`, `check-suite`, `check-suite-map`, `check-suite-contract`;
- fixtures and evidence review: `check-fixture-manifest`, `fixture-test`, `detect-stale-evidence`, `review-checker-change`, `check-maintenance-record`, `check-ai-judgment`, `check-report`, `check-workflow-report`, `make-closure`, `evidence-audit`, `evidence-gc-plan`, `evidence-gc-apply`, `evidence-gc-purge`;
- independent Portfolio maintenance: `build-current-portfolio-registry`, `audit-portfolio`, `mark-portfolio-impact`, `verify-portfolio-impact-receipt`, `prepare-portfolio-run`, `execute-portfolio-run`, `capture-portfolio-production-revalidation`, `assemble-portfolio-run`, `graduate-portfolio`;
- installation evidence: `capture-installation-receipt`, `verify-installation-receipt`;
- repository gates: `check-readme-release`, `self-check`, `write-report`.

The standalone ordinary-skill resolver and consumer prompt installer are intentionally not public commands. The author-only `refresh-global-router` performs its registry and maintainer-prompt projection as one bounded operation.

## Runtime Contract Executor

The runtime executor is an author-maintenance facility. Before it writes state, the caller must supply an explicit author repository role, maintenance unit, author run-state root, and author evidence root. It never defaults these paths into the task's business project.

The executor freezes the exact declared-check inventory, launches only the unit's owned checks, records immutable terminal evidence, verifies dependencies and freshness, and derives a scoped closure. It does not invent domain tests or replace the target skill's own judgment.

Commands such as `init-target`, `init-suite`, and `mark` are maintainer-source utilities. They are not consumer-install or ordinary-project initialization commands.

## Current Executable Contract

The sole current author authority is:

- `.skillguard/contract-source.json`;
- `.skillguard/compiled-contract.json`;
- `.skillguard/check-manifest.json`.

These files belong to the maintained source and are excluded from the consumer distribution. Former schemas, compatibility readers, aliases, converters, reuse tickets, and parallel authority are not current success paths.

The compiler also declares `projection:consumer-distribution`. That projection rejects `.skillguard/**`, SkillGuard prompt markers, SkillGuard imports and commands, receipts, Portfolio data, and global-router state. If target-domain runtime is hidden below `.skillguard/runtime`, distribution blocks until the runtime moves to a target-owned namespace and parity is verified.

## Native-Owned Integration

The target skill remains the sole owner of domain behavior, fixtures, oracles, actions, and native checks. SkillGuard checks whether the target did what it promised; it does not decide what the promise should mean.

A target with one check and a target with many checks use the same supervision rule. Similar commands never authorize sharing by themselves. The target may explicitly bind several semantic checks to one producer execution; their subjects, domains, obligations, and projection identities remain separate. Different maintenance units never satisfy one another's obligations.

## Typical Workflows

### Audit A Skill

1. Select an explicitly maintained source.
2. Read its `SKILL.md` and native check declarations.
3. Run the author-side contract and declared-check execution checks.
4. Report failures, blockers, skipped checks, residual risk, and the exact claim boundary.

### Write Current Runtime Gates

Edit the current contract source and target-native checks in the maintainer repository, compile deterministic authority, then run only the affected validation owners. Do not place the generated control trio in the consumer skill.

### Govern One Current Skill Run

Freeze one maintenance unit, its members, semantic checks, dependencies, and evidence roots. Reuse only an exact same-unit success identity. Run one final full owner after the unit's source and toolchain are stable.

### Maintain Global Skill Routing

```powershell
python .agents/skills/skillguard/scripts/skillguard.py refresh-global-router --skill-root <explicit-author-skill-root> --codex-home <maintainer-codex-home> --output-dir <private-router-output>
python .agents/skills/skillguard/scripts/skillguard.py check-global-registry --registry <private-router-output>/global_registry.json
```

This registry is private author-maintenance state. It does not govern ordinary consumer execution and is not copied to another computer with a graduated skill.

### Validate And Revalidate A Skill Portfolio

Portfolio records one status per independent maintenance unit. A change stales only units whose exact component graph consumes the changed input. Each stale unit must regain currentness through its own evidence; no prior unit, parent receipt, or external provider can prove it.

### Adopt Or Audit A Skill Repository

```powershell
python .agents/skills/skillguard/scripts/skillguard.py maintainer-adopt --root <author-repository> --managed-skill "<skill-path>|<native-owner>" --skillguard-version 0.4.2
python .agents/skills/skillguard/scripts/skillguard.py maintainer-audit --root <author-repository>
```

These commands accept only explicit skill-authoring repositories. An ordinary business project is ineligible and remains unchanged.

### Review Stale Evidence

Use affected-only invalidation for maintained source, test, contract, configuration, toolchain, and policy inputs. Reports, receipts, logs, timestamps, progress, and status files are evidence outputs and do not retrigger their own producer.

Use `evidence-audit` and `evidence-gc-plan` for zero-write reachability inspection. Applying a plan only moves exact unreachable objects into quarantine; permanent purge is a separate command that requires the matching apply receipt, a fresh audit, replay gates, and the declared grace period.

## README And Release Gates

README completeness, model evidence, local tests, installation parity, Git state, tag creation, and package publication are separate claims. Passing one does not imply the others.

The README gate checks the bilingual mirror, hero provenance, current version, model evidence, public command surface, privacy, and conservative claim wording.

## Validation

Focused validation covers schemas, compiler parity, author context, unit identity, receipt isolation, TestMesh, Portfolio, router contraction, consumer distribution, installation rollback, ordinary-project zero-write behavior, and official-provider exclusion.

Final closure requires a frozen source and toolchain, one explicit full execution owner, confirmed descendant cleanup after any timeout, and current evidence for every required check. A diagram or prose explanation is not validation evidence.

## What SkillGuard Is Not

SkillGuard is not:

- a runtime dependency of graduated skills;
- a global governor for every skill on every computer;
- a replacement for target-native checks or domain judgment;
- an owner of official OpenSpec;
- a cross-skill evidence exchange;
- proof of fixture coverage, suite automation, package publication, release readiness, or code-contract validation merely because files exist.

## Public Boundary

Public source excludes credentials, private paths, transient process ids, machine-specific receipts, and author runtime state. Consumer distributions exclude all SkillGuard control state.

Local validation does not prove remote CI, external services, future AI behavior, factual correctness, a GitHub release, or a published package.

## Repository Layout

```text
.agents/skills/skillguard/   Skill entrypoint, author runtime, schemas, fixtures, templates
.flowguard/                  Executable behavior and process models
openspec/                    Current change artifacts and historical records
tests/                       Focused and integration tests
assets/readme-hero/          README visual and provenance evidence
```

Maintainer-control files and consumer-distribution files are intentionally different projections.

## Release History

See `CHANGELOG.md`. Historical entries describe the architecture that existed at that time; the current README and current OpenSpec change define the active boundary.

## License

See `LICENSE`.

# SkillGuard 中文说明

SkillGuard 是一个只在技能维护端使用的维护与毕业证据系统。它帮助维护者说明技能承诺什么、冻结技能自己的检查、确认这些由目标技能自己声明的检查是否真正运行并有当前证据，然后生成一个干净、独立的消费者版本。技能毕业以后，不需要带着 SkillGuard 才能工作。SkillGuard 不负责判断目标技能“应该更深”，也不会替它发明领域检查。

## 为什么需要它

技能很容易出现“声明与证据不一致”：提示词写得很好，但没有可运行检查；声明了检查，却从未真正运行；或者结论超过目标自己声明的证据边界。SkillGuard 在维护阶段把这些精确缺口明确暴露出来；技能究竟应该承诺什么，仍由目标技能及其作者决定。

边界同样重要。SkillGuard 是学校和毕业考试，不是毕业生必须随身携带的设备。因此：

- 合同、模型、收据、运行状态、Portfolio 和路由状态只留在明确的作者维护仓库；
- 每个维护单元拥有自己的义务、语义检查、证据主体和收据；
- 不同维护单元不能相互共享或导入证明，即使命令看起来完全一样；
- 如果两个技能的语义职责重叠，应当拆分、合并或退役，而不是共享测试；
- 普通业务项目不接收任何 SkillGuard 文件或提示块；
- 官方 OpenSpec 属于外部工具，SkillGuard 不维护它；FlowGuard 只能只读读取 proposal、design、specs、tasks 和 status 作为上下文。

## 声明了合同，不等于已有执行证据

`CONTRACT_DEPTH_PASS` 表示作者合同准确声明了目标技能自己的负责人、路线、义务和检查。`EXECUTION_DEPTH_PASS` 表示被冻结的每一项必需检查，都有属于同一维护单元、成员、证据主体、语义检查、执行负责人、请求、输入、依赖、工具链和环境的当前成功收据。

只有合同文件不代表真正运行过。缺失、失败、跳过、过期、超时、取消、清理未确认和未运行都必须继续显示为阻断。

只有同一个维护单元里、完全相同的一次检查请求，才可以合并为一次执行。另一个维护单元必须自己执行并拥有证据。毕业技能里既不带这些收据，也不带查收据的规则。

## 它现在能做什么

| 范围 | 当前能力 |
| --- | --- |
| 作者仓库接入 | 只为明确的技能作者仓库写入私有维护提示和 `.skillguard/author-project.json`。 |
| 合同编译 | 从维护源码生成唯一当前作者合同和精确检查清单。 |
| 声明核验 | 对照目标自己声明的技能承诺、原生检查、当前执行证据和有限结论，不发明领域标准。 |
| 维护单元隔离 | 用单元、成员、主体、语义职责、负责人、输入、依赖、工具链和环境绑定检查与收据。 |
| TestMesh | 冻结单元内的验证计划和依赖顺序，保留不可变证据，并显示跳过或未运行。 |
| Portfolio | 汇总相互独立的维护单元状态，检查语义重叠，但不传递证明。 |
| 消费者分发 | 生成不含 `.skillguard`、SkillGuard 提示、命令、导入、收据、Portfolio 和路由状态的技能目录。 |
| 安全安装 | 先暂存和检查，再原子切换；失败时回滚，并保留被用户修改过的冲突文件。 |
| 作者路由 | 只在维护电脑上登记明确被维护的技能源码。 |
| 外部工具 | 把官方 OpenSpec 保持为外部工具，禁止跨工具收据、会话或缓存桥。 |

## 当前状态

SkillGuard 目前以源码和本地 Python 调度器的形式存在，不是托管服务，也不是已经打包的控制台命令。

| 项目 | 状态 |
| --- | --- |
| 技能入口 | `.agents/skills/skillguard/SKILL.md` |
| 本地调度器 | `.agents/skills/skillguard/scripts/skillguard.py` |
| 源码版本 | `0.4.2` |
| 作者控制目录 | 只存在于明确维护源码里的 `.skillguard/**` |
| 消费者投影 | 目标自己的文件和 `consumer-release.json`，不依赖 SkillGuard |
| 普通项目 | SkillGuard 零写入 |
| OpenSpec | 官方外部工具，只读上下文 |
| 发布 | 不能由本地源码或测试自动证明 |

## 命令面

从仓库根目录运行：

```powershell
python .agents/skills/skillguard/scripts/skillguard.py commands
```

当前公开命令按用途分为：作者发现与路由、规划与生成、作者仓库与合同、测试与证据检查、相互独立的 Portfolio 维护、安装证据和仓库门禁。英文部分已经列出全部精确命令名。

面向普通技能的独立解析命令和消费者提示安装命令已经退出公开命令面。作者专用的 `refresh-global-router` 在一次受限操作中完成注册表和维护提示投影。

## 运行合同执行器

运行执行器只用于作者维护。写入任何状态之前，调用者必须明确提供作者仓库角色、维护单元、作者运行状态根和作者证据根。它绝不能把这些目录默认写进用户的业务项目。

执行器冻结精确检查清单，只启动本单元拥有的检查，记录不可变终态证据，验证依赖和新鲜度，再生成范围受限的结论。它不会发明领域测试，也不会替代技能自己的判断。

`init-target`、`init-suite` 和 `mark` 都是维护源码工具，不是消费者安装命令，也不是普通项目初始化命令。

## 当前可执行合同

唯一当前作者权威由以下三个文件组成：

- `.skillguard/contract-source.json`；
- `.skillguard/compiled-contract.json`；
- `.skillguard/check-manifest.json`。

这些文件属于维护源码，不进入消费者分发。旧 schema、兼容读取器、别名、转换器、复用票据和平行权威都不是当前成功路径。

编译器还声明 `projection:consumer-distribution`。它拒绝 `.skillguard/**`、SkillGuard 提示标记、SkillGuard 导入和命令、收据、Portfolio 数据和全局路由状态。如果目标领域运行时代码藏在 `.skillguard/runtime` 下，必须先迁移到目标自己的目录并验证一致性，才能生成消费者版本。

## 目标原生路线

目标技能始终独自拥有领域行为、夹具、判定标准、动作和原生检查。SkillGuard 检查目标是否兑现了承诺，但不替目标决定承诺的领域含义。

只有一项检查的技能和有很多检查的技能使用同一套监管原则。相似命令本身不能授权共享；只有目标合同明确把多项语义检查绑定到同一个执行生产者时，才允许只运行一次，而且每项检查的证据主体、证据域、义务和投影身份仍分别保留。不同维护单元永远不能相互完成义务。

## 常见工作流

### 审计一个技能

先选择明确被维护的源码，阅读它的 `SKILL.md` 和原生检查声明，再运行作者侧合同与声明检查执行核验。最后明确报告失败、阻断、跳过、剩余风险和结论边界。

### 写入当前运行门

只在维护仓库里修改当前合同源码和目标原生检查，编译确定性的作者权威，然后只运行受影响的验证负责人。不要把生成的控制三件套放进消费者技能。

### 管理一次当前技能运行

冻结一个维护单元、它的成员、语义检查、依赖和证据根。只允许完全相同的单元内成功身份复用。源码和工具链稳定以后，只运行一次最终完整负责人。

### 维护全局技能路由

使用英文部分给出的 `refresh-global-router` 和 `check-global-registry` 示例。这个注册表是维护电脑上的私有作者状态，不管理普通消费者运行，也不会随毕业技能复制到另一台电脑。

### 验证并重新验证技能组合

Portfolio 为每个独立维护单元记录一个状态。某个输入变化，只会让明确消费该输入的单元过期。每个过期单元必须依靠自己的证据恢复当前状态；以前的单元、父收据或外部工具都不能替它证明。

### 接管或审计技能仓库

使用 `maintainer-adopt` 和 `maintainer-audit`，而且只针对明确的技能作者仓库。普通业务项目不符合资格，失败时必须保持完全不变。

### 检查过期证据

只有被维护的源码、测试、合同、配置、工具链和策略输入会按精确依赖关系触发失效。报告、收据、日志、时间戳、进度和状态文件都是证据输出，不能反过来触发自己的生产者。

`evidence-audit` 和 `evidence-gc-plan` 只读检查可达性。执行计划只会把精确、不可达对象移动到隔离区；永久清除是另一条明确命令，必须同时满足匹配的隔离收据、最新审计、回放门和声明的宽限期。

## README 和发布门禁

README 完整度、模型证据、本地测试、安装一致性、Git 状态、标签和 package publication 都是不同的声明。通过一项不能自动推出其他项。

README 门禁检查中英文镜像、主视觉来源、当前版本、模型证据、公开命令面、隐私和保守的结论措辞。

## 验证

聚焦验证覆盖 schema、编译器一致性、作者上下文、单元身份、收据隔离、TestMesh、Portfolio、路由收缩、消费者分发、安装回滚、普通项目零写入和官方外部工具排除。

最终完成要求冻结源码和工具链，指定唯一完整执行负责人；任何超时后都要确认所有后代进程已经结束；每一项必需检查都要有当前证据。图和文字说明都不能替代验证证据。

## SkillGuard 不是什么

SkillGuard 不是：

- 毕业技能的运行依赖；
- 每台电脑上所有技能的总监管器；
- 目标原生检查或领域判断的替代品；
- 官方 OpenSpec 的维护者；
- 跨技能证据交换系统；
- 仅凭文件存在就能证明 fixture coverage、suite automation、package publication、release readiness 或 code-contract validation 的工具。

## 公开边界

公开源码不包含凭据、私有路径、临时进程号、机器专属收据和作者运行状态。消费者分发不包含任何 SkillGuard 控制状态。

本地验证不能证明远程 CI、外部服务、未来 AI 行为、事实正确性、GitHub Release 或已发布软件包。

## 仓库结构

```text
.agents/skills/skillguard/   技能入口、作者运行时、schema、夹具和模板
.flowguard/                  可执行行为与流程模型
openspec/                    当前变更和历史记录
tests/                       聚焦测试与集成测试
assets/readme-hero/          README 视觉和来源证据
```

维护者控制文件与消费者分发文件是两个有意分开的投影。

## 发布历史

参见 `CHANGELOG.md`。历史条目描述当时的架构；当前 README 和当前 OpenSpec 变更定义现在有效的边界。

## 许可证

参见 `LICENSE`。
