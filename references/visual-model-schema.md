# VEM：视觉解释模型

VEM（Visual Explanation Model）是**技术原理**与**图形渲染**之间的中间表示。

它存在的理由：原理模型和图形布局是两个不同的问题。同一个机制可以用数据迁移图讲，
也可以用时间序列图讲——技术语义不变，变的是视觉结构。把两者混在一起，
模型会直接跳进绘图状态，产出「精美但知识提取不准确」的图。

**写 VEM 的顺序永远是：先把机制想清楚，再决定画成什么形状。**

## 公共字段

```yaml
title: Redis 渐进式 Rehash：迁移工作如何被摊开   # 一句话说明这张图解释什么
visual_type: flow                              # 七选一，见下
question: 为什么扩容时不一次性把 ht[0] 全部搬到 ht[1]？   # 这张图回答的问题
core_message: >                                # 一句话结论（读者看完应得到的判断）
  把迁移摊到每次读写操作上，单次开销从 O(n) 降到 O(1)，
  代价是迁移期间两表并存。

scope:                                         # 版本相关的技术必须写
  system: Redis
  version: "7.x"

evidence:                                      # 每条关键关系的原文依据
  - source_ref: "原文 §字典扩容"
    supports: "迁移工作分散到多次操作中"

unknowns:                                      # 原文没说明、图里也不该编的部分
  - "每步具体搬运多少桶"

conclusion: 关键不是"分批"，而是迁移被绑定在正常操作路径上。  # 图下方的结论条
boundary: 图中步数为示意；实际触发条件随版本变化。           # 图下方的边界说明
```

### 三类信息必须分清

| 类型 | 能否进图 | 怎么标 |
|---|---|---|
| 原文明确陈述的事实 | 可以 | 直接写，`evidence` 指向原文 |
| 有依据的解释与推论 | 可以 | `evidence` 里写清推理依据 |
| 原文没有说明的信息 | **不可以** | 写进 `unknowns`，或直接留白 |

**不得为了让图看起来完整而补造细节。** 原文缺信息时，宁可图上少一个节点，
也不要把猜测画成事实。

## 七种 visual_type 与专属字段

### flow —— 步骤 + 分支

一个操作按什么顺序执行。适合：请求处理、编译流程、迁移步骤。

```yaml
visual_type: flow
steps:                        # 主路径，横向排布，按数组顺序连成链
  - {id: s1, label: 触发扩容, sub: 负载因子超阈值, role: neutral}
  - {id: s2, label: 分配 ht[1], sub: 容量翻倍, role: primary}
branches:                     # 主链之外的连线：分支、回环、异常路径
  - {from: s4, to: s3, label: 未搬完，循环推进, detour: below, role: primary}
  - {from: s4, to: s5, label: rehashidx == -1, style: weak, role: line}
```

- `detour: below|above` 只在自环（from == to）时需要。
- `style: weak` 表示「可能发生」而非「必然发生」——**不要把可能画成必然**。

### mechanism —— 组件 + 作用关系

某个功能究竟如何工作。适合：缓存、GC、负载均衡。

```yaml
visual_type: mechanism
core: {id: cache, label: 缓存层, sub: 内存 KV}     # 被解释的机制，居中
actors:                                            # 参与的组件
  - {id: app, label: 应用, side: left}
  - {id: db,  label: 数据库, sub: 持久化, side: right}
relations:
  - {from: app, to: cache, label: 读, role: primary}
  - {from: cache, to: db, label: 未命中, style: weak, role: warn}
```

`side` 取 `left|right|top|bottom`；不写则自动左右交替。

### structure —— 组件 + 组织关系

数据/组件如何组织与存储。适合：哈希表布局、内存结构、系统架构。

```yaml
visual_type: structure
regions:                       # 每个 region 是一块分区（背景板 + 标题）
  - id: r1
    label: 桶数组
    sub: 连续内存
    cols: 3                    # 分区内节点排成几列
    nodes:
      - {id: b0, label: bucket[0]}
      - {id: b1, label: bucket[1]}
links:
  - {from: b1, to: n1, label: next, role: primary}
```

**分区要有意义**：分区边界本身就是信息（「这两组属于不同层次」）。

### comparison —— 同构对照 + 差异高亮

两种方案的差异及其代价。适合：同步 vs 异步、选型对比。

```yaml
visual_type: comparison
options:                       # 2~3 个方案，横向分列
  - {id: o1, label: 同步写, sub: 写完才返回}
  - {id: o2, label: 异步写, sub: 入队即返回, role: accent}
dimensions:                    # 逐维度对照，同一行是同一维度
  - {label: 延迟, values: ["高（等落盘）", "低（只入队）"], diff: true}
  - {label: 一致性, values: [强, 最终一致], diff: true}
  - {label: 实现复杂度, values: [低, 高（需补偿）]}
verdict: {text: 选择依据是能否接受最终一致，而不是单纯比快慢。}
```

- `values` 的长度必须与 `options` 一致，顺序一一对应。
- `diff: true` 的行会高亮——**只标真正有差异的维度**，全标等于没标。

### sequence —— 参与者 + 时间顺序

多个参与者之间的消息往来。适合：RPC、网络协议、并发交互。

```yaml
visual_type: sequence
actors:
  - {id: c, label: 客户端}
  - {id: s, label: 服务端}
messages:
  - {from: c, to: s, label: 请求}
  - {from: s, to: c, label: 响应, style: weak, note: 异步返回}
activations:                   # 可选：某参与者正在处理的时间段
  - {actor: s, from: 0, to: 3} # from/to 是 messages 的下标
```

**时序图最大的风险是把并发画成串行。** 如果两个消息没有确定的先后关系，
必须在图注或 `boundary` 里说明，不能靠箭头的上下位置暗示必然顺序。

### state —— 状态 + 迁移条件

系统在不同状态下如何变化。适合：TCP 状态机、任务生命周期。

```yaml
visual_type: state
states:
  - {id: st1, label: ESTABLISHED, initial: true}
  - {id: st3, label: TIME_WAIT, role: warn}
  - {id: st4, label: CLOSED, final: true}
transitions:
  - {from: st1, to: st2, trigger: 主动关闭}
```

`trigger` 是**迁移条件**，不是动作描述——写「收到 ACK」而不是「处理 ACK」。

### causality —— 原因 → 机制 → 结果

为什么某个现象会发生。适合：性能瓶颈、死锁形成、缓存失效。

```yaml
visual_type: causality
causes:    [{id: c1, label: 缓存命中率低, sub: 热点分散}]
mechanism: [{id: m1, label: 每次请求先查缓存, sub: 多一次网络往返}]
effects:   [{id: e1, label: 延迟上升, role: warn}]
links:
  - {from: c1, to: m1}
  - {from: m1, to: m2}
  - {from: m2, to: e1, style: weak}    # weak = 可能，不是必然
```

因果图是三栏布局，从左到右是时间/逻辑顺序。

## 通用字段速查

| 字段 | 取值 | 含义 |
|---|---|---|
| `role` | `neutral` `primary` `accent` `warn` `danger` `violet` `ghost` | 语义色。**同一张图里同一 role 永远是同一个颜色** |
| `style` | `solid` `weak` `async` `data` | 线型。表达「确定/弱」「同步/异步」，不是装饰 |
| `shape` | `rect` `pill` `diamond` `note` `cylinder` | 节点形状。`diamond` 表判断，`note` 表依据/未知项 |
| `arrow` | `end` `both` `none` | 箭头方向 |

### role 的用法约定

`role` 不是「这个节点重要所以标红」。它表达的是**语义类别**，一张图内必须自洽：

- `primary` —— 当前讨论的主路径、被解释的核心
- `accent` —— 目标状态、达成、正常结果
- `warn` —— 风险、阻塞、代价、需要注意的中间态
- `danger` —— 异常、错误、失败路径
- `neutral` —— 其余

**如果图中用颜色表达了状态差异，就必须有图例。** 见 `visual-design-system.md`。

## 自检：VEM 写完先问四个问题

1. **`question` 明确吗？** 读者能知道这张图试图解释什么吗？
2. **`core_message` 是判断吗？** 「Redis 使用渐进式 rehash」不是判断，
   「迁移被绑定在正常操作路径上，所以不会单独阻塞请求」才是。
3. **每条关键关系都有 `evidence` 吗？** 没有依据的关系要么补依据，要么删掉。
4. **`unknowns` 写了吗？** 如果一项都没有，很可能是把不知道的东西当成了知道。
