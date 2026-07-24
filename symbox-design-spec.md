# Symbox 设计规范 v0.2 — 语法驱动的符号推理沙盒

> **日期**: 2026-07-24
> **作者**: Tony（概念设计）/ Toni（整理）
> **状态**: 核心设计已拍板，JSON 接口 + 混动 Adj 方案确定
> **关联**: GitHub Issue #1（开题）, `symbox-heritage-research.md`（工具调研）

---

## 1. 核心哲学

Symbox 用**自然语言的语法范畴**（主-谓-形-标签）做知识表示的类型系统，Python OOP 做实现载体，ltms 式真值传播做推理引擎。

LLM 通过 **标准 JSON** 操作这些语法对象——不是自然语言，不是伪代码，是 LLM 最熟悉的结构化输出。系统自动维护逻辑一致性，幻觉在产生时就被拦截。

**设计原则**：语法范畴（主语/动词/Adj/tags）是**内部建模的本体论**，不是**输入格式**。LLM 面对的是简洁的 JSON API，底层引擎用主谓形标签组织知识——两层各归各位。

---

## 2. 对象类别

| 类别 | 定位 | 逻辑对应 | OOP 实现 |
|------|------|---------|---------|
| **主语类 (S)** | 可自定义注册的实体类型 | 个体常量 | 普通 Python class |
| **动词类 (V)** | 自带逻辑注册的谓词，调用时对 S 和 O 施加内部规则 | n 元谓词 + 公理 | class，实例化 = 断言一条关系 |
| **Adj 类** | 动词规则的"补丁包"，存储在主语内 | 一元谓词 | 主语的 attribute / mixin |
| **tags 类** | 对 Adj 的聚类，用于快速描述主语 | 类型（many-sorted logic 的 sort） | class-level 标签 |

**手动关系创建**: LLM 可直接 `Verb(subject, obj)` 实例化一条关系，等价于断言基元事实（ground fact）。

---

## 2.5 JSON 接口规范（LLM 的操作界面）

LLM 通过标准 JSON 操作 Symbox，每个操作是一个原子事务：

### 声明主语
```json
{"op": "declare", "type": "subject", "class": "Person", "id": "tony"}
{"op": "declare", "type": "subject", "class": "Device", "id": "laptop", "state": {"battery": 0.05}}
```

**状态覆写 = 重新声明**：第二次 `declare` 同一个 id，引擎 diff 出变化，沿 justification 链传播修正。

### 声明关系
```json
{"op": "relate", "verb": "Owns", "args": ["tony", "laptop"]}
```

### 挂载/更新 Adj（混动设计）

**方式 A — 显式 set（主）**：
```json
{"op": "patch", "target": "laptop", "set": {"Broken": false, "Fixed": true}}
```
原子完成反转 + 新增，无歧义，一轮搞定。LLM 知道当前状态时用这条。

**方式 B — embedding 反问（辅）**：
```json
{"op": "patch", "target": "laptop", "adj": "Fixed"}
```
引擎检测到 `Fixed` 与现有 `Broken` 反义，返回确认请求：
```json
{"status": "confirm_needed", "question": "是将 Broken 置为 false 的意思吗？", "target": "laptop", "conflict": "Broken", "proposed": "Fixed"}
```
LLM 确认后引擎执行反转。LLM 不确定当前状态时用这条，引擎兜底防幻觉。

### 声明 Worry
```json
{"op": "declare", "type": "worry", "watch": "laptop", "condition": "battery < 0.2", "as": "low_battery"}
```

### 上下文操作（假设层）
```json
{"op": "push_context", "label": "假设 laptop 没坏"}
{"op": "declare", "type": "subject", "class": "Device", "id": "laptop", "state": {"battery": 0.05, "status": "working"}}
{"op": "pop_context"}
```

### 提交校验
```json
{"op": "commit"}
```
将当前事务批次打包校验：一致则写入主图，矛盾则返回 `conflicts` 数组报错。

---

## 3. 超现实主语（注册范围不限于物理实体）

主语可以是抽象的、元认知的，用于在沙盒中建模逻辑判定：

### 3.1 Worry 对象 — 值域→符号域的桥

**问题**: ltms 只懂符号真值（`rain=true`），不懂值（`temperature=38.5`）。现实中大量矛盾发生在值域：`battery.level=0.05` ∧ `Executes(robot, task)=true` 在符号层完全自洽，值域里却矛盾。

**方案**: Worry 监控主语的值，将值条件编译成符号真值，接入传播网络。ltms 引擎一行不用改，感知范围扩展到值域。

```python
# 概念示意
w = Worry(watch=battery, condition=lambda b: b.level < 0.2)
# 当 battery.level 降到 0.2 以下，worry 节点翻转为 true，触发传播
```

### 3.2 Attention 对象 — 元认知上下文

建模当前注意力焦点，让系统能推理"如果我关注 X，相关后果是什么"。这让 Symbox 从被动知识库变成有自我模型的推理体，是元认知推理的入口。

### 3.3 类型隔离

主语 class 加 `kind` 标记，动词的 domain/range 校验 kind，防止无意义组合：

| kind | 示例 | 规则 |
|------|------|------|
| `physical` | Person, Apple | 普通动词可作用 |
| `abstract` | Property, Relation | 部分动词可作用 |
| `meta` | Worry, Attention | 普通动词不可作用 |

---

## 4. 设计决策

### 4.1 动词规则的触发时机

| 选项 | 机制 | 优点 | 缺点 |
|------|------|------|------|
| A | 实例化即检查（`Eats(person, apple)` 一创建就抛异常） | 即时反馈 | 只能抓单关系矛盾，跨关系矛盾漏掉 |
| **B（已拍板）** | 注册到全局引擎，统一传播调度 | 能发现跨关系矛盾，复用 ltms 传播算法 | 需要引擎基础设施 |

### 4.2 Adj 混动设计（已拍板）

Adj 是 dict，支持多属性共存，显式声明反转：

```python
laptop.adj = {
    "Broken": {"value": True, "since": "2026-07-24T10:00", "justification": [...]},
    "Fixed": {"value": False, "since": None, "justification": []},
    "Old": {"value": True, "since": "2026-07-24T09:00", "justification": [...]},
}
```

| 方式 | 场景 | 机制 |
|------|------|------|
| **显式 set（主）** | LLM 知道当前状态 | `{"set": {"Broken": false, "Fixed": true}}` 原子反转 |
| **embedding 反问（辅）** | LLM 不确定当前状态 | 引擎检测反义，返回确认请求，LLM 裁决 |

**混动价值**: 显式 set 保证效率，embedding 反问给 LLM 留出幻觉鲁棒性——当 LLM 对状态记忆模糊时，引擎主动提醒潜在冲突，防止不一致溜进主图。

**Adj patch 的两种语义**（保留）：
- **拦截型 (veto)**：直接阻止动词成立 → 矛盾（如 `Rotten` 阻止 `Eats`）
- **修饰型 (modify)**：动词成立但附加后果（如 `Eats(rotten_apple)` → `Sick(person)`）

### 4.3 tags 动态派生 vs 手动打标

| 方式 | 机制 | 场景 |
|------|------|------|
| **动态为主（已拍板）** | Adj 声明 `implies_tags=["food"]`，挂载时自动派生 | 推理自动性 |
| 手动兜底 | LLM 直接给主语打 tag | 灵活性、快速标注 |

### 4.4 Worry 的触发机制

| 选项 | 机制 | 优点 |
|------|------|------|
| **A（已拍板）** | Observer：值变化立即触发（主语的值走 `@property` setter hook） | 实时 |
| B | 每轮传播结束后全量重评估 | 兜底，保证边界情况不漏 |

**已定**: A 为主，B 兜底。

### 4.5 真值存在哪？（⭐ 地基问题）

ltms 的精髓：每个节点有 **true / false / unknown** 三态，justification 记录"它为什么为真"，撤回时沿 justification 链自动修正。

| 选项 | 机制 | 评价 |
|------|------|------|
| **A（已拍板）** | **引擎持有真值**：对象是"事实的句柄"，真值表 + justification 图住在引擎里。`del` 对象 → 引擎标记 retracted → 沿依赖链传播修正 | justification 链是跨对象的全局结构，集中管理才一致 |
| B | 对象持有真值：每个对象自带 truth 和 dependents，自己管理传播 | 状态分散，跨对象依赖链无法维护 |

**A 的本质**: 主语/动词/Adj 是**语法外壳**（LLM 的操作界面），引擎是**语义内核**（真值传播）。呼应"语言层 → 逻辑层"的整体直觉。

### 4.6 输入格式（已拍板）

| 选项 | 评价 |
|------|------|
| 自然语言解析 | ❌ 脱裤子放屁，LLM 不需要"组织语言" |
| **标准 JSON（已拍板）** | ✅ LLM 最熟悉的输出格式，function calling 原生支持 |

**三层结构**：
| 层 | 机制 | JSON 对应 |
|---|------|----------|
| Committed | 校验通过写入主图 | 普通 `declare`/`relate` |
| Hypothetical | 假设层操作 | `push_context` → 操作 → `pop_context` |
| Conflict | 校验失败报错 | 返回值带 `conflicts` 数组 |

**原子事务**: 每个 JSON 操作是一个原子事务，或 LLM 显式 `commit` 打包校验。

---

## 5. 学术血统（为什么这个设计不是拍脑袋）

| 传统 | 对应 | 年份 |
|------|------|------|
| 语义网络 (Semantic Networks) | 主语 + 关系 = 节点 + 边 | Quillian 1966 |
| 格语法 (Case Grammar) | 动词的论元角色约束 | Fillmore 1968 |
| FrameNet | 动词框架 + 角色填充 | 1990s- |
| Truth Maintenance System | 真值传播 + 信念修正 | Doyle 1979, de Kleer 1986 |
| Fluent (situation calculus) | Worry 监控值域变化 | McCarthy 1963 |
| 认知架构 (SOAR/ACT-R) | Attention 元认知 | 1980s- |

---

## 6. 架构预览（决策拍板后细化）

```
┌─────────────────────────────────────────┐
│           LLM (function calling)         │
│    create_subject / create_verb / ...    │
└──────────────────┬──────────────────────┘
                   │ 语法外壳 (OOP objects)
┌──────────────────▼──────────────────────┐
│           Symbox Engine                  │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Truth    │ │ Justifi- │ │ Contrad-│ │
│  │ Table    │ │ cation   │ │ iction  │ │
│  │ (t/f/u)  │ │ Graph    │ │ Detector│ │
│  └──────────┘ └──────────┘ └─────────┘ │
│  ┌──────────┐ ┌──────────┐             │
│  │ Worry    │ │ Belief   │             │
│  │ Monitor  │ │ Revision │             │
│  └──────────┘ └──────────┘             │
└─────────────────────────────────────────┘
         │ 可选后端
    ┌────┴────┐
    Z3    PySAT
```

---

## 7. 下一步

- [x] Tony 拍板核心设计决策（§4 全部已定）
- [ ] Tony 亲自 code Layer 0 核心引擎
- [ ] 画 draw.io 宏观架构图（Issue #1 任务①）
- [ ] 同步本文档到 GitHub Issue（给 nahanhhan 对齐）
- [ ] 读 ltms 源码，提取 TMS 算法模式（供引擎参考）

---

*v0.2 — 2026-07-24 by Toni，基于 Tony 的语法猜想 + JSON 接口 + 混动 Adj 方案整理*
