"""画布与自动布局原语。

这里是「不依赖模型手算坐标」的落点。模板只声明**语义关系**
（谁在谁右边、谁连谁、哪个是重点），坐标、尺寸、锚点由本模块算出来。

布局分两步：
  1. 节点自身尺寸 —— 由文字测量决定（measure_node），保证标签一定装得下。
  2. 节点间位置   —— 由行/列排布决定（row / column / grid），保证不重叠、不越界。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import textmetrics as tm
from .tokens import CANVAS, GAP, NODE, PALETTE, RADIUS, STROKE, TEXT_PAD, TITLE_BLOCK, FONT


# ── 图元 ──────────────────────────────────────────────────────────────
@dataclass
class Node:
    """一个节点（矩形卡片）。坐标与尺寸在布局阶段被赋值。"""

    id: str
    label: str
    sub: str | None = None
    role: str = "neutral"
    shape: str = "rect"          # rect | pill | diamond | note | cylinder
    icon: str | None = None
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    # 布局提示：同层内的相对权重（用于按内容宽度分配空间）
    grow: float = 1.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def anchors(self) -> dict[str, tuple[float, float]]:
        """八个连接锚点，箭头据此贴边而不扎进卡片。"""
        return {
            "l": (self.x, self.cy),
            "r": (self.x + self.w, self.cy),
            "t": (self.cx, self.y),
            "b": (self.cx, self.y + self.h),
            "tl": (self.x, self.y),
            "tr": (self.x + self.w, self.y),
            "bl": (self.x, self.y + self.h),
            "br": (self.x + self.w, self.y + self.h),
        }


@dataclass
class Region:
    """一个分区（背景板 + 标题）。用于给节点分组，形成「有意义的空间分组」。"""

    id: str
    label: str
    sub: str | None = None
    role: str = "neutral"
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


@dataclass
class Edge:
    """一条连线。source/target 是节点 id 或 (节点 id, 锚点) 元组。"""

    source: str | tuple[str, str]
    target: str | tuple[str, str]
    label: str | None = None
    style: str = "solid"          # 对应 tokens.DASH 的键
    role: str = "line"            # line | primary | accent | warn | muted
    arrow: str = "end"            # end | both | none
    waypoints: list[tuple[float, float]] = field(default_factory=list)
    # 自环/回环：绕行方向（"above" | "below"），None 表示自动
    detour: str | None = None
    offset: float = 0.0           # 平行连线之间的偏移，避免重叠
    _path: str = ""

    @property
    def path(self) -> str:
        return self._path


@dataclass
class Annotation:
    """图上的辅助文字：结论条、边界说明、图例项。"""

    text: str
    kind: str = "note"            # note | conclusion | boundary | legend
    x: float = 0.0
    y: float = 0.0
    role: str = "muted"


# ── 文字测量驱动的节点尺寸 ────────────────────────────────────────────
def measure_node(node: Node, max_text_w: float | None = None) -> None:
    """就地设置节点的 w/h，保证 label/sub 装得下。

    这是「文字超出容器」这类问题的根治手段：宽度先按文字算出来，
    再受 min/max 约束夹逼，而不是先定宽度再把文字硬塞进去。
    """
    limit = (max_text_w or NODE["max_w"]) - NODE["pad_x"] * 2 - TEXT_PAD
    label_w = tm.text_width(node.label, FONT["node"])
    sub_w = tm.text_width(node.sub, FONT["node_sub"]) if node.sub else 0.0
    icon_w = 20 if node.icon else 0
    content_w = max(label_w, sub_w) + icon_w

    w = max(NODE["min_w"], min(content_w + NODE["pad_x"] * 2 + TEXT_PAD, NODE["max_w"]))
    if max_text_w:
        w = min(w, max_text_w)

    # 高度：单行 / 两行；两行时允许标签本身折成多行
    inner_w = w - NODE["pad_x"] * 2 - icon_w
    label_lines = tm.wrap(node.label, inner_w, FONT["node"])
    node._label_lines = label_lines  # type: ignore[attr-defined]
    node._sub_lines = (  # type: ignore[attr-defined]
        tm.wrap(node.sub, inner_w, FONT["node_sub"]) if node.sub else []
    )
    n_lines = len(label_lines) + len(node._sub_lines)  # type: ignore[attr-defined]
    if n_lines <= 1:
        h = NODE["h"]
    elif n_lines == 2:
        h = NODE["h_two_line"]
    else:
        h = NODE["h_two_line"] + (n_lines - 2) * (FONT["node_sub"] + 4)
    if node.shape == "diamond":
        # 菱形要留出斜边空间
        w *= 1.45
        h = max(h * 1.9, 74)
    node.w, node.h = w, h


# ── 排布原语 ──────────────────────────────────────────────────────────
def row(
    nodes: list[Node],
    x: float,
    y: float,
    width: float,
    align: str = "center",
    gap: float | None = None,
) -> list[Node]:
    """水平排布，撑满给定宽度（PRD：不要把内容挤在中间留两侧大白边）。"""
    for n in nodes:
        measure_node(n)
    total = sum(n.w for n in nodes)
    n_gaps = max(len(nodes) - 1, 1)
    g = gap if gap is not None else max(GAP["node_x"], (width - total) / n_gaps)
    span = total + g * (len(nodes) - 1)
    cur = x + (width - span) / 2 if align == "center" else x
    max_h = max((n.h for n in nodes), default=0)
    for n in nodes:
        n.x = cur
        n.y = y if align != "bottom" else y + (max_h - n.h)
        if align == "center_v":
            n.y = y + (max_h - n.h) / 2
        cur += n.w + g
    return nodes


def column(nodes: list[Node], x: float, y: float, width: float, gap: float | None = None) -> list[Node]:
    """垂直排布，节点左右居中于给定列。"""
    for n in nodes:
        measure_node(n, max_text_w=width)
        n.x = x + (width - n.w) / 2
    g = gap if gap is not None else GAP["node_y"]
    cur = y
    for n in nodes:
        n.y = cur
        cur += n.h + g
    return nodes


def grid(nodes: list[Node], x: float, y: float, width: float, cols: int, gap_x: float | None = None,
         gap_y: float | None = None) -> list[Node]:
    """网格排布，用于结构图、对比矩阵。"""
    for n in nodes:
        measure_node(n, max_text_w=width / cols - GAP["node_x"])
    rows = math.ceil(len(nodes) / cols)
    gx = gap_x if gap_x is not None else GAP["node_x"]
    gy = gap_y if gap_y is not None else GAP["node_y"]
    cell_w = (width - gx * (cols - 1)) / cols
    for i, n in enumerate(nodes):
        r, c = divmod(i, cols)
        n.x = x + c * (cell_w + gx) + (cell_w - n.w) / 2
        row_h = max((nodes[r * cols + k].h for k in range(cols) if r * cols + k < len(nodes)), default=n.h)
        n.y = y + r * (row_h + gy) + (row_h - n.h) / 2
    return nodes


# ── 连线路径 ──────────────────────────────────────────────────────────
def _anchor_of(node: Node, spec: str | tuple[str, str]) -> tuple[float, float]:
    if isinstance(spec, tuple):
        return node.anchors()[spec[1]]
    return (node.cx, node.cy)


def _auto_anchors(a: Node, b: Node) -> tuple[tuple[float, float], tuple[float, float], str]:
    """按相对位置自动选锚点，并给出建议的绕行方向。"""
    dx, dy = b.cx - a.cx, b.cy - a.cy
    if abs(dx) >= abs(dy):
        return a.anchors()["r" if dx >= 0 else "l"], b.anchors()["l" if dx >= 0 else "r"], "h"
    return a.anchors()["b" if dy >= 0 else "t"], b.anchors()["t" if dy >= 0 else "b"], "v"


def route(edge: Edge, nodes: dict[str, Node]) -> str:
    """计算连线的 SVG path，写入 edge._path 并返回。

    直线用轻微的三次贝塞尔而不是纯直线——纯直线在密集图里会和节点边框混淆，
    微弯也让「这条线从哪来、到哪去」更容易跟。
    """
    src_id = edge.source[0] if isinstance(edge.source, tuple) else edge.source
    dst_id = edge.target[0] if isinstance(edge.target, tuple) else edge.target
    a, b = nodes[src_id], nodes[dst_id]

    if src_id == dst_id:
        return _self_loop(edge, a)

    explicit = isinstance(edge.source, tuple) or isinstance(edge.target, tuple)
    if explicit:
        p0 = _anchor_of(a, edge.source)
        p1 = _anchor_of(b, edge.target)
        axis = "h" if abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1]) else "v"
    else:
        p0, p1, axis = _auto_anchors(a, b)

    # 平行连线偏移：垂直于主轴方向平移，避免两条线完全重合
    if edge.offset:
        if axis == "h":
            p0 = (p0[0], p0[1] + edge.offset)
            p1 = (p1[0], p1[1] + edge.offset)
        else:
            p0 = (p0[0] + edge.offset, p0[1])
            p1 = (p1[0] + edge.offset, p1[1])

    if edge.waypoints:
        pts = [p0, *edge.waypoints, p1]
        d = f"M{p0[0]:.1f} {p0[1]:.1f}"
        for pt in pts[1:]:
            d += f" L{pt[0]:.1f} {pt[1]:.1f}"
        edge._path = d
        return d

    if axis == "h":
        mx = (p0[0] + p1[0]) / 2
        d = f"M{p0[0]:.1f} {p0[1]:.1f} C{mx:.1f} {p0[1]:.1f} {mx:.1f} {p1[1]:.1f} {p1[0]:.1f} {p1[1]:.1f}"
    else:
        my = (p0[1] + p1[1]) / 2
        d = f"M{p0[0]:.1f} {p0[1]:.1f} C{p0[0]:.1f} {my:.1f} {p1[0]:.1f} {my:.1f} {p1[0]:.1f} {p1[1]:.1f}"
    edge._path = d
    return d


def _self_loop(edge: Edge, n: Node) -> str:
    """自环 / 回环：从节点一侧出去绕回来。"""
    side = edge.detour or "above"
    if side == "above":
        y = n.y - GAP["node_y"] * 0.9
        d = (f"M{n.x + n.w * 0.28:.1f} {n.y:.1f} C{n.x + n.w * 0.1:.1f} {y:.1f} "
             f"{n.x + n.w * 0.9:.1f} {y:.1f} {n.x + n.w * 0.72:.1f} {n.y:.1f}")
    else:
        y = n.y + n.h + GAP["node_y"] * 0.9
        d = (f"M{n.x + n.w * 0.72:.1f} {n.y + n.h:.1f} C{n.x + n.w * 0.9:.1f} {y:.1f} "
             f"{n.x + n.w * 0.1:.1f} {y:.1f} {n.x + n.w * 0.28:.1f} {n.y + n.h:.1f}")
    edge._path = d
    return d


def route_all(edges: list[Edge], nodes: dict[str, Node]) -> None:
    """给一组连线计算路径，并自动为平行线分配偏移。"""
    # 统计同向同锚点的连线，给它们错开
    seen: dict[tuple, int] = {}
    for e in edges:
        key = (
            e.source[0] if isinstance(e.source, tuple) else e.source,
            e.target[0] if isinstance(e.target, tuple) else e.target,
        )
        n = seen.get(key, 0)
        seen[key] = n + 1
        if n and not e.offset:
            e.offset = 14 * ((n + 1) // 2) * (1 if n % 2 else -1)
        route(e, nodes)


# ── 分区 ──────────────────────────────────────────────────────────────
def region_bounds(region: Region, nodes: list[Node], pad: float | None = None) -> Region:
    """按分区内节点的实际包围盒反推分区尺寸（PRD：区块高度贴内容）。"""
    p = pad if pad is not None else GAP["region_pad"]
    if not nodes:
        return region
    x0 = min(n.x for n in nodes) - p
    y0 = min(n.y for n in nodes) - p - (GAP["region_head"] if region.label else 0)
    x1 = max(n.x + n.w for n in nodes) + p
    y1 = max(n.y + n.h for n in nodes) + p
    region.x, region.y, region.w, region.h = x0, y0, x1 - x0, y1 - y0
    return region


def stack_regions(regions: list[Region], nodes_by_region: dict[str, list[Node]],
                  x: float, y: float, width: float) -> float:
    """把多个分区自上而下堆叠，返回总高度。"""
    cur = y
    for r in regions:
        ns = nodes_by_region.get(r.id, [])
        if ns:
            for n in ns:
                n.x += x - min(m.x for m in ns)
        region_bounds(r, ns)
        r.x, r.w = x, width
        r.y = cur
        cur += r.h + GAP["region"]
    return cur - y - GAP["region"]


# ── 画布 ──────────────────────────────────────────────────────────────
class Canvas:
    """SVG 画布：累积元素，最后统一输出。

    所有坐标都是绝对坐标（viewBox 从 0 0 开始），不使用嵌套 transform ——
    嵌套 transform 会让「元素是否越界」的校验变得不可靠。
    """

    def __init__(self, width: int | None = None, height: int | None = None, title: str | None = None,
                 subtitle: str | None = None):
        self.width = width or CANVAS["width"]
        self.height = height or 0
        self.title = title
        self.subtitle = subtitle
        self._parts: list[str] = []
        self._defs: list[str] = [f"<style>\n{svg_header_style()}</style>"]

    def add(self, markup: str) -> None:
        self._parts.append(markup)

    def add_def(self, markup: str) -> None:
        self._defs.append(markup)

    def content_top(self) -> float:
        return (TITLE_BLOCK if self.title else 0) + CANVAS["margin"]

    def to_svg(self) -> str:
        h = self.height or 600
        defs = "\n".join(self._defs)
        body = "\n".join(self._parts)
        title = ""
        if self.title:
            y = CANVAS["margin"] + 22
            title += (
                f'<text class="t-title" x="{CANVAS["margin"]}" y="{y}">{_esc(self.title)}</text>\n'
            )
            if self.subtitle:
                title += (
                    f'<text class="t-sub" x="{CANVAS["margin"]}" y="{y + 20}">'
                    f'{_esc(self.subtitle)}</text>\n'
                )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {h}" '
            f'width="{self.width}" height="{h}" role="img" '
            f'aria-label="{_esc(self.title or "技术原理解释图")}">\n'
            f"<defs>\n{_ARROW_DEFS}\n{defs}\n</defs>\n"
            f'<rect width="{self.width}" height="{h}" fill="{PALETTE["bg"]}"/>\n'
            f"{title}{body}\n</svg>\n"
        )


def _esc(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_ARROW_DEFS = """\
  <marker id="arrow" viewBox="0 0 10 8" refX="9.5" refY="4" markerWidth="8" markerHeight="7"
          orient="auto-start-reverse" markerUnits="userSpaceOnUse">
    <path d="M0 0.6 L9.5 4 L0 7.4 Z" fill="context-stroke"/>
  </marker>
  <marker id="arrow-muted" viewBox="0 0 10 8" refX="9.5" refY="4" markerWidth="8" markerHeight="7"
          orient="auto-start-reverse" markerUnits="userSpaceOnUse">
    <path d="M0 0.6 L9.5 4 L0 7.4 Z" fill="#6b7280"/>
  </marker>"""


def esc(s: str) -> str:
    return _esc(s)


def svg_header_style() -> str:
    """内联样式表。渲染出的 SVG 自包含，不依赖外部 CSS。"""
    from .tokens import FONT_STACK, FONT_MONO, PALETTE, FONT

    return f"""\
/* 变量声明在 svg 根元素上，不是 :root —— 独立 SVG 文档里 :root 不生效，
   变量会解析失败并回退成黑色填充（曾导致整张图变成黑底）。 */
svg {{
  --bg: {PALETTE['bg']}; --bg-soft: {PALETTE['bg_soft']};
  --ink: {PALETTE['ink']}; --ink-muted: {PALETTE['ink_muted']};
  --line: {PALETTE['line']}; --neutral: {PALETTE['neutral']};
  --primary: {PALETTE['primary']}; --primary-soft: {PALETTE['primary_soft']};
  --accent: {PALETTE['accent']}; --accent-soft: {PALETTE['accent_soft']};
  --warn: {PALETTE['warn']}; --warn-soft: {PALETTE['warn_soft']};
  --danger: {PALETTE['danger']}; --danger-soft: {PALETTE['danger_soft']};
  --violet: {PALETTE['violet']}; --violet-soft: {PALETTE['violet_soft']};
  font-family: {FONT_STACK};
}}
text {{ fill: var(--ink); }}
.t-title {{ font-size: {FONT['title']}px; font-weight: 650; }}
.t-sub {{ font-size: {FONT['subtitle']}px; fill: var(--ink-muted); }}
.t-region {{ font-size: {FONT['region']}px; font-weight: 600; }}
.t-node {{ font-size: {FONT['node']}px; }}
.t-node-sub {{ font-size: {FONT['node_sub']}px; fill: var(--ink-muted); }}
.t-label {{ font-size: {FONT['label']}px; fill: var(--ink-muted); }}
.t-conclusion {{ font-size: {FONT['conclusion']}px; font-weight: 550; }}
.t-legend {{ font-size: {FONT['legend']}px; fill: var(--ink-muted); }}
.t-mono {{ font-family: {FONT_MONO}; font-size: {FONT['label']}px; }}
.edge {{ fill: none; }}
.edge-label-bg {{ fill: var(--bg); }}
"""
