# Symbox v0.6

Symbox 是面向 LLM/Agent 的项目本地符号状态 CLI。它以规范 JSON 保存对象、属性、绑定、SVK 关系和真值依据，通过统一事务边界保证失败操作不污染当前状态，并使用项目隔离的 bare Git 仓库保存可恢复 backup。

## 环境与安装

- Python 3.12+
- Git（用于 backup）
- 推荐使用 `uv`

```bash
uv sync --dev
uv run sbox --version
```

所有正常命令向 stdout 输出一个 JSON envelope，包含 `status`、`data`、`diagnostics`、`conflicts` 和 `transaction_id`。验证、冲突与系统错误使用不同退出码。

可通过全局 `--root <project>` 显式指定项目作用域；省略时使用当前目录：

```bash
uv run sbox --root ./example create robot
```

## v0.6 CLI

```text
sbox create <name> [--category physical|abstract|meta]
sbox delete <name>
sbox bind <name> <qualified_function> -f <project-relative.py> [--verb]
sbox unbind <name>
sbox set <name> <key=JSON> [<key=JSON> ...]
sbox unset <name> <key> [<key> ...]
sbox now <subject> <verb> [args ...] [key=value ...]
sbox list objects|verbs|backups|<object-name>
sbox backup create <note>
sbox backup list
sbox backup delete <commit-id> [<commit-id> ...]
sbox backup rollback <commit-id>
```

## 对象、绑定与 SVK

对象名称在项目内唯一，分类为 `physical`、`abstract` 或 `meta`。只有通过 `bind --verb` 显式标记的对象能位于 `now` 的 Verb 槽位。

绑定函数来自项目内普通 Python 文件。Subject 必须是显式第一参数，后续参数使用 Python 原生签名、默认值和参数验证：

```python
def moves(subject, destination, speed=1):
    return subject == "robot" and bool(destination) and speed > 0
```

```bash
sbox create robot
sbox create moves --category abstract
sbox bind moves -f rules/checks.py --verb
sbox now robot moves dock speed=2
```

`now` 使用 SVK 变长关系：

- `sbox now door opens`：零个后置论元；
- `sbox now robot moves dock`：一个位置论元；
- `sbox now john gives mary book priority=1`：多个位置论元和具名参数。

关系身份采用 `SVK:<subject>:<verb>:<sha256>`。具名参数输入顺序不影响身份；Subject、Verb、任一位置参数或有效具名参数不同都会生成不同身份。

## Worry 极性与监控

Worry 是 `meta` 对象，复用普通对象的 bind/unbind 生命周期，把值域变化桥接为统一真值节点。检查函数极性固定为：

- `True`：状态正常，健康节点为 `true`；
- `False`：条件不满足，健康节点为 `false`，并触发相关 justification 的重新传播。

Worry 依赖使用规范节点键，例如 `Adj:robot:battery` 或 `Worry:battery-ok`。属性候选更新会即时检查相关 Worry；传播尾部继续重评估间接受影响的 Worry，直到达到固定点。重复状态或超过最大迭代边界会中止并回滚整个事务。

## 属性相似度与 embedding 配置

Embedding 仅用于新属性 key 的相似度提示，不是真值来源。配置来自进程环境：

| 环境变量 | 含义 | 默认值 |
|---|---|---|
| `SBOX_EMBEDDING_BASE_URL` | OpenAI-compatible endpoint | 未配置 |
| `SBOX_EMBEDDING_MODEL` | embedding 模型 | 未配置 |
| `SBOX_EMBEDDING_API_KEY` | 可选凭据 | 未配置 |
| `SBOX_SIMILARITY_THRESHOLD` | 严格 `score > threshold` 的确认阈值 | `0.85` |
| `SBOX_EMBEDDING_TIMEOUT_SECONDS` | 请求超时秒数 | `10` |

当 endpoint/model 未配置，或服务超时、失败时，系统降级为精确字符串名称判定并返回 degraded diagnostics，不阻断普通属性写入。API key 与其他环境凭据不会写入状态、backup tree 或 backup 列表。

## 项目状态与 backup

每个项目的运行数据均位于项目自己的 `.sbox/`：

```text
.sbox/
├── state.json      # 带 schema version、规范排序的当前状态
├── state.lock      # 状态写锁
├── backups/        # 独立 bare Git 仓库
└── backups.lock    # backup/ref 操作锁
```

状态写入使用同目录临时文件、flush/fsync 和原子 replace。每个成功写命令只增加一次 revision；解析、绑定、传播、持久化或 Git 失败时，已提交状态保持不变。

`backup create` 将规范 `state.json` 写为 Git tree/commit，并返回完整 commit ID。`backup list` 按创建时间从新到旧、再按 ID 确定排序。批量 `backup delete` 在更新任何 ref 前验证全部 ID；`backup rollback` 先完整读取并验证快照，再通过普通状态仓储原子恢复。

## 当前推理边界

v0.6 使用可替换的 `TruthKernel` 端口和当前 LTMS adapter：

- 支持 `true`、`false`、`unknown` 三值状态；
- 支持 assumption、justification、撤回和依据解释；
- 对已注册 Horn 风格规则产生的结论保持健全；
- 检测当前传播图可达的矛盾，并在提交前回滚候选事务。

当前层不声称完备处理任意非 Horn 全局约束、不可达深层矛盾、多上下文 ATMS 假设组合、最小撤回建议或 Z3 全局求解。无法由当前规则推出的结论保持 `unknown`，不得伪造冲突依据。

## 开发验证

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
openspec validate --change initialize-symbox-v0.6 --strict
```
