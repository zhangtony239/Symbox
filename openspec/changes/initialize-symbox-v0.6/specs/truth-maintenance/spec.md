## Purpose

定义 Symbox v0.6 当前层集中式真值维护的可观察一致性、依据追踪、撤回传播和事务边界，确保失败断言不会污染当前知识状态。

## ADDED Requirements

### Requirement: 三值真值状态
系统 SHALL 为可推理事实维护 `true`、`false`、`unknown` 三种状态，并由统一真值内核持有状态而非把最终真值分散存放在领域对象中。

#### Scenario: 已支持事实为 true
- **WHEN** 一个事实具有当前有效且未被击败的 justification
- **THEN** 系统查询该事实时返回 `true`

#### Scenario: 支持被撤回后变为 unknown
- **WHEN** 一个 true 事实的全部有效 justification 被撤回且无反向依据
- **THEN** 系统传播后返回该事实为 `unknown`

#### Scenario: 健康条件失败为 false
- **WHEN** 一个接入真值网络的必要健康条件变为不成立
- **THEN** 系统把对应节点标记为 `false` 并传播其后果

### Requirement: justification 可追踪
每个派生真值 SHALL 保留足以说明其直接依据的 justification；查询冲突或事实详情时，系统 MUST 返回可遍历到相关基元事实或 assumption 的依据链。

#### Scenario: 查询派生事实依据
- **WHEN** 调用方查询一个由多个前提推出的事实
- **THEN** 结果包含该事实的直接前提，并允许继续定位前提来源

#### Scenario: 返回矛盾依据
- **WHEN** 新命令因传播检测到矛盾而失败
- **THEN** 冲突结果标识冲突事实及已知 justification 链，而不只返回布尔失败

### Requirement: 统一传播调度
对象、Adj、tag、SVK 关系与 Worry 状态的变化 MUST 注册到同一传播调度中，以检测跨对象和跨关系的传播可达矛盾。

#### Scenario: 跨关系矛盾
- **WHEN** 一个新关系与另一对象上的既有属性通过 justification 链共同构成矛盾
- **THEN** 系统在该命令提交前检测冲突

#### Scenario: 属性撤回修正派生事实
- **WHEN** 作为关系依据的属性被撤回
- **THEN** 系统沿依赖链重新计算所有受影响事实

### Requirement: 命令事务原子性
每个改变状态的 CLI 命令 MUST 是原子事务；任何解析、类型、绑定、校验、传播、持久化或冲突错误 MUST 使内存与磁盘可观察状态恢复到命令前。

#### Scenario: 传播阶段发现矛盾
- **WHEN** 命令的局部校验通过但统一传播发现矛盾
- **THEN** 系统返回非成功冲突结果，且对象、真值、justification 与持久化状态均未提交本次变化

#### Scenario: 全流程成功
- **WHEN** 命令所有阶段成功且传播达到稳定状态
- **THEN** 系统一次性提交领域状态与真值状态并返回成功

### Requirement: 当前层推理边界
v0.6 当前 LTMS 实现层 MUST 对其已产生的传播结论保持健全，并 SHALL 检测传播链可达矛盾；当前层 SHALL NOT 声称对任意非 Horn 约束、不可达深层矛盾或多上下文假设组合具备完备判定。

#### Scenario: 无法推出的深层矛盾
- **WHEN** 输入只在当前 LTMS 传播能力之外的全局约束下矛盾
- **THEN** 系统可保留 `unknown` 或接受该事实，但不得伪造已证明的冲突依据

#### Scenario: 传播可达矛盾
- **WHEN** 冲突可由已注册规则和当前 justification 链推出
- **THEN** 系统必须拒绝导致该冲突的事务
