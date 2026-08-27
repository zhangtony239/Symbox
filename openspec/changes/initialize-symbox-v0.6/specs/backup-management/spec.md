## Purpose

定义项目本地 backup 的可恢复快照契约，使 Agent 能在实验操作前保存状态、查看历史并以原子方式回到已知状态。

## ADDED Requirements

### Requirement: 项目本地 backup 存储
系统 SHALL 在当前项目的 `.sbox/backups/` 中维护隔离的 backup 存储，并 MUST 确保一个项目的 backup 命令不读取或修改其他项目的状态。

#### Scenario: 首次创建 backup
- **WHEN** 当前项目尚无 backup 存储且调用方创建快照
- **THEN** 系统初始化项目本地存储并创建首个可恢复快照

#### Scenario: 切换项目作用域
- **WHEN** 在另一个项目目录执行 backup 日志查询
- **THEN** 系统仅返回该项目自己的快照历史

### Requirement: 创建具名快照
系统 SHALL 支持使用非空 note 创建当前已提交 Symbox 状态的快照，并返回可供删除和回滚使用的稳定标识。

#### Scenario: 创建快照成功
- **WHEN** 当前状态完整可持久化且 note 合法
- **THEN** 系统原子记录当前领域状态与真值状态并返回快照标识和 note

#### Scenario: 快照持久化失败
- **WHEN** backup 存储不可写或状态序列化失败
- **THEN** 系统返回错误且不得留下可见的半成品快照

### Requirement: 查看和删除快照
系统 SHALL 通过 `backup list` 按确定顺序列出快照标识、note 与创建时间，并 SHALL 支持一次删除一个或多个指定快照；`backup log` 已被 `backup list` 彻底替换并移除，系统 MUST NOT 注册、接受或保留任何 `backup log` 兼容别名；包含未知标识的批量删除 MUST 不删除任何目标。

#### Scenario: 查看历史
- **WHEN** 调用方请求 backup 日志
- **THEN** 系统按从新到旧的确定顺序返回所有现存快照元数据

#### Scenario: 原子批量删除
- **WHEN** 删除请求中的所有快照标识均存在且不违反存储完整性
- **THEN** 系统在一个操作中删除全部指定快照

#### Scenario: 批量删除含未知标识
- **WHEN** 删除列表至少包含一个未知快照标识
- **THEN** 系统返回错误且列表中其他快照也不被删除

### Requirement: 原子回滚
系统 SHALL 支持回滚到指定快照，并 MUST 同时恢复领域对象、绑定元数据、属性、关系、真值与 justification 的一致状态。

#### Scenario: 回滚到已知快照
- **WHEN** 调用方选择一个存在且可读取的快照
- **THEN** 系统原子恢复该快照状态，随后查询结果与快照创建时一致

#### Scenario: 回滚目标无效
- **WHEN** 快照不存在、损坏或无法完整加载
- **THEN** 系统返回错误且当前运行状态保持不变

### Requirement: backup 不暴露凭据
系统 MUST 从 backup 内容和日志中排除 embedding API key 及其他仅由环境提供的敏感凭据。

#### Scenario: 创建含外部服务配置的项目快照
- **WHEN** 当前进程通过环境变量配置了 embedding 凭据
- **THEN** 快照与日志不包含凭据明文，回滚后继续从当前环境读取凭据
