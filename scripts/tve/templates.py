"""七种图形模板的渲染函数（PRD 6.1）。

每个模板接收 VEM 的一段结构化描述，返回完整 SVG 字符串。
模板只负责**语义到图形的映射**：哪些是参与者、谁是主路径、差异在哪一维；
坐标、尺寸、锚点一律交给 layout 模块。

七个模板对应七种「内容的天然形状」，不是七种装饰风格：
    mechanism   组件 + 作用关系        —— 某个功能究竟如何工作
    flow        步骤 + 分支            —— 一个操作按什么顺序执行
    sequence    参与者 + 时间顺序      —— 多个参与者之间的消息往来
    state       状态 + 迁移条件        —— 系统在不同状态下如何变化
    structure   组件 + 组织关系        —— 数据/组件如何组织与存储
    comparison  同构对照 + 差异高亮    —— 两种方案的差异及其代价
    causality   原因 → 机制 → 结果     —— 为什么某个现象会发生
"""
from __future__ import annotations

from . import textmetrics as tm
from .layout import (
    Annotation, Canvas, Edge, Node, Region, esc, measure_node, region_bounds,
    route_all, row, column, grid,
)
from .tokens import CANVAS, DASH, FONT, GAP, NODE, PALETTE, RADIUS, ROLES, STROKE

# ── 通用绘制helper ────────────────────────────────────────────────────
_EDGE_COLOR = {
    "line": "var(--line)",
    "primary": "var(--primary)",
    "accent": "var(--accent)",
    "warn": "var(--warn)",
    "danger": "var(--danger)",
    "muted": "var(--ink-muted)",
}


def _draw_region(r: Region, canvas: Canvas) -> None:
    role = ROLES.get(r.role, ROLES["neutral"])
    canvas.add(
        f'<rect x="{r.x:.1f}" y="{r.y:.1f}" width="{r.w:.1f}" height="{r.h:.1f}" '
        f'rx="{RADIUS["region"]}" fill="{PALETTE["bg_soft"]}" '
        f'stroke="{PALETTE["line"]}" stroke-width="{STROKE["region"]}"/>'
    )
    if r.label:
        canvas.add(
            f'<text class="t-region" x="{r.x + GAP["region_pad"]:.1f}" '
            f'y="{r.y + GAP["region_pad"] + FONT["region"] - 2:.1f}">{esc(r.label)}</text>'
        )
    if r.sub:
        lx = r.x + GAP["region_pad"] + tm.text_width(r.label, FONT["region"]) + 10
        canvas.add(
            f'<text class="t-label" x="{lx:.1f}" '
            f'y="{r.y + GAP["region_pad"] + FONT["region"] - 2:.1f}">{esc(r.sub)}</text>'
        )


def _draw_node(n: Node, canvas: Canvas) -> None:
    role = ROLES.get(n.role, ROLES["neutral"])
    rx = RADIUS["pill"] if n.shape == "pill" else RADIUS["node"]
    if n.shape == "diamond":
        cx, cy = n.cx, n.cy
        pts = f"{cx},{n.y} {n.x + n.w},{cy} {cx},{n.y + n.h} {n.x},{cy}"
        canvas.add(
            f'<polygon points="{pts}" fill="{role["fill"]}" stroke="{role["stroke"]}" '
            f'stroke-width="{STROKE["node"]}"/>'
        )
    elif n.shape == "cylinder":
        ry = 8
        canvas.add(
            f'<path d="M{n.x:.1f} {n.y + ry:.1f} a{n.w / 2:.1f} {ry} 0 0 1 {n.w:.1f} 0 '
            f'v{n.h - 2 * ry:.1f} a{n.w / 2:.1f} {ry} 0 0 1 {-n.w:.1f} 0 z" '
            f'fill="{role["fill"]}" stroke="{role["stroke"]}" stroke-width="{STROKE["node"]}"/>'
        )
    elif n.shape == "note":
        # 折角便签，用于「原文依据」「未知项」这类非机制性内容
        fold = 12
        canvas.add(
            f'<path d="M{n.x:.1f} {n.y:.1f} h{n.w - fold:.1f} l{fold} {fold} '
            f'v{n.h - fold:.1f} h{-n.w:.1f} z" fill="{role["fill"]}" '
            f'stroke="{role["stroke"]}" stroke-width="{STROKE["node"]}"/>'
            f'<path d="M{n.x + n.w - fold:.1f} {n.y:.1f} v{fold} h{fold}" fill="none" '
            f'stroke="{role["stroke"]}" stroke-width="{STROKE["node"]}"/>'
        )
    else:
        canvas.add(
            f'<rect x="{n.x:.1f}" y="{n.y:.1f}" width="{n.w:.1f}" height="{n.h:.1f}" '
            f'rx="{rx if rx != RADIUS["pill"] else n.h / 2:.1f}" fill="{role["fill"]}" '
            f'stroke="{role["stroke"]}" stroke-width="{STROKE["node"]}"/>'
        )

    _draw_node_text(n, canvas, role["text"])


def _draw_node_text(n: Node, canvas: Canvas, color: str) -> None:
    label_lines = getattr(n, "_label_lines", [n.label])
    sub_lines = getattr(n, "_sub_lines", [])
    line_h = FONT["node"] + 3
    sub_h = FONT["node_sub"] + 2
    total = len(label_lines) * line_h + len(sub_lines) * sub_h
    y = n.cy - total / 2 + FONT["node"] * 0.85

    for ln in label_lines:
        canvas.add(
            f'<text class="t-node" x="{n.cx:.1f}" y="{y:.1f}" text-anchor="middle" '
            f'fill="{color}">{esc(ln)}</text>'
        )
        y += line_h
    for ln in sub_lines:
        canvas.add(
            f'<text class="t-node-sub" x="{n.cx:.1f}" y="{y:.1f}" text-anchor="middle">{esc(ln)}</text>'
        )
        y += sub_h


def _draw_edge(e: Edge, canvas: Canvas) -> None:
    color = _EDGE_COLOR.get(e.role, "var(--line)")
    dash = DASH.get(e.style)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    marker = ""
    if e.arrow in ("end", "both"):
        marker += ' marker-end="url(#arrow)"'
    if e.arrow == "both":
        marker += ' marker-start="url(#arrow)"'
    sw = STROKE["edge_strong"] if e.role in ("primary", "warn", "danger") else STROKE["edge"]
    canvas.add(
        f'<path class="edge" d="{e.path}" stroke="{color}" stroke-width="{sw}"'
        f'{dash_attr}{marker}/>'
    )
    if e.label:
        mx, my = _path_midpoint(e.path)
        w = tm.text_width(e.label, FONT["label"]) + 8
        canvas.add(
            f'<rect class="edge-label-bg" x="{mx - w / 2:.1f}" y="{my - 9:.1f}" '
            f'width="{w:.1f}" height="15" rx="3"/>'
            f'<text class="t-label" x="{mx:.1f}" y="{my + 2:.1f}" text-anchor="middle">'
            f'{esc(e.label)}</text>'
        )


def _path_midpoint(d: str) -> tuple[float, float]:
    """取路径中点附近的一个点，用于放连线标签。

    用采样近似而不是解析求解：路径由我们自己生成（C 或 L 段），
    采样 24 个点取弧长中点足够准，且对任何路径形式都成立。
    """
    nums = _parse_path(d)
    if not nums:
        return (0.0, 0.0)
    pts = _sample(nums, 24)
    # 取 45% 处，避开箭头和节点边缘
    return pts[int(len(pts) * 0.45)]


def _parse_path(d: str) -> list[tuple[str, list[float]]]:
    import re
    tokens = re.findall(r"[MLCSTQAZmlcstqaz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    out, i = [], 0
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t.upper()
            n = {"M": 2, "L": 2, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}.get(cmd, 0)
            args = [float(x) for x in tokens[i + 1:i + 1 + n]]
            out.append((cmd, args))
            i += 1 + n
        else:
            i += 1
    return out


def _sample(cmds: list[tuple[str, list[float]]], n: int) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    for cmd, a in cmds:
        if cmd == "M":
            cur = start = (a[0], a[1])
            pts.append(cur)
        elif cmd == "L":
            for k in range(1, n + 1):
                t = k / n
                pts.append((cur[0] + (a[0] - cur[0]) * t, cur[1] + (a[1] - cur[1]) * t))
            cur = (a[0], a[1])
        elif cmd == "C":
            p0 = cur
            p1, p2, p3 = (a[0], a[1]), (a[2], a[3]), (a[4], a[5])
            for k in range(1, n + 1):
                t = k / n
                mt = 1 - t
                x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
                y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
                pts.append((x, y))
            cur = p3
        elif cmd == "Z":
            cur = start
    return pts or [(0.0, 0.0)]


def _draw_annotations(anns: list[Annotation], canvas: Canvas, x: float, width: float) -> None:
    for a in anns:
        if a.kind == "conclusion":
            role = ROLES["primary"]
            h = 34
            canvas.add(
                f'<rect x="{x:.1f}" y="{a.y:.1f}" width="{width:.1f}" height="{h}" rx="7" '
                f'fill="{role["fill"]}" stroke="{role["stroke"]}" stroke-width="1.2"/>'
            )
            canvas.add(
                f'<text class="t-conclusion" x="{x + 14:.1f}" y="{a.y + 22:.1f}">'
                f'{esc(a.text)}</text>'
            )
        elif a.kind == "boundary":
            canvas.add(
                f'<text class="t-label" x="{x:.1f}" y="{a.y:.1f}">{esc(a.text)}</text>'
            )
        elif a.kind == "legend":
            canvas.add(f'<text class="t-legend" x="{x:.1f}" y="{a.y:.1f}">{esc(a.text)}</text>')


def _finalize(canvas: Canvas, content_bottom: float, anns: list[Annotation]) -> str:
    """统一收尾：算画布高度、拼装 SVG。"""
    bottom = content_bottom
    for a in anns:
        bottom = max(bottom, a.y + (34 if a.kind == "conclusion" else 18))
    canvas.height = int(bottom + CANVAS["margin"])
    return canvas.to_svg()


# ── 模板 1：Flow（步骤 + 分支）────────────────────────────────────────
def render_flow(spec: dict) -> str:
    """流程图：一条主路径，可有分支。

    spec:
        title, subtitle
        steps:      [{id, label, sub?, role?}]       主路径，横向排布
        branches:   [{from, to, label?, style?}]     额外连线（分支/回环）
        conclusion: str?
        boundary:   str?
    """
    steps = [
        Node(id=s["id"], label=s["label"], sub=s.get("sub"), role=s.get("role", "neutral"),
             shape=s.get("shape", "rect"))
        for s in spec["steps"]
    ]
    canvas = Canvas(title=spec.get("title"), subtitle=spec.get("subtitle"))
    inner_w = canvas.width - CANVAS["margin"] * 2
    y = canvas.content_top() + 10
    row(steps, CANVAS["margin"], y, inner_w, align="center_v")
    nodes = {n.id: n for n in steps}

    edges: list[Edge] = []
    for i in range(len(steps) - 1):
        edges.append(Edge(steps[i].id, steps[i + 1].id, role="primary", arrow="end"))
    for b in spec.get("branches", []):
        edges.append(Edge(b["from"], b["to"], label=b.get("label"),
                          style=b.get("style", "solid"), role=b.get("role", "line"),
                          arrow=b.get("arrow", "end"), detour=b.get("detour")))
    route_all(edges, nodes)

    content_bottom = max(n.y + n.h for n in steps)
    for e in edges:
        _draw_edge(e, canvas)
    for n in steps:
        _draw_node(n, canvas)

    anns = _collect_anns(spec, content_bottom + 30, canvas.width - CANVAS["margin"] * 2,
                         CANVAS["margin"])
    _draw_annotations(anns, canvas, CANVAS["margin"], canvas.width - CANVAS["margin"] * 2)
    return _finalize(canvas, content_bottom, anns)


# ── 模板 2：Mechanism（组件 + 作用关系）──────────────────────────────
def render_mechanism(spec: dict) -> str:
    """机制图：中心机制 + 参与的组件 + 作用关系。

    spec:
        title, subtitle
        core:       {id, label, sub?}                被解释的机制
        actors:     [{id, label, sub?, role?, side?}] 参与者，side: left|right|top|bottom
        relations:  [{from, to, label?, style?, role?}]
        conclusion, boundary
    """
    core_spec = spec["core"]
    core = Node(id=core_spec["id"], label=core_spec["label"], sub=core_spec.get("sub"),
                role=core_spec.get("role", "primary"), shape=core_spec.get("shape", "rect"))
    measure_node(core, max_text_w=320)

    actors = [
        Node(id=a["id"], label=a["label"], sub=a.get("sub"), role=a.get("role", "neutral"))
        for a in spec.get("actors", [])
    ]
    for a in actors:
        measure_node(a, max_text_w=220)

    canvas = Canvas(title=spec.get("title"), subtitle=spec.get("subtitle"))
    inner_w = canvas.width - CANVAS["margin"] * 2
    left = [a for a, s in zip(actors, spec.get("actors", [])) if s.get("side", "left") == "left"]
    right = [a for a, s in zip(actors, spec.get("actors", [])) if s.get("side", "left") == "left" or True]
    right = [a for a, s in zip(actors, spec.get("actors", [])) if s.get("side") == "right"]
    top = [a for a, s in zip(actors, spec.get("actors", [])) if s.get("side") == "top"]
    bottom = [a for a, s in zip(actors, spec.get("actors", [])) if s.get("side") == "bottom"]
    # 未指定 side 的按左右交替
    unspecified = [a for a, s in zip(actors, spec.get("actors", [])) if not s.get("side")]
    for i, a in enumerate(unspecified):
        (left if i % 2 == 0 else right).append(a)

    y_top = canvas.content_top() + 10
    col_w = 220
    # 左右列
    ly = y_top + (max(len(top), 0) * (NODE["h"] + GAP["node_y"]))
    if left:
        column(left, CANVAS["margin"], ly, col_w)
    if right:
        column(right, canvas.width - CANVAS["margin"] - col_w, ly, col_w)
    if top:
        row(top, CANVAS["margin"] + col_w + GAP["node_x"], y_top,
            inner_w - (col_w + GAP["node_x"]) * 2, align="center_v")
    # 中心
    core.x = (canvas.width - core.w) / 2
    left_bottom = max((n.y + n.h for n in left), default=ly)
    right_bottom = max((n.y + n.h for n in right), default=ly)
    core.y = max(left_bottom, right_bottom, y_top) - core.h / 2 + 20
    if bottom:
        by = max(left_bottom, right_bottom, core.y + core.h) + GAP["node_y"] + 20
        row(bottom, CANVAS["margin"] + col_w + GAP["node_x"], by,
            inner_w - (col_w + GAP["node_x"]) * 2, align="center_v")

    nodes = {n.id: n for n in [core, *actors]}
    edges = [Edge(r["from"], r["to"], label=r.get("label"), style=r.get("style", "solid"),
                  role=r.get("role", "line"), arrow=r.get("arrow", "end"))
             for r in spec.get("relations", [])]
    route_all(edges, nodes)

    content_bottom = max(n.y + n.h for n in nodes.values())
    for r in spec.get("regions", []):
        pass
    for e in edges:
        _draw_edge(e, canvas)
    for n in nodes.values():
        _draw_node(n, canvas)
    anns = _collect_anns(spec, content_bottom + 30, inner_w, CANVAS["margin"])
    _draw_annotations(anns, canvas, CANVAS["margin"], inner_w)
    return _finalize(canvas, content_bottom, anns)


# ── 模板 3：Structure（组件 + 组织关系）──────────────────────────────
def render_structure(spec: dict) -> str:
    """结构图：分区 + 嵌套。

    spec:
        title, subtitle
        regions:  [{id, label, sub?, role?, nodes: [{id,label,sub?,role?}]}]
        links:    [{from, to, label?, style?}]
        conclusion, boundary
    """
    canvas = Canvas(title=spec.get("title"), subtitle=spec.get("subtitle"))
    inner_w = canvas.width - CANVAS["margin"] * 2
    y = canvas.content_top() + 10
    all_nodes: dict[str, Node] = {}
    regions: list[Region] = []

    for rs in spec.get("regions", []):
        region = Region(id=rs["id"], label=rs.get("label", ""), sub=rs.get("sub"),
                        role=rs.get("role", "neutral"))
        ns = [Node(id=n["id"], label=n["label"], sub=n.get("sub"), role=n.get("role", "neutral"),
                   shape=n.get("shape", "rect")) for n in rs.get("nodes", [])]
        cols = min(len(ns), rs.get("cols", 4)) or 1
        grid(ns, CANVAS["margin"] + GAP["region_pad"], y + GAP["region_head"] + GAP["region_pad"],
             inner_w - GAP["region_pad"] * 2, cols)
        region_bounds(region, ns)
        region.x, region.w = CANVAS["margin"], inner_w
        region.y = y
        y += region.h + GAP["region"]
        regions.append(region)
        for n in ns:
            all_nodes[n.id] = n

    edges = [Edge(l["from"], l["to"], label=l.get("label"), style=l.get("style", "solid"),
                  role=l.get("role", "line"), arrow=l.get("arrow", "end"))
             for l in spec.get("links", [])]
    route_all(edges, all_nodes)

    for r in regions:
        _draw_region(r, canvas)
    for e in edges:
        _draw_edge(e, canvas)
    for n in all_nodes.values():
        _draw_node(n, canvas)

    content_bottom = y - GAP["region"]
    anns = _collect_anns(spec, content_bottom + 26, inner_w, CANVAS["margin"])
    _draw_annotations(anns, canvas, CANVAS["margin"], inner_w)
    return _finalize(canvas, content_bottom, anns)


# ── 模板 4：Comparison（同构对照 + 差异高亮）─────────────────────────
def render_comparison(spec: dict) -> str:
    """对比图：左右同构，差异点高亮。

    spec:
        title, subtitle
        options:   [{id, label, sub?, role?}]            2~3 个方案，横向分列
        dimensions:[{label, values: [str, ...], diff?: bool}]  逐维度对照
        verdict:   {text, role?}                         结论条
        boundary
    """
    opts = spec["options"]
    dims = spec.get("dimensions", [])
    canvas = Canvas(title=spec.get("title"), subtitle=spec.get("subtitle"))
    inner_w = canvas.width - CANVAS["margin"] * 2
    label_col_w = 132
    n_opt = len(opts)
    col_w = (inner_w - label_col_w - GAP["node_x"] * (n_opt - 1)) / n_opt

    y = canvas.content_top() + 10
    head_nodes = [
        Node(id=o["id"], label=o["label"], sub=o.get("sub"), role=o.get("role", "primary"))
        for o in opts
    ]
    for i, n in enumerate(head_nodes):
        measure_node(n, max_text_w=col_w)
        n.x = CANVAS["margin"] + label_col_w + i * (col_w + GAP["node_x"]) + (col_w - n.w) / 2
        n.y = y
    head_h = max(n.h for n in head_nodes)
    y += head_h + GAP["node_y"]

    row_h = 40
    row_ys: list[float] = []
    for d in dims:
        row_ys.append(y)
        y += row_h

    content_bottom = y
    verdict = spec.get("verdict")
    if verdict:
        content_bottom += 16

    # 绘制
    for n in head_nodes:
        _draw_node(n, canvas)
    # 维度分隔线与标签
    for i, d in enumerate(dims):
        ry = row_ys[i]
        if d.get("diff"):
            canvas.add(
                f'<rect x="{CANVAS["margin"]:.1f}" y="{ry - 6:.1f}" width="{inner_w:.1f}" '
                f'height="{row_h - 4}" rx="6" fill="{PALETTE["warn_soft"]}"/>'
            )
        canvas.add(
            f'<text class="t-label" x="{CANVAS["margin"] + 10:.1f}" y="{ry + 17:.1f}">'
            f'{esc(d["label"])}</text>'
        )
        for j, v in enumerate(d.get("values", [])[:n_opt]):
            cx = CANVAS["margin"] + label_col_w + j * (col_w + GAP["node_x"]) + col_w / 2
            lines = tm.wrap(str(v), col_w - 8, FONT["node_sub"])
            ty = ry + 17 - (len(lines) - 1) * 6
            for k, ln in enumerate(lines):
                cls = "t-node-sub" if not d.get("diff") else "t-node"
                canvas.add(
                    f'<text class="{cls}" x="{cx:.1f}" y="{ty + k * 14:.1f}" '
                    f'text-anchor="middle">{esc(ln)}</text>'
                )
        if i < len(dims) - 1:
            canvas.add(
                f'<line x1="{CANVAS["margin"]:.1f}" y1="{ry + row_h - 8:.1f}" '
                f'x2="{CANVAS["margin"] + inner_w:.1f}" y2="{ry + row_h - 8:.1f}" '
                f'stroke="{PALETTE["line"]}" stroke-width="1"/>'
            )

    anns: list[Annotation] = []
    if verdict:
        anns.append(Annotation(text=verdict["text"], kind="conclusion",
                               y=content_bottom - row_h + 12, role=verdict.get("role", "primary")))
        content_bottom += 20
    if spec.get("boundary"):
        anns.append(Annotation(text=spec["boundary"], kind="boundary", y=content_bottom + 20))
        content_bottom += 24
    _draw_annotations(anns, canvas, CANVAS["margin"], inner_w)
    return _finalize(canvas, content_bottom, anns)


# ── 模板 5：Sequence（参与者 + 时间顺序）─────────────────────────────
def render_sequence(spec: dict) -> str:
    """时序图：泳道 + 消息箭头 + 时间轴。

    spec:
        title, subtitle
        actors:  [{id, label, sub?}]
        messages:[{from, to, label, style?, role?, note?}]
        conclusion, boundary
    """
    actors = [Node(id=a["id"], label=a["label"], sub=a.get("sub"), role=a.get("role", "neutral"),
                   shape="rect") for a in spec["actors"]]
    canvas = Canvas(title=spec.get("title"), subtitle=spec.get("subtitle"))
    inner_w = canvas.width - CANVAS["margin"] * 2
    y = canvas.content_top() + 10
    row(actors, CANVAS["margin"], y, inner_w, align="center_v")
    head_bottom = max(n.y + n.h for n in actors)
    lifeline_top = head_bottom + 14

    msgs = spec.get("messages", [])
    step = 46
    lifeline_bottom = lifeline_top + len(msgs) * step + 18

    # 泳道竖线
    for a in actors:
        canvas.add(
            f'<line x1="{a.cx:.1f}" y1="{lifeline_top:.1f}" x2="{a.cx:.1f}" '
            f'y2="{lifeline_bottom:.1f}" stroke="{PALETTE["line"]}" stroke-width="1" '
            f'stroke-dasharray="4 5"/>'
        )

    by_id = {a.id: a for a in actors}
    for i, m in enumerate(msgs):
        my = lifeline_top + 22 + i * step
        src, dst = by_id[m["from"]], by_id[m["to"]]
        role = m.get("role", "primary")
        color = _EDGE_COLOR.get(role, "var(--primary)")
        dash = DASH.get(m.get("style", "solid"))
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        marker = ' marker-end="url(#arrow)"' if m.get("style") != "return" else ' marker-end="url(#arrow)"'
        # 返回消息（从右往左）用虚线区分
        if src.cx <= dst.cx:
            x0, x1 = src.cx + 2, dst.cx - 2
        else:
            x0, x1 = src.cx - 2, dst.cx + 2
        canvas.add(
            f'<line x1="{x0:.1f}" y1="{my:.1f}" x2="{x1:.1f}" y2="{my:.1f}" '
            f'stroke="{color}" stroke-width="{STROKE["edge"]}"{dash_attr}{marker}/>'
        )
        # 序号
        canvas.add(
            f'<circle cx="{CANVAS["margin"] + 8:.1f}" cy="{my:.1f}" r="9" '
            f'fill="{PALETTE["bg_soft"]}" stroke="{PALETTE["line"]}" stroke-width="1"/>'
            f'<text class="t-label" x="{CANVAS["margin"] + 8:.1f}" y="{my + 3.5:.1f}" '
            f'text-anchor="middle">{i + 1}</text>'
        )
        # 消息标签（放在线中段上方）
        mid = (x0 + x1) / 2
        canvas.add(
            f'<text class="t-label" x="{mid:.1f}" y="{my - 6:.1f}" text-anchor="middle">'
            f'{esc(m["label"])}</text>'
        )
        if m.get("note"):
            canvas.add(
                f'<text class="t-label" x="{mid:.1f}" y="{my + 13:.1f}" text-anchor="middle" '
                f'font-style="italic">{esc(m["note"])}</text>'
            )

    # 激活条（可选的「某参与者正在处理」语义）
    for act in spec.get("activations", []):
        a = by_id[act["actor"]]
        y0 = lifeline_top + 22 + act["from"] * step - 12
        y1 = lifeline_top + 22 + act["to"] * step + 6
        canvas.add(
            f'<rect x="{a.cx - 6:.1f}" y="{y0:.1f}" width="12" height="{y1 - y0:.1f}" rx="2" '
            f'fill="{PALETTE["primary_soft"]}" stroke="{PALETTE["primary"]}" stroke-width="1"/>'
        )

    for a in actors:
        _draw_node(a, canvas)

    content_bottom = lifeline_bottom
    anns = _collect_anns(spec, content_bottom + 26, inner_w, CANVAS["margin"])
    _draw_annotations(anns, canvas, CANVAS["margin"], inner_w)
    return _finalize(canvas, content_bottom, anns)


# ── 模板 6：State（状态 + 迁移条件）──────────────────────────────────
def render_state(spec: dict) -> str:
    """状态图：状态节点 + 带条件的迁移。

    spec:
        title, subtitle
        states:     [{id, label, sub?, role?, initial?: bool, final?: bool}]
        transitions:[{from, to, trigger, style?, role?}]
        conclusion, boundary
    """
    states = [
        Node(id=s["id"], label=s["label"], sub=s.get("sub"), role=s.get("role", "neutral"),
             shape="pill" if s.get("initial") or s.get("final") else "rect")
        for s in spec["states"]
    ]
    canvas = Canvas(title=spec.get("title"), subtitle=spec.get("subtitle"))
    inner_w = canvas.width - CANVAS["margin"] * 2
    y = canvas.content_top() + 10
    cols = min(len(states), spec.get("cols", 4)) or 1
    grid(states, CANVAS["margin"], y, inner_w, cols)
    nodes = {n.id: n for n in states}

    edges = [Edge(t["from"], t["to"], label=t.get("trigger"), style=t.get("style", "solid"),
                  role=t.get("role", "line"), arrow="end", detour=t.get("detour"))
             for t in spec.get("transitions", [])]
    route_all(edges, nodes)

    content_bottom = max(n.y + n.h for n in states)
    for e in edges:
        _draw_edge(e, canvas)
    for n in states:
        _draw_node(n, canvas)
    # 初始/终态标记
    for s, n in zip(spec["states"], states):
        if s.get("initial"):
            canvas.add(
                f'<circle cx="{n.x - 16:.1f}" cy="{n.cy:.1f}" r="6" fill="{PALETTE["ink"]}"/>'
            )
        if s.get("final"):
            canvas.add(
                f'<circle cx="{n.x + n.w + 16:.1f}" cy="{n.cy:.1f}" r="7" fill="none" '
                f'stroke="{PALETTE["ink"]}" stroke-width="1.6"/>'
                f'<circle cx="{n.x + n.w + 16:.1f}" cy="{n.cy:.1f}" r="3.6" fill="{PALETTE["ink"]}"/>'
            )

    anns = _collect_anns(spec, content_bottom + 30, inner_w, CANVAS["margin"])
    _draw_annotations(anns, canvas, CANVAS["margin"], inner_w)
    return _finalize(canvas, content_bottom, anns)


# ── 模板 7：Causality（原因 → 机制 → 结果）──────────────────────────
def render_causality(spec: dict) -> str:
    """因果图：从原因经中间机制到结果，区分「必然」与「可能」。

    spec:
        title, subtitle
        causes:   [{id, label, sub?}]
        mechanism:[{id, label, sub?}]
        effects:  [{id, label, sub?, role?}]      role=warn 表示负面结果
        links:    [{from, to, label?, style?}]    style=weak 表示「可能」而非「必然」
        conclusion, boundary
    """
    causes = [Node(id=c["id"], label=c["label"], sub=c.get("sub"), role="neutral") for c in spec["causes"]]
    mech = [Node(id=m["id"], label=m["label"], sub=m.get("sub"), role="primary") for m in spec["mechanism"]]
    effects = [Node(id=e["id"], label=e["label"], sub=e.get("sub"), role=e.get("role", "accent"))
               for e in spec["effects"]]

    canvas = Canvas(title=spec.get("title"), subtitle=spec.get("subtitle"))
    inner_w = canvas.width - CANVAS["margin"] * 2
    y = canvas.content_top() + 10
    lane_w = inner_w / 3 - GAP["node_x"]

    column(causes, CANVAS["margin"], y, lane_w)
    column(mech, CANVAS["margin"] + lane_w + GAP["node_x"], y, lane_w)
    column(effects, CANVAS["margin"] + (lane_w + GAP["node_x"]) * 2, y, lane_w)

    # 分栏标题
    for i, (t, col) in enumerate([("原因", PALETTE["ink_muted"]),
                                  ("中间机制", PALETTE["primary"]),
                                  ("结果", PALETTE["ink_muted"])]):
        lx = CANVAS["margin"] + i * (lane_w + GAP["node_x"])
        canvas.add(
            f'<text class="t-label" x="{lx + lane_w / 2:.1f}" y="{y - 8:.1f}" '
            f'text-anchor="middle" fill="{col}">{t}</text>'
        )

    nodes = {n.id: n for n in [*causes, *mech, *effects]}
    edges = [Edge(l["from"], l["to"], label=l.get("label"), style=l.get("style", "solid"),
                  role=l.get("role", "line"), arrow=l.get("arrow", "end"))
             for l in spec.get("links", [])]
    route_all(edges, nodes)

    content_bottom = max(n.y + n.h for n in nodes.values())
    for e in edges:
        _draw_edge(e, canvas)
    for n in nodes.values():
        _draw_node(n, canvas)

    anns = _collect_anns(spec, content_bottom + 30, inner_w, CANVAS["margin"])
    _draw_annotations(anns, canvas, CANVAS["margin"], inner_w)
    return _finalize(canvas, content_bottom, anns)


# ── 公共 ──────────────────────────────────────────────────────────────
def _collect_anns(spec: dict, y: float, width: float, x: float) -> list[Annotation]:
    """按 PRD 6.2 的视觉层次收拢图上的辅助文字：结论 → 边界说明。"""
    anns: list[Annotation] = []
    cur = y
    if spec.get("conclusion"):
        anns.append(Annotation(text=spec["conclusion"], kind="conclusion", y=cur))
        cur += 34 + 14
    if spec.get("boundary"):
        anns.append(Annotation(text=spec["boundary"], kind="boundary", y=cur + 6))
    return anns


TEMPLATES = {
    "flow": render_flow,
    "mechanism": render_mechanism,
    "structure": render_structure,
    "comparison": render_comparison,
    "sequence": render_sequence,
    "state": render_state,
    "causality": render_causality,
}


def render(spec: dict) -> str:
    t = spec.get("visual_type") or spec.get("type")
    if t not in TEMPLATES:
        raise ValueError(
            f"未知的 visual_type: {t!r}；可选：{', '.join(sorted(TEMPLATES))}"
        )
    return TEMPLATES[t](spec)
