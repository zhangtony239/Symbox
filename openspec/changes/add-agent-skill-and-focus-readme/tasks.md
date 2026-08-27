## 1. 核对可执行契约与安装方式

- [x] 1.1 从当前 CLI help、项目元数据和相关测试核对 `sbox` 入口、`bind`/`now` 精确语法、JSON 结果处理方式及可用的版本或帮助验证命令
- [x] 1.2 按用户要求在项目 venv 中核对 CLI 可调用性与版本/帮助输出；README 保留从仓库执行 `uv tool install .` 的本地安装方式，不声称本次已实际安装，且不展示缺乏发布依据的包名安装方式

## 2. 创建 Symbox Agent Skill

- [x] 2.1 创建 `skills/symbox/SKILL.md`，加入与目录匹配的标准 YAML frontmatter，并在 description 中覆盖 Skill 能力和具体触发场景
- [x] 2.2 编写 Symbox 心智模型，明确它用于外化 Agent 内在逻辑世界而非项目管理，并说明 Object、Verb、Adj、Worry 与有限推理保证
- [x] 2.3 编写约束建模和认知同步流程，指导 Agent 将检查关系写入 Verb/Adj、遵循 Worry 极性，并使用 `now` 的 SVK 可变长论元同步当下所想
- [x] 2.4 编写结果处理规则和可执行示例，覆盖成功、确认、验证失败及冲突；要求 Agent 修正假设或建模而不是绕过检查、伪造状态或把无冲突等同于现实真相

## 3. 精简项目 README

- [x] 3.1 重写 README 首屏定位与简短工作原理，突出“外化—编码约束—用 `now` 同步—持续监视矛盾”的认知闭环
- [x] 3.2 增加安装完整 `skills/symbox` 目录的客户端无关说明，并提示具体 skills 目标位置以用户所用 Agent 客户端文档为准
- [x] 3.3 增加本地 `uv tool` 安装、版本/帮助验证和最小上手示例；按用户要求仅在项目 venv 中实际执行验证
- [x] 3.4 从 README 主体移除完整命令树、持久化、embedding、backup 和开发验证细节，改为指向 Skill、`sbox --help` 与 v0.6 设计规范，并保留有限保证说明

## 4. 验证与一致性检查

- [ ] 4.1 校验 Skill frontmatter、目录命名、description 触发语义、正文渐进披露和所有内部引用
- [ ] 4.2 对照 v0.6 设计规范、agent-guidance 与 project-onboarding specs 审阅 Skill 和 README，确认未引入深层格术语、项目管理定位或绝对防幻觉承诺
- [ ] 4.3 执行 README 中的安装验证与最小示例，并运行现有自动化测试和严格 OpenSpec 校验，记录任何与本次纯文档变更无关的既有失败
