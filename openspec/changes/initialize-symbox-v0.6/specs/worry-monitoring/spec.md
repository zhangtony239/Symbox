## Purpose

定义 Worry 如何把对象值变化转换为命题健康状态并接入统一传播，使数值阈值冲突能与符号事实共同参与一致性检查。

## ADDED Requirements

### Requirement: Worry 健康极性
Worry 检查 MUST 使用 True 表示被监控条件正常、False 表示条件不满足并触发矛盾传播；系统 MUST 将该布尔值直接映射到对应健康节点而不得反转极性。

#### Scenario: 健康检查通过
- **WHEN** Worry 对当前对象值返回 True
- **THEN** 对应健康节点为 true，依赖该健康条件的关系可继续成立

#### Scenario: 健康检查失败
- **WHEN** Worry 对当前对象值返回 False
- **THEN** 对应健康节点为 false，并触发所有相关 justification 的重新传播

### Requirement: 值变化即时触发
被 Worry 监控的对象属性在成功提交前 SHALL 触发相关检查；系统 MUST 在同一属性事务中评估由检查变化导致的矛盾。

#### Scenario: 值跌破阈值
- **WHEN** 属性更新使一个先前为 True 的 Worry 返回 False
- **THEN** 系统在提交该属性命令前传播健康节点翻转及其冲突后果

#### Scenario: 值恢复正常
- **WHEN** 属性更新使一个先前为 False 的 Worry 返回 True
- **THEN** 系统重新激活健康节点并重新计算依赖事实

### Requirement: 稳定点兜底重评估
每轮传播结束前，系统 SHALL 对受影响对象的 Worry 执行兜底重评估，直到健康节点与对象值一致并达到稳定状态。

#### Scenario: 间接变化影响 Worry
- **WHEN** 一次命令通过派生效果间接改变 Worry 所依赖的对象值
- **THEN** 系统在事务提交前重评估该 Worry 并传播其最终状态

#### Scenario: 重评估不收敛
- **WHEN** Worry 与派生效果在配置的安全边界内无法达到稳定状态
- **THEN** 系统中止事务、返回诊断错误且恢复命令前状态

### Requirement: Worry 复用对象绑定机制
Worry SHALL 作为 meta 分类对象使用通用绑定生命周期，而不要求调用方使用专用的 Worry 绑定命令。

#### Scenario: 绑定 Worry 检查
- **WHEN** 调用方把符合检查约定的函数绑定到 Worry 对象
- **THEN** 系统注册其监控依赖，并在相关值变化时执行该检查

#### Scenario: 解除 Worry 绑定
- **WHEN** 调用方解除一个 Worry 检查绑定
- **THEN** 系统撤回该检查提供的健康 justification 并重新计算依赖事实
