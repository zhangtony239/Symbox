## Why

Symbox 设计规范 v0.6 已经取代先前版本并构成当前完整设计，但项目尚无可验证、可实施的 OpenSpec 行为契约。现在需要将 v0.6 全量规范初始化为项目基线，使后续实现、测试和演进都围绕同一组需求进行。

## What Changes

- 建立以 Python 3.12+ 实现、面向 LLM/Agent 的 Symbox v0.6 原子 CLI 基线。
- 定义 Subject、Verb、Adj、tag、Worry 等对象的注册、删除、绑定和类型约束。
- 定义 `now` 命令及 SVK 变长论元模型；规范只描述 v0.6 当前接口，不保留已被取代的固定 SVO 三槽位接口。
- 定义由引擎集中持有的三值真值、justification、撤回传播和矛盾原子回滚行为。
- 定义 Adj 状态、相似 key 确认、tag 派生及嵌入服务降级行为。
- 定义 Worry 的 ECA 监控与 True=正常、False=矛盾的统一极性。
- 定义项目本地、基于 Git 的 backup 创建、查询、删除和回滚能力。
- 定义对象、动词、备份与单对象状态的机器可消费查询接口。
- 关系断言统一使用 `sbox now <S> <V> ...` 与 SVK。

## Capabilities

### New Capabilities

- `object-model`: Subject、Verb、Adj、tag 与 meta 对象的生命周期、分类和绑定契约。
- `attribute-state`: Adj 属性写入、撤回、相似 key 确认及 tag 派生行为。
- `svk-assertions`: `now` 命令、SVK 变长论元解析、Verb 校验与稳定关系标识。
- `truth-maintenance`: 三值真值、justification、统一传播、撤回与原子矛盾处理。
- `worry-monitoring`: 值域变化到符号健康节点的 ECA 桥接与传播行为。
- `backup-management`: 基于项目本地 Git 存储的快照创建、日志、删除与回滚。
- `state-query`: 对象、动词、备份及对象详情的结构化查询行为。

### Modified Capabilities

无；当前 `openspec/specs/` 尚无既有能力规范。

## Impact

- 新增 Symbox v0.6 的完整公开 CLI 行为契约和 Python 包/命令入口实现范围。
- 影响核心领域模型、TruthKernel 适配层、LTMS 传播、持久化、embedding provider 与命令输出格式。
- 以 `ltms` 作为 v0.6 当前真值内核依赖；`z3-solver` 保留给 v0.6 路线图中的非 Horn/诊断能力，不纳入当前层验收范围。
- 在项目下使用 `.sbox/` 保存运行状态，并以 `.sbox/backups/` 承载 backup 存储；敏感配置来自环境变量，不写入状态或备份输出。
- v0.6 当前实现层聚焦单上下文、传播可达矛盾和快速反馈；规范同时保留 TruthKernel 可替换接缝，ATMS 多上下文、最小撤回建议、Z3 全局求解及 QSIM 式 Worry 扩展按 v0.6 的 v1.5/v2 分层后续实现。
