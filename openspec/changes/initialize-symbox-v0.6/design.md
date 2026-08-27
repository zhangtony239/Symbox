## Context

项目目前只有 Python 3.12+ 包骨架及 `ltms`、`z3-solver` 依赖，尚无实现。公开行为以本 change 的七个 capability spec 为准；设计来源是 Symbox v0.6 完整规范，其中 SVK 替代 SVO，且 TruthKernel 接缝、v1/v1.5/v2 分层和命名空间决策均属于当前架构。

系统面向 LLM/Agent 而非人类交互式会话，因此命令必须可组合、输出可机器解析、失败可诊断，并在进程级命令边界维持内存与磁盘原子性。动态绑定会加载项目提供的 Python 代码，它属于受信任项目内扩展机制，不作为不可信代码沙箱。

## Goals / Non-Goals

**Goals:**

- 通过端口化架构隔离 CLI、领域模型、真值内核、持久化、embedding 与 backup。
- 让 `ltms` 仅存在于 TruthKernel adapter 内，未来切换 ATMS 时公开 CLI 与领域模型无需变化。
- 使用一个事务协调器覆盖解析后的领域变更、Worry/Adj/Verb 检查、真值传播和持久化。
- 为 SVK、节点命名空间、序列化和结构化输出定义确定性编码。
- 以契约/场景测试验证 spec，而不是绑定到当前类布局。

**Non-Goals:**

- 当前实现不提供 ATMS label/nogood DB、多上下文并存、hitting-set 诊断或 Z3 非 Horn 求解。
- 不执行自然语言解析；CLI token 即规范输入。
- 不把动态 Python 绑定变成不可信代码隔离平台。
- 不在关系节点内部做论元级传播；一个 SVK 关系作为一个粗粒度事实节点。

## Decisions

### 1. 采用六边形分层与单一应用服务入口

包按 `cli`、`application`、`domain`、`kernel`、`persistence`、`integrations` 分层。CLI 只解析输入并把命令 DTO 交给应用服务；领域层保存 Subject、Verb、Adj、tag、Worry、SVK 及其显式来源；kernel 端口维护 truth/justification；基础设施实现磁盘、Git 与 embedding。

所有写命令进入同一个事务协调器：加载快照 → 构建候选领域状态 → 运行局部检查 → 同步候选节点/justification → 传播至稳定点 → 写临时状态 → 原子替换当前状态。任何阶段失败就丢弃候选状态。

**替代方案：**让每个 CLI handler 直接调用 `ltms` 与文件系统。该方案初期更短，但会复制回滚逻辑、泄漏内核 API，并阻碍 v1.5 替换，因此拒绝。

### 2. TruthKernel 是稳定端口，LTMS 是当前 adapter

TruthKernel 端口至少提供：注册/撤回节点、声明 assumption、增加/撤回 justification、读取三值状态、传播、解释事实、创建候选副本与提交。领域层只认识稳定节点 key 和三值枚举，不认识 `ltms` 对象。

当前 adapter 把 `ltms` 的 BCP 传播映射到端口。若依赖库不支持安全 clone，则每个事务从已提交领域快照在临时候选 kernel 中重建；正确性优先于启动性能。未来 ATMS adapter 可实现 label/nogood，但不改变上述基础端口。

**替代方案：**直接继承或包装库节点并暴露到领域对象。这样会把第三方生命周期和真值语义扩散到所有模块，拒绝。

### 3. 领域状态使用规范化 JSON，动态绑定保存引用而非代码对象

`.sbox/state.json` 保存带 schema version 的规范化状态：对象、分类、属性及来源、tag 来源、绑定引用、SVK 事实、节点与 justification 描述。JSON key 排序、集合排序并使用明确类型标签，以获得稳定 diff/hash。Python callable 不直接序列化，只保存项目相对源文件、函数限定名、源码摘要和 Verb/Worry 元数据，加载时重新校验。

写入使用同目录临时文件、flush/fsync 后原子 replace；进程启动时只接受完整且 schema version 可识别的状态。

**替代方案：**pickle 可直接保存对象，但存在代码执行、安全、跨版本和不可审计问题；数据库对当前单项目 CLI 过重，均拒绝。

### 4. SVK 采用双层表示并以规范化内容生成身份

CLI parser 先产生 `subject`、`verb`、位置 `args` 和具名 `kwargs`。绑定解析器按 Python signature 绑定 Subject 为显式第一参数，并展开默认值，得到 `effective_args/effective_kwargs`。领域对象保留原始位置结构和完整有效参数。

关系 key 使用 `SVK:<subject>:<verb>:<digest>` 命名空间；digest 输入是带类型标记的规范 JSON，包含 Subject、Verb、位置论元与排序后的有效具名论元，使用 SHA-256。显示可截短，但持久化身份保留足够长度并在碰撞时拒绝提交，不能静默合并。

v0.6 原文的 key 示例存在 `SVK:hash` 与 `SVK:s:v:hash` 两种展示，本设计选择后者作为全局命名空间，digest 规则保证参数顺序确定性。

**替代方案：**只散列 kwargs 会丢失位置论元结构；以人类可读整句作 key 会受转义与长度影响，均拒绝。

### 5. 节点命名空间集中编码

统一 NodeKey codec 生成 `Subject:<id>`、`Adj:<subject>:<key>`、`SVK:<subject>:<verb>:<digest>`、`Worry:<id>` 等 key，所有用户标识先做长度前缀或百分号转义，禁止通过冒号制造碰撞。NodeKey codec 同时负责 parse 与 round-trip 测试。

**替代方案：**各模块拼接字符串，容易形成不可逆 key 和命名空间冲突，拒绝。

### 6. 动态检查分为纯检查阶段与候选效果阶段

绑定 callable 在候选事务上下文中执行。检查返回 bool，True=通过/健康，False=冲突；可选效果必须写入事务提供的受控 mutation context，而不能直接修改已提交对象。首先运行 check，再将效果施加到候选状态并传播。Worry 订阅属性依赖，属性变化即时触发；传播尾部对受影响 Worry 重评估直至固定点，并设定迭代上限防止振荡。

**替代方案：**允许函数直接修改任意领域对象，无法可靠回滚且 check/apply_effect 副作用耦合；因此即使 v0.6 将其列为后续讨论，实现边界仍先通过事务上下文隔离风险。

### 7. Embedding 是可失败的建议型端口

属性写入先做精确名称判定，再尝试 OpenAI-compatible embedding provider。provider 从环境读取 base URL、API key、model、threshold，设定超时且不落盘凭据。未配置或失败返回 degraded 诊断，不中止普通写入。向量可按 provider/model/key 缓存，但缓存不是权威状态。

相似度严格使用 `score > threshold`；`--force` 只绕过此次相似 key 确认，不绕过类型、Worry 或真值矛盾。

**替代方案：**embedding 失败即命令失败会把一致性辅助服务变成可用性单点，违背规范，拒绝。

### 8. Backup 使用独立 Git 仓库存储规范状态

`.sbox/backups/` 初始化为 bare Git 仓库。每个快照把当前规范状态组成 tree/commit，commit message 保存 note，外部返回完整 commit id。日志按提交时间和 id 稳定排序。回滚先在临时目录读取并完整验证目标 tree，再通过普通状态提交路径原子替换当前状态。

删除快照通过受管理 refs 表达，而不是改写不可达对象；批量删除先验证全部 id，再统一更新 refs。运行配置与凭据不进入 tree。

**替代方案：**直接复制目录实现简单，但缺乏内容寻址、历史元数据和完整性校验；使用当前项目主 Git 仓库会污染用户源码历史，均拒绝。

### 9. CLI 结果统一为 JSON envelope 与退出码

stdout 输出单个 JSON envelope：`status`、`data`、`diagnostics`、`conflicts`、`transaction_id`；stderr 只用于无法形成 envelope 的启动级故障。成功和 `confirm_needed` 使用可区分状态，验证/冲突/系统错误使用非零退出码分类。list 输出数组按规范字段排序，查询不得触发可变更状态的 callable。

命令树提供 `create`、`delete`、`bind`、`unbind`、`set`、`unset`、`now`、`list` 和 `backup {create,delete,rollback,list}`。不注册 `svo` 别名，以避免形成未规范化兼容面。

**替代方案：**人类文本加部分 JSON 会迫使 Agent 解析日志，拒绝。

## Risks / Trade-offs

- [v0.6 文本局部存在 S 是否进入 kwargs、hash 长度示例不一致] → 以公开调用契约“Subject 是显式第一参数”和本设计的完整规范编码为准，并用 golden tests 固定身份规则。
- [LTMS 库能力或语义与三值端口不完全吻合] → 先编写 adapter contract tests；缺失能力由 adapter 维护最小元数据，无法可靠映射时从领域快照重建候选 kernel。
- [动态绑定代码可产生外部副作用] → 明确其为受信任扩展；文档要求检查纯函数，超时/异常使事务失败，但不承诺进程内沙箱能撤销网络或外部文件副作用。
- [每事务 clone/rebuild 在大图上成本高] → 当前优先正确性；记录节点数、传播次数与耗时，后续可引入 copy-on-write 或 journal，不改变端口。
- [Git bare 仓库并发更新 refs] → 使用文件锁和 compare-and-swap ref 更新；冲突时整个 backup 操作失败并重试。
- [embedding 非确定性导致不同时间确认结果变化] → 确认只作为写入前提示，阈值/provider/model进入诊断；`--force` 提供显式裁决，权威事实不依赖缓存向量。
- [Worry/派生效果循环不收敛] → 追踪本轮状态签名和最大迭代数，检测重复/越界即回滚并返回循环诊断。

## Migration Plan

1. 建立包骨架、NodeKey/序列化格式与 CLI JSON envelope，不读取任何旧运行状态。
2. 实现领域仓储和 TruthKernel contract，以 in-memory fake 驱动应用层测试。
3. 接入 LTMS adapter、动态绑定、Worry、embedding 与 Git backup。
4. 逐 capability 运行场景测试，并用端到端 CLI 测试验证退出码、原子性与磁盘恢复。
5. 首次运行创建带 schema version 的 `.sbox/state.json`；因当前项目无既有实现，不需要数据迁移。

回滚策略：实现发布失败时回退代码版本；若状态 schema 尚未提交则无需处理，若已提交则先用兼容版本导出/恢复最近 backup。任何未来 schema 升级必须先自动创建 pre-migration backup，迁移失败保留原文件。
