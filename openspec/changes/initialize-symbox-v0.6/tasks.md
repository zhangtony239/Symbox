## 1. 工程骨架与契约测试

- [x] 1.1 配置 Python 包目录、`sbox` 命令入口、开发/测试依赖与基础 lint/type/test 命令
- [x] 1.2 建立 `cli`、`application`、`domain`、`kernel`、`persistence`、`integrations` 分层及依赖方向测试
- [x] 1.3 将七个 capability spec 的场景映射为可追踪的 pytest 契约测试骨架
- [x] 1.4 定义统一 JSON result envelope、错误分类、退出码并添加 CLI golden tests

## 2. 领域模型与确定性标识

- [x] 2.1 实现 Subject、Verb、Adj、tag、Worry、BindingRef、SVK 领域模型及输入不变量
- [x] 2.2 实现 `physical`、`abstract`、`meta` 分类和 Verb domain/range 类型校验
- [x] 2.3 实现 NodeKey codec 的转义、解析和 round-trip 测试
- [x] 2.4 实现规范 JSON value codec 与 SVK SHA-256 身份生成，并覆盖参数顺序、默认值和碰撞测试
- [x] 2.5 实现显式/派生/assumption 来源模型及 Adj、tag 多来源撤回规则

## 3. 状态仓储与事务边界

- [x] 3.1 定义带 schema version 的 `.sbox/state.json` 格式和规范序列化/反序列化
- [x] 3.2 实现项目作用域发现、状态加载、损坏/未知版本拒绝和凭据排除测试
- [x] 3.3 实现临时文件、flush/fsync、原子 replace 的状态写入
- [x] 3.4 实现候选状态事务协调器，保证任一阶段失败时领域状态与磁盘状态均不变
- [x] 3.5 添加并发写锁和事务冲突测试

## 4. TruthKernel 与 LTMS 适配

- [x] 4.1 定义 TruthKernel 端口、三值枚举、节点/assumption/justification/解释数据结构
- [x] 4.2 实现测试用 in-memory fake kernel 并完成端口 contract tests
- [x] 4.3 调研并实现 `ltms` adapter 的节点注册、justification、撤回和传播映射
- [x] 4.4 实现候选 kernel clone；若库不支持安全 clone，则实现从领域快照确定性重建
- [x] 4.5 实现 justification 链解释与传播可达冲突报告
- [x] 4.6 添加跨对象/跨关系传播、撤回修正、sound 边界和原子冲突测试

## 5. 对象生命周期与动态绑定

- [x] 5.1 实现 create/delete 应用命令、唯一名称校验及删除后的事实撤回传播
- [x] 5.2 实现项目相对 Python 源文件与限定函数名的安全加载和签名检查
- [x] 5.3 实现 bind/unbind、Verb 标记、源码摘要持久化和加载时再验证
- [x] 5.4 实现受控 mutation context，确保 check 异常或候选效果失败可回滚
- [x] 5.5 添加重复对象、无效绑定、非 Verb 动词位、分类隔离和解除绑定测试

## 6. 属性、相似度与 tag 派生

- [x] 6.1 实现 set/unset 的批量解析、原子更新、属性来源及 justification 同步
- [x] 6.2 定义 embedding provider 端口和环境配置加载，确保 API key 不持久化
- [x] 6.3 实现 OpenAI-compatible embedding provider、超时、余弦相似度与可选缓存
- [x] 6.4 实现严格 `score > SIMILARITY_THRESHOLD` 的 `confirm_needed` envelope 和 `--force` 重试语义
- [x] 6.5 实现未配置/调用失败时精确名称降级及 degraded diagnostics
- [x] 6.6 实现 `implies_tags` 自动派生、多来源撤回和同名显式 tag 保留
- [x] 6.7 添加批量部分失败、阈值边界、降级、强制确认和 tag 来源测试

## 7. SVK now 关系断言

- [x] 7.1 实现 `now` token parser，区分 Subject、Verb、位置论元和 `key=value` 论元
- [x] 7.2 使用 Python signature 将 Subject 绑定为显式第一参数，并解析必需参数、默认值、重复参数和未知参数
- [x] 7.3 实现 Verb True=通过/False=冲突的检查流程及结构化诊断
- [x] 7.4 将通过的 SVK 注册为粗粒度真值节点并接入 Adj veto/modify 与统一传播
- [x] 7.5 添加零后置论元、多个位置论元、混合参数、顺序等价和参数差异身份测试
- [x] 7.6 添加端到端测试确认只暴露 `now`，不形成 `svo` 兼容面

## 8. Worry ECA 监控

- [x] 8.1 实现 Worry meta 对象、监控依赖注册及通用 bind/unbind 生命周期
- [x] 8.2 实现属性候选更新时即时检查，并将 True/False 直接映射到健康节点
- [x] 8.3 实现传播尾部对受影响 Worry 的固定点重评估
- [ ] 8.4 实现状态签名、最大迭代边界和不收敛事务回滚诊断
- [ ] 8.5 添加阈值跌破、恢复正常、间接值变化、解除绑定和循环测试

## 9. 查询接口

- [ ] 9.1 实现 `list objects` 的确定排序和对象分类/Verb 摘要
- [ ] 9.2 实现 `list verbs` 与绑定摘要过滤
- [ ] 9.3 实现 `list <object>` 的 Adj/tag 来源、绑定、关系、真值与 justification 摘要
- [ ] 9.4 实现未知对象错误及空集合成功语义
- [ ] 9.5 添加查询只读性测试，验证重复查询不写磁盘、不执行有副作用 callable

## 10. Git Backup 管理

- [ ] 10.1 实现 `.sbox/backups/` bare Git 仓库初始化、项目隔离和锁
- [ ] 10.2 实现 backup create，把规范状态写为 tree/commit 并返回稳定 commit id
- [ ] 10.3 实现 backup log 的 note、时间、id 确定排序和 list 入口集成
- [ ] 10.4 实现受管理 refs 与先全量验证后更新的原子批量 delete
- [ ] 10.5 实现 rollback 的临时读取、完整状态验证和事务式原子恢复
- [ ] 10.6 添加首次创建、跨项目隔离、删除含未知 id、损坏快照、并发 ref 与凭据排除测试

## 11. 集成验证与项目文档

- [ ] 11.1 为 create/delete/bind/unbind/set/unset/now/list/backup 全命令树添加端到端 subprocess 测试
- [ ] 11.2 添加故障注入测试，覆盖解析、binding、kernel、embedding、持久化和 Git 各阶段失败
- [ ] 11.3 验证每个写命令成功只提交一次、失败保持内存与磁盘状态不变
- [ ] 11.4 更新 README，记录 v0.6 CLI、SVK 示例、Worry 极性、配置、状态目录和当前推理边界
- [ ] 11.5 运行 formatter、linter、type checker、完整测试与 OpenSpec strict validation，并修复全部问题
