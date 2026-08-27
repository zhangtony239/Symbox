## Purpose

让首次接触项目的用户快速理解 Symbox 的真实定位，并能选择安装 Agent Skill 与命令行工具，而不把 README 变成长篇内部实现或命令参考手册。

## ADDED Requirements

### Requirement: README 准确介绍项目定位
README SHALL 在开头将 Symbox 定义为 LLM/Agent 外化和约束其内在逻辑世界的工具，说明 Verb、Adj、Worry 与 `now` 在防止认知前后矛盾中的作用，并 SHALL 避免将其称为项目 CLI 管理器。

#### Scenario: 新用户阅读项目简介
- **WHEN** 用户打开 README 的首屏内容
- **THEN** 用户能够理解 Symbox 管理的是 Agent 对世界的符号化认知，而不是项目任务、依赖或脚手架

### Requirement: README 提供 Agent Skill 安装入口
README SHALL 提供从仓库 `skills/symbox` 安装或复制 Skill 的说明，并 SHALL 说明应将该目录放入所用 Agent 客户端支持的 skills 位置；对于客户端相关路径，README SHALL 避免声称单一目录适用于所有客户端。

#### Scenario: 用户为 Agent 安装 Skill
- **WHEN** 用户按 README 的 Skill 安装步骤操作
- **THEN** 用户知道需要安装完整的 `symbox` Skill 目录，并依据其 Agent 客户端选择目标 skills 目录

### Requirement: README 提供 uv tool 安装入口
README SHALL 提供基于 `uv tool` 的 Symbox CLI 安装和基础验证命令，并清楚区分本地仓库安装与已发布包安装方式（若两者均被展示）。

#### Scenario: 用户从本地仓库安装 CLI
- **WHEN** 用户已克隆项目并执行 README 中的本地 `uv tool` 安装步骤
- **THEN** `sbox` 命令可直接调用，且用户可通过版本或帮助命令验证安装

### Requirement: README 保持入口文档范围
README SHALL 聚焦项目简介、工作原理概览、安装和最小上手示例；详细命令树、持久化实现、embedding 配置、backup 内部机制和开发验证 SHALL 由 Skill、CLI help 或专门文档承担，而不继续作为 README 的主体内容。

#### Scenario: 用户浏览 README
- **WHEN** 用户从头到尾阅读 README
- **THEN** 文档以较短路径完成“理解定位—安装 Skill—安装工具—运行最小示例”，无需先阅读内部实现细节

### Requirement: README 陈述有限保证
README SHALL 说明 Symbox 只能依据 Agent 已外化的事实、关系和检查约束发现当前推理范围内的冲突，不能验证未输入的外部事实，也不保证完备消除幻觉。

#### Scenario: 用户评估可靠性承诺
- **WHEN** 用户阅读 README 中关于矛盾与幻觉的描述
- **THEN** 用户不会被引导相信 Symbox 能独立验证现实真相或完备证明任意逻辑结论

