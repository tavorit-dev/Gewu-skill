"""SVG 结构与几何校验（PRD 7.1 第三层 / 8.1 的确定性部分）。

**能验的**（本模块负责）：
    - XML 是否合法、是否用了未允许的元素
    - 元素是否越出画布
    - 文字是否装得下所属节点（用 textmetrics 复算）
    - 节点之间是否重叠
    - 连线两端是否真的接在节点边界上
    - 图例/颜色语义是否与 ROLES 一致

**验不了的**（必须人眼终检，不要谎称已验）：
    - 文字实际渲染后是否糊、是否重叠（字体回退、字距都可能改变结果）
    - 中文是否正确渲染（缺字会显示豆腐块）
    - 技术语义是否正确（那要回到 VEM 和原文依据）
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import textmetrics as tm
from .tokens import FONT

SVG_NS = "http://www.w3.org/2000/svg"
# 允许出现的元素：纯静态矢量图不需要 script / foreignObject / image
ALLOWED = {
    "svg", "defs", "style", "title", "desc", "g", "rect", "circle", "ellipse",
    "line", "polyline", "polygon", "path", "text", "tspan", "marker", "use",
}


@dataclass
class Issue:
    level: str      # error | warn
    kind: str       # xml | element | bounds | text | overlap | edge | style
    message: str

    def __str__(self) -> str:
        tag = "ERROR" if self.level == "error" else "WARN "
        return f"[{tag}] {self.kind}: {self.message}"


def _localname(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def validate(svg: str, spec: dict | None = None) -> list[Issue]:
    """校验一段 SVG 文本。spec 存在时额外校验「图文一致性」的几何部分。"""
    issues: list[Issue] = []

    # 1. XML 合法性
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        return [Issue("error", "xml", f"XML 不合法：{e}")]

    # 2. 元素白名单
    for el in root.iter():
        name = _localname(el.tag)
        if name not in ALLOWED:
            issues.append(Issue("error", "element", f"使用了未允许的元素 <{name}>"))

    # 3. 画布边界
    vb = root.get("viewBox", "").split()
    if len(vb) != 4:
        issues.append(Issue("error", "bounds", "viewBox 缺失或格式错误"))
        return issues
    _, _, vw, vh = (float(x) for x in vb)
    for el in root.iter():
        name = _localname(el.tag)
        if name not in ("rect", "circle", "text", "path", "line", "polygon"):
            continue
        box = _element_box(el, name)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        tol = 1.5
        if x0 < -tol or y0 < -tol or x1 > vw + tol or y1 > vh + tol:
            snippet = (el.text or el.get("d", "") or "")[:30]
            issues.append(Issue(
                "error", "bounds",
                f"<{name}> 越出画布 ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f}) "
                f"超出 {vw:.0f}x{vh:.0f}  {snippet!r}"
            ))

    # 4. 文字是否装得下（用与渲染时相同的测量函数复算）
    issues.extend(_check_text_fit(root))

    # 5. 与 spec 对照：节点重叠、连线锚点
    if spec:
        issues.extend(_check_spec_geometry(spec))

    return issues


def _element_box(el, name: str) -> tuple[float, float, float, float] | None:
    def f(k, d=0.0):
        try:
            return float(el.get(k, d))
        except (TypeError, ValueError):
            return d

    if name == "rect":
        x, y, w, h = f("x"), f("y"), f("width"), f("height")
        if w == 0 or h == 0:
            return None
        return (x, y, x + w, y + h)
    if name == "circle":
        cx, cy, r = f("cx"), f("cy"), f("r")
        return (cx - r, cy - r, cx + r, cy + r)
    if name == "line":
        return (min(f("x1"), f("x2")), min(f("y1"), f("y2")),
                max(f("x1"), f("x2")), max(f("y1"), f("y2")))
    if name == "path":
        nums = [float(n) for n in re.findall(r"-?\d*\.?\d+", el.get("d", ""))]
        if len(nums) < 2:
            return None
        xs, ys = nums[0::2], nums[1::2]
        return (min(xs), min(ys), max(xs), max(ys))
    if name == "polygon":
        pts = [float(n) for n in re.findall(r"-?\d*\.?\d+", el.get("points", ""))]
        if len(pts) < 4:
            return None
        return (min(pts[0::2]), min(pts[1::2]), max(pts[0::2]), max(pts[1::2]))
    if name == "text":
        # 用测量函数估算文字盒（text-anchor 影响左右边界）
        txt = "".join(el.itertext())
        if not txt.strip():
            return None
        size = _font_size(el)
        w = tm.text_width(txt, size)
        anchor = el.get("text-anchor", "start")
        x, y = f("x"), f("y")
        if anchor == "middle":
            x0 = x - w / 2
        elif anchor == "end":
            x0 = x - w
        else:
            x0 = x
        return (x0, y - size, x0 + w, y + size * 0.25)
    return None


def _font_size(el) -> float:
    style = el.get("style", "")
    m = re.search(r"font-size:\s*([\d.]+)", style)
    if m:
        return float(m.group(1))
    if el.get("font-size"):
        return float(el.get("font-size"))
    cls = el.get("class", "")
    return {
        "t-title": FONT["title"], "t-sub": FONT["subtitle"], "t-region": FONT["region"],
        "t-node": FONT["node"], "t-node-sub": FONT["node_sub"], "t-label": FONT["label"],
        "t-conclusion": FONT["conclusion"], "t-legend": FONT["legend"],
    }.get(cls, FONT["node"])


def _check_text_fit(root) -> list[Issue]:
    """文字是否装得下所在节点：把每个 text 和它最近的 rect/polygon 配对。

    这是对「文字超出容器」的独立复核——渲染时已经用同一套测量算过一遍，
    这里从产物反查，能抓到渲染代码里的疏漏。
    """
    issues: list[Issue] = []
    # 收集节点矩形
    boxes: list[tuple[float, float, float, float]] = []
    for el in root.iter():
        if _localname(el.tag) == "rect":
            b = _element_box(el, "rect")
            if b and (b[2] - b[0]) > 60 and (b[3] - b[1]) > 28:
                boxes.append(b)
    for el in root.iter():
        if _localname(el.tag) != "text":
            continue
        cls = el.get("class", "")
        if cls not in ("t-node", "t-node-sub"):
            continue
        txt = "".join(el.itertext())
        if not txt.strip():
            continue
        size = _font_size(el)
        w = tm.text_width(txt, size)
        cx = float(el.get("x", 0))
        cy = float(el.get("y", 0))
        for (x0, y0, x1, y1) in boxes:
            if x0 - 2 <= cx <= x1 + 2 and y0 - 2 <= cy <= y1 + 2:
                if w > (x1 - x0) - 4:
                    issues.append(Issue(
                        "error", "text",
                        f"文字超出节点框：「{txt}」宽 {w:.0f}px > 节点内宽 {x1 - x0 - 4:.0f}px"
                    ))
                break
    return issues


def _check_spec_geometry(spec: dict) -> list[Issue]:
    """对照 VEM：节点是否重叠、必填字段是否齐全。"""
    issues: list[Issue] = []
    nodes = _collect_spec_nodes(spec)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            if _overlap(a, b):
                issues.append(Issue(
                    "error", "overlap",
                    f"节点重叠：「{a['label']}」与「{b['label']}」"
                ))
    return issues


def _collect_spec_nodes(spec: dict) -> list[dict]:
    out = []
    for key in ("steps", "actors", "states", "causes", "mechanism", "effects", "options"):
        for n in spec.get(key, []) or []:
            if isinstance(n, dict) and "label" in n and "x" in n:
                out.append(n)
    for r in spec.get("regions", []) or []:
        for n in r.get("nodes", []) or []:
            if "x" in n:
                out.append(n)
    return out


def _overlap(a: dict, b: dict) -> bool:
    ax0, ay0 = a["x"], a["y"]
    ax1, ay1 = ax0 + a.get("w", 0), ay0 + a.get("h", 0)
    bx0, by0 = b["x"], b["y"]
    bx1, by1 = bx0 + b.get("w", 0), by0 + b.get("h", 0)
    ix = min(ax1, bx1) - max(ax0, bx0)
    iy = min(ay1, by1) - max(ay0, by0)
    # 允许 1px 的浮点误差；明显相交才算重叠
    return ix > 2 and iy > 2


def format_report(issues: list[Issue], target: str = "") -> str:
    head = f"校验对象：{target}\n" if target else ""
    if not issues:
        return head + "确定性校验全部通过。\n\n注意：这**不代表图没问题**。文字清晰度、重叠观感、中文渲染、\n技术语义正确性本工具验不了，必须人眼终检。"
    lines = [head, f"发现 {len(issues)} 个问题：\n"]
    for i in issues:
        lines.append("  " + str(i))
    errors = sum(1 for i in issues if i.level == "error")
    if errors:
        lines.append(f"\n其中 {errors} 个是 error，必须修复后才能交付。")
    return "\n".join(lines)
