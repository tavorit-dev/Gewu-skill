"""视觉设计系统：配色、字号、间距、线宽的唯一事实源。

PRD 6.2 要求「颜色由图形语义决定，而不是每次随机分配」。所以这里定义的是
**语义色**（semantic role），不是「第几个区块用什么颜色」。渲染时由模板把
语义角色映射到具体色值，同一张图里同一角色永远同一个颜色。

新增模板时不要自己写死色值，从 ROLES 里取。
"""
from __future__ import annotations

# ── 语义配色 ──────────────────────────────────────────────────────────
# 背景用白/极浅灰；主文字近黑；强调色低饱和。技术感来自结构清晰，不是色彩丰富。
PALETTE = {
    "bg": "#ffffff",
    "bg_soft": "#f6f7f9",       # 分区底色，比背景深一档
    "ink": "#1f2328",           # 主文字、主描边
    "ink_muted": "#6b7280",     # 次级文字、注释、虚线
    "line": "#c9ced6",          # 常规连线
    "neutral": "#eef0f3",       # 常规组件填充
    "neutral_edge": "#b9c0c9",
    "primary": "#3b6fd4",       # 主要执行路径、当前焦点
    "primary_soft": "#e4ecfb",
    "accent": "#2f9e8f",        # 关键状态、目标、达成
    "accent_soft": "#dff2ef",
    "warn": "#d98324",          # 风险、阻塞、代价（克制使用）
    "warn_soft": "#fbeedd",
    "danger": "#c8483c",        # 异常、错误
    "danger_soft": "#fae5e2",
    "violet": "#7c5cbf",        # 第四种分类色（对比图第三、四项）
    "violet_soft": "#eee8f8",
}

# 语义角色 → 填充色 / 描边色 / 文字色
ROLES: dict[str, dict[str, str]] = {
    "neutral": {"fill": PALETTE["neutral"], "stroke": PALETTE["neutral_edge"], "text": PALETTE["ink"]},
    "primary": {"fill": PALETTE["primary_soft"], "stroke": PALETTE["primary"], "text": PALETTE["ink"]},
    "accent": {"fill": PALETTE["accent_soft"], "stroke": PALETTE["accent"], "text": PALETTE["ink"]},
    "warn": {"fill": PALETTE["warn_soft"], "stroke": PALETTE["warn"], "text": PALETTE["ink"]},
    "danger": {"fill": PALETTE["danger_soft"], "stroke": PALETTE["danger"], "text": PALETTE["ink"]},
    "violet": {"fill": PALETTE["violet_soft"], "stroke": PALETTE["violet"], "text": PALETTE["ink"]},
    "ghost": {"fill": PALETTE["bg"], "stroke": PALETTE["line"], "text": PALETTE["ink_muted"]},
}

# ── 字号阶梯（PRD 6.2 的五级视觉层次）─────────────────────────────────
FONT = {
    "title": 26,        # 图标题：一句话说明这张图解释什么
    "subtitle": 14,     # 副标题 / 边界说明
    "region": 15,       # 分区标题
    "node": 14,         # 节点主标签
    "node_sub": 11.5,   # 节点次级标签
    "label": 11.5,      # 连线标签、注释
    "conclusion": 13,   # 结论条
    "legend": 11.5,     # 图例
    "min": 11.0,        # 下限：低于此不再缩，改为拆图
}

FONT_STACK = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB',"
    "'Microsoft YaHei','Source Han Sans SC',sans-serif"
)
FONT_MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# ── 几何与间距 ────────────────────────────────────────────────────────
CANVAS = {"width": 1100, "margin": 32}
GAP = {
    "node_x": 56,       # 同层节点水平间距
    "node_y": 44,       # 层间垂直间距
    "region": 22,       # 分区之间
    "region_pad": 18,   # 分区内边距
    "region_head": 34,  # 分区标题占高
}
STROKE = {
    "region": 1.2,
    "node": 1.3,
    "edge": 1.6,
    "edge_strong": 2.0,
    "rule": 1.0,
}
RADIUS = {"region": 12, "node": 8, "pill": 999}
NODE = {
    "min_w": 96,
    "max_w": 300,
    "h": 46,            # 单行节点高
    "h_two_line": 62,   # 两行节点高
    "pad_x": 16,        # 节点内左右留白
    "pad_y": 12,
}
TEXT_PAD = 6            # 判定「装得下」时额外要求的余量，抵消宽度表 ±5% 误差
TITLE_BLOCK = 62        # 图标题区高度（标题 + 副标题）

# ── 线型语义 ──────────────────────────────────────────────────────────
# PRD 6.2：实线/虚线表达「确定 / 弱」的强弱语义，不是「主流程 / 回环」的分工。
DASH = {
    "solid": None,
    "weak": "6 5",          # 弱关联、可选路径、控制面
    "async": "2 4",         # 异步、非阻塞
    "data": "10 4",         # 数据面、批量
}

# 箭头尺寸
ARROW = {"w": 9, "h": 7}
