# 格物 Gewu

> **致知在格物，物格而后知至。**
> ——《礼记·大学》

从技术文章、文档或一段描述中识别**真正值得可视化的技术原理**，提取可验证的解释模型（VEM），渲染成准确、克制的 SVG 原理解释图，并验证图文一致性。

## 命名由来

「格物」取自《礼记·大学》的「致知在格物，物格而后知至」。

格物，意味着探究事物、求索其理；致知，则指向认知的深化与完善。这与本 skill 的设计理念相契合：**面对技术文章，不急于绘图，而是先理解内容、探究原理、梳理关系**，再将复杂的技术知识转化为准确、清晰的视觉表达。

**先格物，后成图；先求真，再求美。**

## 这是什么

一个 Claude Code skill，定位是**技术知识视觉解释引擎**，不是图片生成器。

它固化的核心能力不是「怎么画图」（那已经工程化在 `scripts/` 里），而是三件事：

1. **知识发现** —— 一篇文章里哪些原理最值得画？哪些该合并、哪些该拆？为什么值得画？
2. **技术解释** —— 机制如何工作、哪些组件参与、什么条件不能忽略、哪些结论有依据
3. **视觉表达** —— 选哪种图形、如何组织信息与视觉层次、如何生成并**验证**最终 SVG

三者通过 **VEM**（Visual Explanation Model）连接：VEM 是原理与渲染之间的结构化中间表示，落盘后可复用——换风格、调模板、升级渲染器时不必重新分析原文。

**最重要的设计判断**：成功标准不是「生成了一张漂亮的图」，而是「从一篇文章中找到了真正值得解释的机制，并用一张准确、清晰的图让读者更容易理解它」。

## 工作流：七阶段

```
Stage 1  解析内容，建立知识上下文     → 语义单元
Stage 2  发现可视化候选，评分筛选     → 候选清单（含筛选理由）
Stage 3  提取原理，建立 VEM 模型      → models/*.yaml
Stage 4  选择视觉表达形式             → visual_type
Stage 5  渲染 SVG                     → diagrams/*.svg
Stage 6  四层验证                     → report/validation.md
Stage 7  交付与迭代
```

**前四阶段解决「画什么、为什么画」，第五阶段才解决「怎么画出来」。** 混在一起做，会直接进入绘图状态，产出精美但不准确的图。

## 安装

本目录是唯一事实源，`~/.claude/skills/gewu` 是指向它的软链接：

```bash
ln -sfn ~/company/open-source/Gewu-skill ~/.claude/skills/gewu
```

### 依赖

**零第三方依赖即可渲染**——渲染器只用 Python 标准库（文字测量用内置字符宽度表，不需要 fontTools 或字体文件）。

| 依赖 | 用途 | 缺失时 |
|---|---|---|
| Python 3.9+ | 渲染与校验 | 必需 |
| PyYAML | 读 `.yaml` 格式的 VEM | 可改用 `.json` |
| Chrome / Chromium | `--png` 导出与像素校验 | 只能交付 SVG |
| `PIL` + `numpy` | 像素校验 | 跳过，但必须说明未验 |
| `tesseract` | 确认英文标签渲染出来了 | 跳过（**无中文包，中文必然乱码**） |
| `ffmpeg` | GIF 动效校验 | 跳过，但必须说明未验 |
| Hexo 8（Node >= 20.19） | 宿主是 Hexo 时校验产物 | 无法验证图片是否真的解析 |

## 用法

```bash
# 列出可用模板
python3 scripts/render.py --list

# 打印 VEM 字段说明
python3 scripts/render.py --schema

# 渲染 + 校验（有 error 时退出码 1）
python3 scripts/render.py templates/redis-rehash.yaml -o out.svg --check

# 渲染 + 导出 PNG（2x）+ 像素校验
python3 scripts/render.py templates/redis-rehash.yaml -o out.svg --png out.png
python3 scripts/vis_check.py out.png --expect "rehashidx"

# 回归测试（改渲染器后必跑）
python3 tests/test_render.py
```

## 结构

```
SKILL.md                              主文件：七阶段工作流 + 症状速查表
references/
    candidate-selection.md            候选发现、评分模型、图组规划
    visual-model-schema.md            VEM 字段规范（写图前必读）
    visual-design-system.md           配色、字号、间距、线型语义
    quality-rules.md                  四层验证与能力边界
    cover-image.md                    封面图选图原则
    diagram-checklist.md              交付前自检清单
scripts/
    render.py                         CLI：渲染 + 校验 + 导出 PNG
    vis_check.py                      渲染后像素校验
    gewu/textmetrics.py               文字测量（内置宽度表，零依赖）
    gewu/tokens.py                    设计系统（改配色改这里）
    gewu/layout.py                    自动布局原语（节点尺寸/锚点/避让）
    gewu/templates.py                 七种图形模板
    gewu/validate.py                  SVG 结构与几何校验
templates/                            可复制的 VEM 示例
tests/test_render.py                  回归测试
evals/evals.json                      评测用例（含隔离要求）
```

## 七种图形模板

| visual_type | 核心表达 | 典型用途 |
|---|---|---|
| `mechanism` | 组件 + 作用关系 | 缓存、GC、负载均衡 |
| `flow` | 步骤 + 分支 | 请求处理、编译流程、迁移步骤 |
| `sequence` | 参与者 + 时间顺序 | RPC、网络协议、并发交互 |
| `state` | 状态 + 迁移条件 | TCP 状态机、任务生命周期 |
| `structure` | 组件 + 组织关系 | 哈希表、内存布局、系统架构 |
| `comparison` | 同构对照 + 差异高亮 | 同步 vs 异步、选型对比 |
| `causality` | 原因 → 机制 → 结果 | 性能瓶颈、死锁、缓存失效 |

模板只声明**语义关系**，坐标由布局引擎算出来——这是「文字一定装得下、箭头一定贴边、节点一定不重叠」的程序保证。

## 迭代

1. 改本目录的 `SKILL.md` / `references/` / `scripts/`
2. 改渲染器必跑 `python3 tests/test_render.py`
3. 跑 `evals/evals.json` 的用例——注意 eval-0 必须在干净 worktree 里跑
4. 验证有效后提交

**不要改 `~/.claude/skills/gewu/` 下的文件**：那是软链接，绕过版本记录。

## 已知边界

**本环境 `Read` 打不开图片**（只返回 `[Image #N]` 占位符），`analyzeImage` 工具不存在，降采样也解决不了。所以：

- **能验**：XML 合法性、元素越界、文字是否超出节点框、节点是否重叠、尺寸、墨色分布、英文标签 OCR、GIF 是否在动
- **验不了**：文字是否糊、视觉重叠、**中文是否正确渲染**、**技术语义是否正确**

本机 `tesseract` 只装了 `eng` 包，中文必然识别成乱码，所以 OCR 只能确认「文字渲染出来了」。

SKILL.md 和 `quality-rules.md` 都明确写了这一点——**这是有意保留的**：一个不说清自己能力边界的 skill，会诱导 agent 编造「我已检查过图片」的结论。交付时明确区分已验/未验，把视觉终检交给用户。
