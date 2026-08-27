## Context

变更动机见 `proposal.md`。当前入口只有一份 125 行的 README，它混合项目定位、完整命令树、绑定示例、存储格式、embedding 配置、backup 细节和开发命令；尚无 `skills/` 目录。v0.6 规范已定义 SVK、`now`、Verb/Adj/Worry 语义与当前 LTMS 边界，因此此次实现应重组现有知识，而不是发明新的运行时行为。

Agent Skills 的开放格式要求技能目录至少包含带 YAML frontmatter 的 `SKILL.md`。调研到的官方规范与 Anthropic authoring guidance 共同强调：`name` 与目录匹配；`description` 同时承担“做什么”和“何时触发”；正文使用面向行动的指令；通过渐进披露控制上下文体积；引用资料应保持浅层。此次内容规模较小，不需要新增 `references/`、`scripts/` 或 `assets/`。

## Goals / Non-Goals

**Goals:**

- 形成一个无需读取 README 即可指导 Agent 正确使用 Symbox 的自包含 Skill。
- 在 Skill 和 README 中统一“外化内在逻辑世界”的产品叙事与有限保证。
- 让 README 成为短小的 onboarding 页面，以 Skill 安装和 `uv tool` 安装为主要行动入口。
- 让示例忠实于现有 CLI 的真实签名、输出 envelope 和 v0.6 SVK 行为。

**Non-Goals:**

- 不修改 Python 运行时、命令树、JSON envelope、持久化格式或推理内核。
- 不把完整 v0.6 设计规范复制进 Skill，也不要求 Agent 学习 Fillmore 格语法术语。
- 不承诺 Symbox 能验证现实事实、完备求解任意逻辑或绝对消除幻觉。
- 不为每一种 Agent 客户端固定唯一安装路径或新增自动安装脚本。

## Decisions

### 1. 使用单文件标准 Skill，并为未来渐进披露留边界

创建 `skills/symbox/SKILL.md`，frontmatter 仅使用跨客户端最稳妥的标准字段，至少包含 `name: symbox` 和一段具体、可触发的 `description`。正文保持短于约 500 行，以祈使式步骤组织；本次不增加引用子文件。

选择理由：Skill 的核心是工作流与心智模型，单文件能避免 Agent 为掌握基础流程继续追踪文档。相比加入客户端专有 frontmatter 字段，标准字段具有更好的可移植性。若未来命令参考显著膨胀，再把详细资料移到 `references/`，并由 `SKILL.md` 直接链接一层。

### 2. Skill 以认知闭环而不是命令分类组织

正文按以下闭环编排：

1. 判断何时使用 Symbox：多步推理、跨对象约束、需要持续监视担忧或避免前后矛盾时触发。
2. 建立心智模型：对象是 Agent 当前相信或考虑的实体；Adj 是属性/约束补丁；Verb 是关系及论元约束；Worry 是元认知监视器；Symbox 是外部符号护栏。
3. 外化世界：创建对象、写入属性、绑定 Verb/Adj/Worry 检查。
4. 用 `now` 同步当下认知：以 SVK 的 Subject + Verb + 可变长论元包表达关系。
5. 读取 JSON 结果：区分成功、确认、验证错误和冲突；冲突时修正假设或建模，不绕过或编造状态。
6. 认知变化后继续同步，并在必要时查询或备份。

选择理由：完整命令字典不能告诉 Agent“为什么、何时、以何种顺序”使用工具；闭环流程更符合技能作为行为指导的职责。命令细节可通过 `sbox --help` 获取。

### 3. 把约束编码与 `now` 同步设为核心机制

Skill 明确要求 Agent 不要只在自然语言上下文中记住关键约束，而应将可执行检查写入 Verb 或 Adj 绑定：`check` 返回 `True` 表示当前候选正常，返回 `False` 表示冲突。Worry 复用同一极性表达持续关注条件。随后每次关键认知变化通过 `now` 或属性写入同步，使 Symbox 在已编码关系范围内检查前后不一致。

选择理由：这直接落实用户所述“让 Symbox 帮它看着别出幻觉”的机制。替代方案是把 Skill 写成 CLI 教程，但那会继续强化“项目 CLI 管理器”的错误定位。

### 4. README 采用四段式精简结构

README 主体组织为：

- 项目是什么：用一到两段说明认知外化、约束和同步闭环。
- 工作原理：用极短列表解释 Object、Adj、Verb、Worry、`now`。
- 安装 Agent Skill：复制完整 `skills/symbox` 目录到用户所用客户端支持的 skills 目录，提示具体位置以客户端文档为准。
- 安装 CLI 与最小上手：优先给出从当前仓库执行 `uv tool install .`（开发/本地），若包发布信息可由项目元数据确认，再补充相应来源安装；用 `sbox --version` 或 `sbox --help` 验证。

尾部保留一小段“边界”：只检查已外化且已编码的约束，不验证未提供的现实信息。详细 CLI、环境变量、存储和开发验证从 README 移除，Agent 使用流程归 Skill，命令精确语法归 `sbox --help`。

选择理由：README 是人类首次接触入口，不应与 Agent 的操作规程争夺职责。相比仅修改首段而保留其余参考内容，整体精简能持续防止定位回退。

### 5. 示例以当前实现为准，避免照抄设计稿中的过时调用

实现时应通过当前 CLI help 与现有测试核对安装后的入口、`bind` 参数顺序、`now` 语法和 JSON 输出，再编写 Skill/README 示例。设计规范用于语义与概念依据，现有可执行契约用于命令精确性。

选择理由：v0.6 设计规范中的草案示例与当前 README/实现可能在参数形态上已有差异。文档应避免创建一个语义正确但无法执行的 Agent 工作流。

## Risks / Trade-offs

- [“防幻觉”措辞被理解为绝对保证] → 在 Skill 与 README 同时陈述仅对已输入信息、已编码检查和当前内核可达传播负责。
- [不同 Agent 客户端的 Skill 安装路径不同] → 安装步骤描述“复制完整目录”，列举时标明客户端相关，并要求以客户端文档为准，不假定通用全局路径。
- [`uv tool install` 的发布源尚不明确] → 保证本地仓库安装路径可执行；只有在项目元数据或发布配置明确时才声称可按包名远程安装。
- [README 变短后高级用户难以发现详细参数] → 明确指向 Agent Skill、`sbox --help` 和设计规范，而不是在 README 重建参考手册。
- [Skill 内容重复设计规范并逐渐漂移] → Skill 只保留稳定的心智模型和操作闭环；实现时用测试/CLI help 校验命令，不复制内部架构细节。

## Migration Plan

1. 新增 Skill 文件，不影响现有 CLI 用户。
2. 用精简版本替换 README，同时确保旧 README 中仍属 onboarding 必需的信息有明确去向（Skill、CLI help 或设计规范）。
3. 使用 Agent Skills frontmatter 校验规则进行静态检查，并运行现有测试确认纯文档变更没有引入包或命令回归。
4. 验证 README 中的本地 `uv tool` 安装与最小命令能够执行。

回滚只需恢复旧 README 并删除 `skills/symbox`；无状态迁移、API 兼容或数据回滚要求。
