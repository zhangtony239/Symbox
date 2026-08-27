## Why

当前 README 将 Symbox 描述成“项目本地符号状态 CLI”，并承担了过多操作参考职责，容易让 Agent 把它误解为项目管理工具，而不是用于外化、同步和约束其内在逻辑世界的认知护栏。项目需要一个遵循 Agent Skills 规范的技能入口，把 v0.6 的概念模型和正确工作流直接交给 Agent，同时让 README 回归项目介绍与安装入口。

## What Changes

- 新增 `skills/symbox/SKILL.md`，采用标准 Agent Skill 目录与 YAML frontmatter，明确触发条件、核心心智模型和 Agent 使用 Symbox 的分步流程。
- Skill 将 Symbox 定义为 LLM/Agent 的外部符号逻辑世界：对象承载当前认知，Verb 与 Adj 的检查关系表达约束，Worry 表达持续关注的元认知条件，`now` 同步 Agent 当下所想并在提交前暴露矛盾或幻觉风险。
- Skill 基于 v0.6 的 SVK 模型指导 Agent 使用可变长论元，而不引入深层格术语，也不把 Symbox 当成项目 CLI 管理器。
- 精简 README，使其聚焦项目定位、适用场景、Agent Skill 安装和基于 `uv tool` 的 CLI 安装；详细操作方法由 Skill 和 CLI 自身帮助承担。
- 保留必要的推理边界说明，避免把当前 LTMS 能力描述成任意逻辑完备性或“绝对防幻觉”保证。

## Capabilities

### New Capabilities
- `agent-guidance`: 定义可安装 Agent Skill 的格式、触发语义、认知建模原则，以及 Agent 使用 `now`、Verb、Adj 和 Worry 维护内在逻辑世界的规范工作流。
- `project-onboarding`: 定义 README 对项目定位、Skill 安装及 `uv tool` 安装入口的精简职责。

### Modified Capabilities

<!-- 当前 openspec/specs/ 为空；此变更不修改既有 capability。 -->

## Impact

- 新增文档资产：`skills/symbox/SKILL.md`。
- 重写项目入口文档：`README.md`，移除大段 CLI、存储和开发参考内容，保留简明定位与安装路径。
- 不改变 Python API、CLI 命令行为、状态格式、真值内核或运行时依赖。
- Skill 格式对齐 Agent Skills 开放规范与 Anthropic authoring guidance：使用与目录匹配的 kebab-case 名称、同时描述“做什么/何时使用”的 description、渐进披露和面向行动的指令。
