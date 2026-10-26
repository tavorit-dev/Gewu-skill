# tech-visual-explainer

把一段技术内容变成读者能看懂的视觉解释：判断该配什么图、写独立可读的图注、画手绘风解说动图，并接进静态博客文章里。

## 这是什么

一个 Claude Code skill。它固化的不是「怎么画图」（那是 `animated-sketch-diagram` 插件的事），而是**配图决策**和**落盘校验**：

- 什么内容值得配图、该配哪种图（流程/结构/对比/概念各有对应形态）
- 图注怎么写才有价值（读者会跳过图直接读图注）
- 图怎么接进 Hexo 文章（裸文件名、postAsset、资源目录）
- 怎么验证图真的生效了——`hexo g` 在产物完全错误时也 exit 0，**退出码不可信**

## 安装

本目录是唯一事实源，`~/.claude/skills/tech-visual-explainer` 是指向它的软链接：

```bash
ln -sfn ~/company/open-source/tech-visual-explainer ~/.claude/skills/tech-visual-explainer
```

依赖：

- `animated-sketch-diagram` 插件（画解说图）
- Hexo 8 环境（校验产物用），Node >= 20.19
- `ffmpeg` + Python `PIL`/`numpy`（动图程序化校验）

## 结构

```
SKILL.md                          # 主文件：工作流 + 症状速查表
references/cover-image.md         # 封面图选图原则
references/diagram-checklist.md   # 交付前自检清单
evals/evals.json                  # 评测用例（含隔离要求）
```

## 迭代

1. 直接改本目录的 `SKILL.md` 或 `references/`
2. 跑 `evals/evals.json` 的用例——注意 eval-0 必须在干净 worktree 里跑
3. 验证有效后提交

**不要改 `~/.claude/skills/tech-visual-explainer/` 下的文件**：那是软链接，绕过版本记录。

## 已知边界

**本环境 `Read` 打不开图片**（只返回 `[Image #N]` 占位符），`analyzeImage` 不可用。所以「抽帧回读自检」这一步做不到，只能做程序化校验（尺寸、墨色占比、动画是否在动），视觉终检必须交给用户。

SKILL.md 和 checklist 都明确写了这一点——**这是有意保留的**：一个不说清自己能力边界的 skill，会诱导 agent 编造「我已检查过图片」的结论。
