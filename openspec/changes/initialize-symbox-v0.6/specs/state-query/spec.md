## Purpose

定义供 LLM/Agent 稳定消费的状态查询接口，使对象、Verb、backup 和单对象推理详情无需解析人类日志即可获得。

## ADDED Requirements

### Requirement: 查询对象集合
系统 SHALL 提供对象集合查询，并以结构化、确定顺序返回每个对象的名称、分类和是否为 Verb。

#### Scenario: 对象集合非空
- **WHEN** 调用方查询 `objects`
- **THEN** 系统返回当前项目所有对象的结构化摘要，顺序在状态不变时保持稳定

#### Scenario: 对象集合为空
- **WHEN** 当前项目尚无对象
- **THEN** 系统成功返回空集合而非未找到错误

### Requirement: 查询 Verb 集合
系统 SHALL 提供 Verb 集合查询，仅返回当前有效且显式具有 Verb 标记的对象。

#### Scenario: 混合对象中查询 Verb
- **WHEN** 项目同时存在普通对象、Worry 和 Verb 对象
- **THEN** `verbs` 查询只返回 Verb 对象及其可用绑定摘要

### Requirement: 查询 backup 集合
系统 SHALL 通过统一 list 查询入口提供现存 backup 摘要，且其结果与 backup 日志中的快照身份一致。

#### Scenario: 查询 backup
- **WHEN** 调用方查询 `backups`
- **THEN** 系统返回每个快照的稳定标识、note 与创建时间

### Requirement: 查询单对象详情
系统 SHALL 按对象名返回分类、显式与派生 Adj/tag、绑定、相关关系、真值和 justification 摘要；未知对象 MUST 返回明确的未找到结果。

#### Scenario: 查询存在对象
- **WHEN** 调用方查询一个存在的对象名
- **THEN** 系统返回该对象当前完整可观察状态，并标识状态来源是显式、派生或 assumption

#### Scenario: 查询未知对象
- **WHEN** 调用方查询不存在的对象名
- **THEN** 系统返回非成功的结构化未找到结果且不修改任何状态

### Requirement: 查询不改变状态
所有 list 查询 MUST 是只读操作，不得创建 backup、改变真值、运行有副作用的绑定或更新持久化时间戳。

#### Scenario: 重复执行查询
- **WHEN** 调用方在没有写命令的情况下重复执行同一查询
- **THEN** 除允许的非状态诊断元数据外，两次结果等价且项目状态字节级未被查询修改
