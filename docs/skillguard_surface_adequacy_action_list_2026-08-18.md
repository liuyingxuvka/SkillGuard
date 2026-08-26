# SkillGuard 反向功能闭包审计与执行清单

日期：2026-08-18<br>
对象：SkillGuard 作者侧维护源，不是普通 consumer 安装包

## 先记住三条边界

1. SkillGuard 只监督“作者侧已经明确注册的维护源”。普通使用某个已经毕业的 skill 时，不需要安装 SkillGuard，不需要 `.skillguard`，也不需要携带 SkillGuard receipt、router 或 Portfolio 状态。
2. 目标 skill 自己决定领域意图、成功标准、错误 oracle、fixture 和 native checks。SkillGuard 只检查身份、完整性、执行深度、收据、projection 和安装当前性，不替目标发明领域含义。
3. “声明的检查全部通过”不等于“真实功能全部被声明”。反向 surface inventory 是独立分母；没有它，不能毕业，也不能作完整 DNA/functional claim。

## 本轮最新复核（覆盖本文件中较早的 candidate/unverified 记录）

当前对象是 v0.7.2 tag 内容的脏 detached worktree；本轮没有把它宣称为 Git/tag/release 已发布。
SkillGuard 自身的 51 个 public command 有 51 个可独立验收的 target-owned surface observations，global-router 自身另有
5 行 inventory，当前 `check-depth` 与 `self-check` 为 current/pass。SkillGuard 的合同、执行、安装和
aggregation 证据只覆盖这两个明确注册的作者维护单元，不会自动替其他 skill 发明意图或借用收据；
其中 native execution、完整 self-host/release 和跨 consumer fleet 证据仍须单独收口。

## 终端状态定义

- `pass/current`：当前身份下有可重放的结构或收据证据。
- `blocked`：发现未映射、重复 owner、身份不一致、缺收据、缺恢复路径或任何硬门失败。
- `stale`：源、模型、toolchain、安装或 evidence 的 fingerprint 已变化。
- `not_run`：该 owner 尚未运行；不能写成 pass。
- `not_applicable_proven`：有独立 proof 和理由证明该表面确实不适用；不能只写一句“没有 UI”。

任何阶段遇到 `blocked/stale/not_run`，停止向下游传播绿色结论，先修当前阶段。

## 阶段 0：冻结唯一作者身份

动作：

1. 只在 clean、明确的作者源 worktree 工作；不要在脏旧 checkout 上直接修复。
2. 记录 `source_sha`、SkillGuard 版本、Python/toolchain、`contract-source.json`、`compiled-contract.json`、`check-manifest.json` 的 hash。
3. 记录 maintenance unit、member ids、semantic checks、evidence subjects、execution owners、依赖和 private evidence root。
4. 检查有没有超时、取消或残留 descendant process；process tree 未确认归零时，不复用旧 receipt，也不启动新 owner。

通过条件：所有身份唯一，工作树 dirt 已归属，且后续 source/toolchain/impact plan 不再改变。<br>
失败条件：切换 checkout、改变 contract、修改 source 或改变运行环境；所有后续 execution/installation evidence 作废，回到本阶段。

## 阶段 1：建立独立真实 surface 分母

由 target-owned native discovery 产生 `.skillguard/surface-inventory.json`。不得从已有 check rows、测试文件名、模型节点或 README 反推分母。

至少发现并分类：

- public CLI command、subcommand、option、dispatch entry；
- exported API、class、function、console script；
- prompt route、触发词、模板 action；
- config/schema/file format；
- 文件、目录、进程、网络等外部 effect；
- raise、异常、非零退出、权限失败、输入拒绝；
- retry、resume、rollback、recover、cleanup、restore、repair、reconnect、cancel；
- UI-like button、click、menu、select、submit、navigate、launch、interactive confirmation；
- install、upgrade、rollback、uninstall 和 consumer entrypoint。

每个 review row/group 至少包含：`surface_id`、source path/ref/fingerprint、kind、intent id、owner id、route/function/step、required check ids、adequacy check ids、evidence subject ids 和 disposition。这里的 row 不是每行源代码：`surface` 是可独立触发的 command/API/UI/config/install/effect/fault/recovery，`component` group 是多个内部 helper/派生 facet 的共同审查边界，source line/span 只作定位锚点。一个 group 只有在所有成员都绑定相同 current intent、owner、obligation、check 和 receipt 时才可关闭。

通过条件：两次在同一 source SHA 上生成的 inventory bytes/hash 完全相同；`discovered_surface_count = governed + internal_proven + retired_proven + not_applicable_proven`；`orphan_surface_count=0`。<br>
失败条件：扫描有预算截断、手工删除未解释 row、重复 id、unknown disposition 或 source fingerprint 过期。

## 阶段 2：做双向追踪，而不是单向挂钩

对每个 surface 或 component group 建立以下链：

`surface/group -> intent -> model route/function/step -> obligation -> semantic checks -> execution owner -> producer receipt/projection -> consumer/install disposition`

同时建立反向链：

`model obligation -> implementation surface(s)`

每个 model obligation 必须属于以下一种：

- `governed`：指向一个或多个当前真实实现 surface；
- `model_only_proven`：明确没有当前实现，且有独立 proof/ref 和理由；
- `retired_proven`：旧义务已退役，且有当前 proof/ref 和理由；
- `not_applicable_proven`：在当前 scope 不适用，且有独立 proof/ref 和理由。

通过条件：surface 与 model obligation 双向守恒，唯一 primary owner，没有 unknown/orphan/duplicate。<br>
失败条件：只做 surface→test、不做 obligation→surface；用函数存在或测试名称冒充 owner；用 parent summary 代替 leaf receipt。

## 阶段 3：强制 adequacy，而不是只强制 non-empty

目标的 depth profile 必须同时声明：

1. `model_deepening_check_id`；
2. `surface_inventory.path`；
3. 至少一个 `adequacy_check_id`；
4. surface inventory 自己的 model-deepening binding 和 inventory hash。

至少安排五类 target-owned adequacy check：

- surface completeness：新增真实入口会被发现；
- intent/contract mapping：每个入口有意图和合同路径；
- negative/failure：错误、权限、边界和拒绝分支有 oracle；
- recovery/cleanup/idempotency：失败后恢复、清理、重复执行有证据；
- model/depth adequacy：模型义务、测试深度和声明范围一致。

通过条件：删除任意一个 adequacy receipt、删掉一个真实 surface row 或删掉一个 obligation 反向链接，`check-depth` 和 `graduate-portfolio` 都 fail closed。<br>
失败条件：只检查 JSON 形状、字符串 `kind`、`sha256:` 前缀、布尔 `passed` 或 evidence 自己提供的 expected input。

## 阶段 4：先用 SkillGuard 自己做 dogfood

当前 SkillGuard 自己的审计 denominator 是 51 个 public commands。用当前 dispatch table 和 route registry 对账：

- 51/51 命令必须有明确 disposition；
- 当前发现的 26 个 route gap 必须逐个建立 route 或 typed internal/subroute/retired proof；
- 当前发现的 44 个空 `required_check_ids` 必须逐个补 native check，或提供独立 typed disposition；
- 每个 mutating command 必须有 `intent_id`、`function_id`、`route_id`、semantic checks、owner、lifecycle phase 和 write authority。

本轮 self-dogfood 已完成上述结构性修复：当前 route registry 为 v5，51/51 命令都有独立 current route，51/51 命令都有 contract-source 中的 target-native required checks，surface validator 返回 0 findings。原始 26/44 状态仍保留为 deterministic negative fixture，删除 route/check 仍会 fail closed。

本轮 current 结构证据：`skillguard_compile.py --check` 返回 `ok=true`；
源码作者树的 `self-check` 返回 pass；安装后的 `self-check` 也返回 pass；安装后的
`check-depth` 返回 `decision=pass`、`depth_classification=declared-contract-current`、
`surface inventory rows=51`、`findings=[]`。当前 contract hash 为
`08F1A2FD133BB62782AC05885C820534C147AC667B026E2FB3BA9FCD3DB53C44`，manifest hash 为
`E48B5B959AF65025B8038B4D17C629B44F0DF5E58CB30A8BDD6E8F926BD7535A`；作者侧完整反向发现
为 `1,848 observations / 1,398 review groups / 1,336 surface / 512 component`，discovery
fingerprint 为 `sha256:ea691f6c6e8629eb6d5d775d5cf061db2602ce06ad590854157ac005c66c548e`。
本轮窄验证为 `129 passed, 20 subtests passed`。这些命令和测试证明当前合同、反向分母结构
和局部负例，不证明目标领域语义正确或完整 native execution。

安装阶段已在同一 current stage 上通过源/暂存 parity、安装 smoke、runtime import、无字节码残留
和 descendant cleanup；直接激活事务 `install-5ace2a94cb2b4514a0b573e309f87f8d` 的 receipt
状态为 `activation_verified`，安装后 self-check/check-depth 均通过。这个安装证据只关闭
SkillGuard 当前安装投影，不等于 author-side full TestMesh aggregation、目标 skill 领域质量或发布证明。

曾经的 TestMesh full aggregation 和完整 semantic adequacy receipt 不在本轮重新冻结的当前执行证据内；
因此当前仍只能写成“结构与安装窄路径已验证，native self-host/full semantic execution incomplete，
完整 aggregation/parity matrix 未验证”，不能写成 execution closure 或 semantic graduation 已完成。

通过条件：51 个命令、所有 route、所有 public mutation 和所有 required checks 都 accounted，且 surface inventory hash、contract hash、manifest hash 同一 source identity。<br>
失败条件：只运行旧 `self-check` 并把它的静态 pass 当成完整 surface pass。旧 `self-check` 的 claim boundary 较窄；真正的 completeness 以 `check-depth`/graduation 为准。

此前对 FlowGuard 15-member suite 的诊断为：`scope=static` 返回
`blocked`、`passed=0/15`。15 个成员的 `SKILL.md` 和旧合同结构检查可以读取，但每个成员都缺少 target-owned
`.skillguard/surface-inventory.json` 及其 depth-profile declaration，所以统一被
`contract_source_surface_inventory_declaration_missing` / `compiled_contract_surface_inventory_declaration_missing`
挡住；任何新 source identity 都必须重新执行，而不是复用旧诊断。这是应当保留的 fail-closed 结果，
不应批量复制一份假的一行 inventory 来制造绿色。

## 阶段 5：补齐 mutation-negative 测试

至少逐个验证：

1. 新增 dispatch command 但不加 inventory → blocked；
2. 新增 API/script/export 但不绑定 intent/owner/test → blocked；
3. 删除 route/check 但命令仍存在 → blocked；
4. 只绑定 generic smoke、没有 failure/recovery → blocked；
5. 两个 surface 共享一个 primary owner → blocked；
6. model obligation 没有实现 surface，也没有 model-only proof → blocked；
7. UI-like action 没有状态变化、错误和恢复 oracle → blocked；
8. 明确的 internal helper 有真实 verifier proof → allowed；
9. consumer tree 带 `.skillguard`、SkillGuard import/command、receipt/router/Portfolio 字段 → blocked；
10. `skillguard_version` 等 underscore identity key 或 JSON author field → blocked；
11. 只改变 pretty/uppercase/unprefixed manifest hash → blocked；
12. `skillguard_depth.py` 明确标记 retired/negative/not-runtime 且无真实 import → only this typed sentinel allowed。

每个负例都要验证 exit status、稳定 finding code 和没有发生不应发生的写入。

## 阶段 6：执行与复用 receipt

1. 先冻结 owner plan，再让唯一 execution owner 启动真正 native check；`--resume` 是执行命令，不是 read-only receipt audit。
2. 每个 required semantic check 必须有同 unit、同 request、同 inputs/dependencies/toolchain/environment 的 immutable terminal-success producer receipt。
3. 一个 producer 可以投影给多个语义 check，但每个 projection 必须保留自己的 subject/domain/obligation；不能用“一次 pass”抹掉语义差异。
4. result path 必须存在并重新计算 hash；producer receipt 必须重新计算 canonical hash，并绑定 owner/source/model/toolchain/environment/result/terminal/cleanup。
5. timeout/cancel 后先确认 descendant count=0，再决定是否允许新 owner；`cleanup-unconfirmed` 永远不可复用。

通过条件：0 missing/stale/skipped/failed/timed_out/cancelled/cleanup-unconfirmed，且 current aggregation 只读消费，不启动 owner。

## 阶段 7：构建独立 consumer projection

1. 从 author source 只投影 target-owned files；`.skillguard`、author contract、private receipt、router、Portfolio、maintenance identity 不得进入 consumer。
2. `consumer-release.json` 必须使用 FlowGuard-compatible compact sorted JSON、一个 LF、lowercase `sha256:<64 hex>`；release id 和 manifest hash 的输入字段固定。
3. 在没有 SkillGuard 的临时环境中运行 target-owned smoke；它必须仍能完成自己的 domain work。

通过条件：consumer tree 中 SkillGuard path/import/command/reference/receipt/router/Portfolio/author field 的扫描结果为 0，且 manifest raw bytes、release id、manifest hash、file hashes 全部 replay 通过。

结构性 consumer projection 规则已实现并有 focused tests；普通 consumer 仍不应携带 SkillGuard。
但跨边界 installed-current/fleet/release 结论必须以同一冻结身份下的实际 manifest、release id、安装和
consumer receipts 为准；“projection tree 没有 SkillGuard 文件”不能被写成“installed-current / release-current”。
若出现 producer 与 auditor 的 canonical JSON/hash authority 或 release id 不一致，必须先统一唯一 authority，
再重建同一冻结身份下的 consumer receipts。

## 阶段 8：安装、回滚和 bytecode residue

安装 currentness 与 validation receipt 分开检查：

- stage/activate/rollback/recover 事务各有 owner 和 negative test；
- consumer stage 中 `.pyc`、`.pyo`、`__pycache__` 为 0；
- 安装 currentness read-only 检查不能偷偷启动 smoke 或另一个 validation owner；
- 安装之后重新 replay target-owned currentness receipt，不把 source-only test 当 installed-current。

任何 bytecode residue、manifest mismatch、release id mismatch 或 rollback 无法恢复，都保持 `blocked`。

## 阶段 9：Portfolio 与 graduation

只在下列证据同时 current 时才允许 graduation：

1. contract structural current；
2. reverse surface current；
3. target execution current；
4. consumer projection current；
5. installed current；
6. Git/tag/publication current（若本次声明包含发布）。

任何一类证据缺失都写 `not_run/unverified/blocked`，不能用 README、OpenSpec checkbox、global registry 或旧 receipt 代替。

## 阶段 10：最终报告格式

最终报告必须分开列出：

- 已发现的真实 surface 数量和 source identity；
- governed/internal/retired/not-applicable 各自数量；
- intent/model/obligation/test/owner 双向 gap；
- 每个 required check 的 executed/reused/not-run 状态；
- producer receipt、result artifact、consumer manifest、installation receipt 的 fingerprints；
- UI、fault matrix、platform/provider、miss backfeed、release 哪些没有运行；
- 普通 consumer 是否保持 SkillGuard-free；
- claim boundary：当前到底只证明 scoped、functional、release 还是 highest-quality。

只要 reverse surface、真实执行、安装、UI 或故障证据仍缺失，措辞必须是“partial/scoped/blocked”，不能写“SkillGuard 已证明目标 skill 完整可用”。

本轮仍需保留的未闭合边界：global-router 的 5 行 inventory 已通过结构/depth 检查，但没有在本轮单独启动
一个 global-router maintenance unit 的 5-owner full semantic run；它的 current registry refresh 是
作者侧路由证据，不是该 skill 领域质量证明。另一个未闭合边界是反向 adequacy 的领域语义：SkillGuard 已经
能够要求 target-owned surface inventory、model-deepening 和 native receipts，但“这个 surface 的错误原因、
恢复行为和业务 oracle 是否正确”仍必须由目标 skill 自己提供，不能由 SkillGuard 的数量或 receipt 形状替代。
