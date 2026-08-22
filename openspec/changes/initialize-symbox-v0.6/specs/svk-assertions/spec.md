## Purpose

定义 `now` 关系断言接口与 SVK 变长论元契约，使零论元自我修改、位置论元和具名论元在同一原子命令中可被校验和记录。

## ADDED Requirements

### Requirement: now 命令使用 SVK 关系格式
系统 SHALL 通过 `sbox now <subject> <verb> [args...] [key=value...]` 接收关系断言，其中 Subject 和 Verb 是必需前槽位，其余位置论元与具名论元组成可为空的变长论元包。

#### Scenario: 零个后置论元
- **WHEN** 调用方执行仅含 Subject 和 Verb 的 `now` 命令
- **THEN** 系统把它解析为 `S`、`V` 和空论元包，并允许 Verb 表达 Subject 的自我修改

#### Scenario: 多个位置论元
- **WHEN** 调用方在 Subject 与 Verb 后提供多个位置值
- **THEN** 系统保持其顺序并把完整位置论元序列交给 Verb 校验

#### Scenario: 混合位置与具名论元
- **WHEN** 调用方同时提供位置论元和不重名的 `key=value` 论元
- **THEN** 系统把两类论元无损传递给 Verb 校验并记录于关系事实

### Requirement: Verb 参数契约
系统 MUST 把 Subject 作为 Verb 校验的显式第一参数，并按 Verb 声明解析其余论元；缺失无默认值的必需参数、重复具名参数或未知且不被接收的参数 MUST 产生验证错误。

#### Scenario: 使用参数默认值
- **WHEN** 调用方省略一个由 Verb 声明默认值的参数
- **THEN** 系统使用该默认值完成校验并在规范化关系中记录有效参数值

#### Scenario: 缺失必需参数
- **WHEN** 调用方未提供 Verb 要求且无默认值的论元
- **THEN** 系统返回指出缺失参数的可诊断错误且不创建关系

#### Scenario: 重复具名参数
- **WHEN** 同一个参数名在命令中被填充两次
- **THEN** 系统返回结构性冲突且不调用 Verb 的业务校验

### Requirement: Verb 校验极性
Verb 的检查结果 MUST 使用 True 表示关系可成立，False 表示关系产生矛盾；False 结果 MUST 进入统一矛盾处理而不得写入主图。

#### Scenario: Verb 校验通过
- **WHEN** Verb 对 Subject 与完整论元包返回 True 且传播未发现其他矛盾
- **THEN** 系统提交关系事实

#### Scenario: Verb 校验失败
- **WHEN** Verb 对 Subject 与完整论元包返回 False
- **THEN** 系统返回冲突结果和可用的依据，且状态与命令前完全一致

### Requirement: 关系身份稳定且顺序规范化
系统 SHALL 根据关系的 Subject、Verb、位置论元和具名论元生成稳定的 `SVK` 关系身份；语义等价但具名参数顺序不同的调用 MUST 指向同一身份，不同完整论元包 MUST 不被视为同一关系。

#### Scenario: 具名参数顺序不同
- **WHEN** 两个断言仅有具名参数的输入顺序不同而有效值完全相同
- **THEN** 系统为二者生成相同的关系身份

#### Scenario: 任一有效论元不同
- **WHEN** 两个断言的 Subject、Verb、位置论元或任一有效具名论元不同
- **THEN** 系统将二者作为不同关系事实处理

### Requirement: v0.6 关系断言入口
v0.6 公开关系断言接口 MUST 使用 `now`；固定三槽位的 `svo` 命令不属于当前规范。

#### Scenario: 客户端使用规范接口
- **WHEN** 客户端需要创建任意元数关系
- **THEN** 客户端能够仅使用 `now` 完成零个、一个或多个后置论元的断言
