## Purpose

定义对象属性的原子写入和撤回、相似名称风险确认、嵌入服务降级以及由属性自动派生 tag 的可观察行为。

## ADDED Requirements

### Requirement: 原子属性写入与撤回
系统 SHALL 支持一次为对象设置一个或多个键值，也 SHALL 支持一次撤回一个或多个键；整个命令 MUST 作为单个原子事务执行。

#### Scenario: 批量设置成功
- **WHEN** 所有目标 key 均通过验证且无需确认
- **THEN** 系统在同一事务中写入全部值并触发一次统一传播

#### Scenario: 批量设置部分无效
- **WHEN** 一次设置中的任一 key 或 value 无效
- **THEN** 系统返回错误且该次设置中的所有 key 均保持原值

#### Scenario: 撤回属性
- **WHEN** 调用方撤回对象上存在的属性 key
- **THEN** 系统移除该显式属性事实并重新计算其派生 tag 与依赖事实

### Requirement: 相似 key 确认
当一个新 key 与对象既有 key 的 embedding 相似度严格大于 `SIMILARITY_THRESHOLD` 时，系统 MUST 暂停写入并返回结构化确认请求；带强制确认的重试 SHALL 执行该写入。

#### Scenario: 新 key 超过阈值
- **WHEN** 新 key 与既有 key 的相似度大于配置阈值且命令未带强制确认
- **THEN** 系统不修改状态，并返回 `confirm_needed`、目标对象、既有 key、拟议 key 与供调用方裁决的问题

#### Scenario: 强制确认后写入
- **WHEN** 调用方使用相同输入并提供强制确认
- **THEN** 系统跳过本次相似 key 拦截并按正常事务规则写入

#### Scenario: 相似度等于阈值
- **WHEN** 新 key 与既有 key 的相似度恰好等于配置阈值
- **THEN** 系统不因该比较要求确认

### Requirement: Embedding 配置与降级
系统 SHALL 从环境配置读取 embedding endpoint、凭据、模型和相似度阈值；在 embedding 未配置或调用失败时，系统 MUST 降级为精确字符串名称判定，不得因外部 embedding 不可用阻断普通属性写入。

#### Scenario: Embedding 服务可用
- **WHEN** embedding 配置完整且服务成功返回向量
- **THEN** 系统使用配置阈值执行新旧 key 相似度检测

#### Scenario: Embedding 服务不可用
- **WHEN** embedding 配置缺失、超时或服务返回失败
- **THEN** 系统继续处理命令，仅执行精确字符串名称判定，并在诊断信息中说明相似度检测已降级

### Requirement: tag 自动派生
当生效的 Adj 声明蕴含 tag 时，系统 SHALL 自动使这些 tag 对所属对象生效；当最后一个支持来源被撤回时，系统 MUST 撤回对应派生 tag，但 MUST 保留同名显式 tag。

#### Scenario: Adj 派生 tag
- **WHEN** 一个声明 `implies_tags` 的 Adj 在对象上变为有效
- **THEN** 系统将所声明 tag 作为派生 tag 加入对象状态

#### Scenario: 撤回最后一个派生来源
- **WHEN** 一个派生 tag 的最后一个有效 Adj 来源被撤回且不存在同名显式 tag
- **THEN** 系统撤回该 tag 并传播依赖变化

#### Scenario: 保留同名显式 tag
- **WHEN** 派生来源被撤回但对象仍具有同名显式 tag
- **THEN** 该 tag 继续有效且来源仅保留为显式
