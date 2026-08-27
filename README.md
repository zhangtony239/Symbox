# Symbox v0.6

Symbox 是 LLM/Agent 的外部符号认知护栏。它帮助 Agent 把当前相信、考虑或担忧的对象与关系外化出来，把重要约束编码成可执行检查，再用 `now` 同步“此刻所想”，从而在多步行动中持续发现前后矛盾。

Symbox 管理的是 Agent 对世界的符号化认知，不是项目任务、依赖或脚手架，也不是外部事实来源。

## 工作原理

1. **外化认知**：用 Object 表达当前涉及的实体、概念和元认知关注点。
2. **编码约束**：用 Adj 表达对象属性及约束补丁，用 Verb 表达关系及其论元检查。
3. **同步当下**：用 `now` 以 Subject + Verb + 可变长论元包提交 Agent 当前的关系判断。
4. **持续监视**：用 Worry 关注可能使当前认知失效的条件；所有检查均遵循 `True` 表示正常、`False` 表示冲突。
5. **修正模型**：遇到验证错误或冲突时检查假设、依据和建模，而不是绕过检查或虚构成功状态。

## 安装 Agent Skill

仓库中的 [`skills/symbox`](skills/symbox) 是完整的 Symbox Agent Skill。复制或安装整个 `symbox` 目录，而不是只复制其中的 `SKILL.md`：

```text
skills/
└── symbox/
    └── SKILL.md
```

将该目录放入你所用 Agent 客户端支持的 skills 位置。不同客户端和安装范围可能使用不同目标目录，请以该客户端的 Agent Skills 文档为准，不要假定存在适用于所有客户端的单一全局路径。

Skill 包含何时使用 Symbox、如何建模约束、如何同步认知以及如何处理结构化结果的完整 Agent 工作流。

## 安装 CLI

需要 Python 3.12+ 和 [`uv`](https://docs.astral.sh/uv/)。克隆仓库后，在仓库根目录从本地源码安装命令行工具：

```bash
uv tool install .
```

验证命令是否可调用：

```bash
sbox --version
sbox --help
```

`sbox --version` 返回 JSON，其中 `status` 应为 `success`，`data.version` 应为当前版本。本仓库元数据没有提供足以确认已发布包来源的信息，因此这里只展示从已克隆仓库安装，不提供未经确认的包名安装命令。

开发环境中也可不安装工具，直接使用项目虚拟环境运行等价命令：

```bash
uv sync
uv run sbox --version
```

## 最小上手

下面的例子外化一个 `robot`，为 `moves` 关系绑定检查，然后同步一条带位置论元和具名参数的当前认知。

先创建项目内的 `rules/checks.py`：

```python
def moves(subject, destination, speed=1):
    return subject == "robot" and bool(destination) and speed > 0
```

在同一项目根目录执行：

```bash
sbox create robot
sbox create moves --category abstract
sbox bind moves -f rules/checks.py --verb
sbox set robot 'mode="ready"'
sbox now robot moves dock speed=2
sbox list robot
```

每条正常命令都向标准输出写入 JSON envelope。根据 `status` 区分 `success`、`confirm_needed`、`error` 和 `conflict`，并检查 `data`、`diagnostics` 与 `conflicts`；不要只根据命令意图假定写入成功。确切命令与参数以安装版本的 `sbox --help` 和子命令帮助为准。

## 能力边界与详细资料

Symbox 只能依据 Agent 已外化的事实、关系、检查约束和当前推理内核可达的传播路径发现冲突。未报告冲突仅表示“在已编码约束与当前推理边界内未发现冲突”，不表示外部事实已获验证，也不保证完备证明任意逻辑或绝对消除幻觉。

- Agent 使用流程与结果处理：[`skills/symbox/SKILL.md`](skills/symbox/SKILL.md)
- 当前安装版本的命令契约：`sbox --help`
- SVK 与真值维护设计边界：[`symbox-design-spec-v0.6.md`](symbox-design-spec-v0.6.md)
