## Purpose

定义 Symbox 中可被 LLM/Agent 操作的对象类别、生命周期、函数绑定和类型隔离契约，为所有状态与关系操作提供稳定句柄。

## ADDED Requirements

### Requirement: 对象生命周期
系统 SHALL 提供按项目作用域创建和删除具名对象的 CLI 操作；对象名称在同一项目状态中 MUST 唯一，失败操作 MUST 不留下部分对象状态。

#### Scenario: 创建新对象
- **WHEN** 调用方使用尚未占用的名称创建对象
- **THEN** 系统创建该对象并返回成功结果，使其可被后续属性、绑定和关系命令引用

#### Scenario: 拒绝重复名称
- **WHEN** 调用方创建一个名称已存在的对象
- **THEN** 系统返回非成功结果且保留原对象不变

#### Scenario: 删除对象
- **WHEN** 调用方删除一个存在的对象
- **THEN** 系统撤回该对象及其直接事实句柄，并触发依赖真值的重新计算

### Requirement: 对象分类与类型隔离
每个对象 SHALL 具有 `physical`、`abstract` 或 `meta` 分类；系统 MUST 在关系断言时执行 Verb 声明的适用分类约束，并拒绝不允许的组合。

#### Scenario: 拒绝普通 Verb 作用于 meta 对象
- **WHEN** 一个未声明支持 meta 分类的 Verb 被用于 meta 对象
- **THEN** 系统返回类型冲突且不写入关系

#### Scenario: 接受声明允许的分类
- **WHEN** Subject 与所有论元满足 Verb 声明的分类约束
- **THEN** 系统继续执行该 Verb 的关系校验

### Requirement: 函数绑定与 Verb 标记
系统 SHALL 允许调用方从指定 Python 源文件把具名检查函数绑定到对象，也 SHALL 允许解除绑定；只有显式标记为 Verb 的对象 MUST 能出现在 `now` 命令的动词位置。

#### Scenario: 绑定普通检查函数
- **WHEN** 调用方提供可加载源文件、对象名和符合约定的函数名
- **THEN** 系统把函数绑定到对象且不赋予该对象 Verb 身份

#### Scenario: 绑定 Verb
- **WHEN** 调用方绑定符合 `check(S, *args, **kwargs) -> bool` 调用约定的函数并指定 Verb 标记
- **THEN** 系统记录该对象可用于 `now` 命令的动词位置

#### Scenario: 拒绝非 Verb 动词位
- **WHEN** `now` 命令在动词位置引用未标记为 Verb 的对象
- **THEN** 系统返回验证错误且不创建关系

#### Scenario: 绑定加载失败
- **WHEN** 源文件、函数名或函数调用约定无效
- **THEN** 系统返回可诊断错误且保持对象原有绑定不变

### Requirement: Adj 与 tag 模型
对象 SHALL 能同时持有多个具名 Adj 状态和多个 tag；Adj MAY 声明蕴含的 tag，系统 MUST 能区分显式 tag 与由 Adj 派生的 tag。

#### Scenario: 多属性共存
- **WHEN** 调用方为同一对象写入多个名称不同且未触发冲突确认的 Adj
- **THEN** 系统保留所有 Adj 及各自的值、时间和 justification 信息

#### Scenario: 显式 tag 与派生 tag 共存
- **WHEN** 一个对象同时被显式赋予 tag 且其 Adj 也派生 tag
- **THEN** 查询结果分别保留二者来源，并把二者都视为对象的有效 tag
