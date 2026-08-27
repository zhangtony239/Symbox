## Purpose

为支持 Agent Skills 的客户端提供可发现、可安装的 Symbox 使用指南，使 Agent 能把自己的当前认知外化为受约束的符号世界，并在行动过程中持续同步和检查它。

## ADDED Requirements

### Requirement: Skill 具有标准且可发现的入口
项目 SHALL 在 `skills/symbox/SKILL.md` 提供 Agent Skill；该文件 SHALL 包含有效 YAML frontmatter，名称 SHALL 与 `symbox` 目录一致，description SHALL 同时说明 Skill 的用途与触发场景。

#### Scenario: Agent 客户端发现 Skill
- **WHEN** 支持 Agent Skills 规范的客户端扫描 `skills/symbox`
- **THEN** 客户端能够从 `SKILL.md` 的 frontmatter 识别名为 `symbox` 的 Skill，并判断何时应加载它

### Requirement: Skill 建立正确的 Symbox 心智模型
Skill SHALL 明确说明 Symbox 是 LLM/Agent 用于外化其内在逻辑世界、同步当前认知并监视矛盾的符号护栏，而不是项目 CLI 管理器、事实来源或任意逻辑的完备证明器。

#### Scenario: Agent 判断 Symbox 的职责
- **WHEN** Agent 阅读 Skill 以决定是否用 Symbox 管理项目任务
- **THEN** Skill 引导 Agent 仅将 Symbox 用于表达和校验自身认知中的对象、关系、约束与担忧，不将其当作项目管理系统

#### Scenario: Agent 解释防幻觉边界
- **WHEN** Agent 依据 Symbox 未报告冲突而形成结论
- **THEN** Skill 要求 Agent 将该结果解释为“在已编码约束与当前推理边界内未发现冲突”，而不是外部事实已被证明或幻觉已被绝对排除

### Requirement: Skill 指导 Agent 表达逻辑世界
Skill SHALL 说明对象用于承载当前认知，Verb 用于表达 SVK 关系及其论元检查，Adj 用于表达对象属性和约束补丁，Worry 用于持续监视需要关注的元认知条件；Verb 和 Adj 中的检查关系 SHALL 被描述为约束编码位置。

#### Scenario: Agent 建模约束
- **WHEN** Agent 需要记录某个动作只在特定对象属性或论元组合下成立
- **THEN** Skill 引导 Agent 把该约束编码到相应 Verb 或 Adj 的检查关系中，而不是仅保留在自然语言上下文里

#### Scenario: Agent 建模担忧
- **WHEN** Agent 需要持续关注某种可能令当前认知失效的状态
- **THEN** Skill 引导 Agent 使用 Worry 表达该元认知条件，并遵循 `True` 表示正常、`False` 表示触发矛盾的极性

### Requirement: Skill 指导 Agent 使用 now 同步当前认知
Skill SHALL 将 `now` 描述为 Agent 把“此刻所想”同步至 Symbox 的原子断言操作，并 SHALL 使用 v0.6 的 SVK 可变长论元模型解释零个、一个或多个后置论元与具名参数。

#### Scenario: 同步零后置论元关系
- **WHEN** Agent 要表达主体自身发生的状态变化
- **THEN** Skill 允许 Agent 使用仅含 Subject 与 Verb 的 `now` 断言

#### Scenario: 同步多论元关系
- **WHEN** Agent 要表达带多个参与者或限定信息的关系
- **THEN** Skill 引导 Agent 使用位置论元和具名参数组成可变长论元包，且不强制采用 Fillmore 深层格术语

#### Scenario: 同步失败
- **WHEN** `now` 因参数、检查或传播冲突而失败
- **THEN** Skill 告知 Agent 该断言不会进入符号世界，并要求其检查自身假设、补足信息或修正建模后再重试

### Requirement: Skill 提供可执行的 Agent 工作流
Skill SHALL 给出简洁、面向行动的工作流，覆盖初始化认知对象、绑定约束、写入属性、使用 `now` 同步、查询结果、响应确认或冲突，以及在认知发生变化时继续同步。

#### Scenario: Agent 开始处理需要一致性约束的任务
- **WHEN** Agent 面临跨多步推理、多个对象关系或易发生前后矛盾的任务
- **THEN** Skill 引导 Agent 先外化相关对象与约束，再在每次关键认知变化后同步和查询 Symbox

#### Scenario: Symbox 报告冲突
- **WHEN** 命令结果表明当前断言与已编码约束冲突
- **THEN** Skill 要求 Agent 根据 diagnostics、conflicts 和已知依据修正其内在模型，而不是绕过检查或虚构成功状态

