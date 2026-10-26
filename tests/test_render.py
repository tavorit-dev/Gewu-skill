#!/usr/bin/env python3
"""渲染器与校验器的回归测试。

跑法：python3 tests/test_render.py
不依赖 pytest（本 skill 要能在任何装了 python3 的环境里自检）。
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from gewu import textmetrics as tm, validate
from gewu.templates import TEMPLATES, render

FAILURES: list[str] = []
PASSES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSES
    if cond:
        PASSES += 1
    else:
        FAILURES.append(f"{name}: {detail}")


# ── 文字测量 ──────────────────────────────────────────────────────────
def test_textmetrics() -> None:
    # 中文一个字约等于一个字号宽
    w = tm.text_width("中", 20)
    check("textmetrics/cjk", 19 <= w <= 21, f"中文宽 {w}，期望 ~20")

    # 拉丁小写窄于大写
    check("textmetrics/case", tm.text_width("aaa", 20) < tm.text_width("AAA", 20),
          "小写应窄于大写")

    # i 明显窄于 m
    check("textmetrics/i_lt_m", tm.text_width("i", 20) < tm.text_width("m", 20) * 0.5,
          "i 应远窄于 m")

    # 折行：不产生超宽行
    lines = tm.wrap("这是一段需要折行的中文文本内容示例", 60, 14)
    check("textmetrics/wrap_cjk", all(tm.text_width(l, 14) <= 60 + 1e-6 for l in lines),
          f"折行后仍有超宽行：{[(l, tm.text_width(l, 14)) for l in lines]}")
    check("textmetrics/wrap_count", len(lines) >= 2, f"应折成多行，实际 {len(lines)}")

    # 折行不丢字
    src = "hello world 这是中文 mixed content 123"
    joined = "".join(tm.wrap(src, 70, 13)).replace(" ", "")
    check("textmetrics/wrap_noloss", joined == src.replace(" ", ""),
          f"折行丢字：{joined!r} != {src.replace(' ', '')!r}")

    # shrink_to_fit 不越界
    size = tm.shrink_to_fit("一个很长的标签文本内容", 50, 14, min_size=11)
    check("textmetrics/shrink", size >= 11, f"缩小到 {size} 低于下限")


# ── 各模板渲染 ────────────────────────────────────────────────────────
SPECS: dict[str, dict] = {
    "flow": {
        "title": "请求处理流程",
        "subtitle": "示例",
        "visual_type": "flow",
        "core_message": "请求依次经过三层处理",
        "steps": [
            {"id": "a", "label": "接收请求", "sub": "HTTP 解析"},
            {"id": "b", "label": "鉴权", "sub": "校验 token", "role": "primary"},
            {"id": "c", "label": "业务处理", "sub": "读写数据库"},
            {"id": "d", "label": "返回响应", "role": "accent"},
        ],
        "branches": [{"from": "b", "to": "d", "label": "鉴权失败", "style": "weak", "role": "warn"}],
        "conclusion": "鉴权失败会短路，不进入业务处理。",
        "boundary": "图中省略了缓存层。",
    },
    "mechanism": {
        "title": "缓存如何减少数据库压力",
        "visual_type": "mechanism",
        "core_message": "命中缓存时请求不落到数据库",
        "core": {"id": "cache", "label": "缓存层", "sub": "内存 KV"},
        "actors": [
            {"id": "app", "label": "应用", "side": "left"},
            {"id": "db", "label": "数据库", "sub": "持久化", "side": "right"},
        ],
        "relations": [
            {"from": "app", "to": "cache", "label": "读", "role": "primary"},
            {"from": "cache", "to": "db", "label": "未命中", "style": "weak", "role": "warn"},
            {"from": "db", "to": "cache", "label": "回填", "style": "data"},
        ],
        "conclusion": "缓存的价值在于把重复读挡在数据库之外。",
    },
    "structure": {
        "title": "哈希表的内存布局",
        "visual_type": "structure",
        "core_message": "桶数组 + 链表解决冲突",
        "regions": [
            {"id": "r1", "label": "桶数组", "sub": "连续内存",
             "nodes": [{"id": "b0", "label": "bucket[0]"}, {"id": "b1", "label": "bucket[1]"},
                       {"id": "b2", "label": "bucket[2]"}]},
            {"id": "r2", "label": "冲突链表", "role": "primary",
             "nodes": [{"id": "n1", "label": "entry A", "sub": "key=foo"},
                       {"id": "n2", "label": "entry B", "sub": "key=bar"}]},
        ],
        "links": [{"from": "b1", "to": "n1", "label": "next", "role": "primary"},
                  {"from": "n1", "to": "n2", "label": "next"}],
    },
    "comparison": {
        "title": "同步与异步写入的取舍",
        "visual_type": "comparison",
        "core_message": "同步简单但慢，异步快但要处理失败",
        "options": [
            {"id": "o1", "label": "同步写", "sub": "写完才返回"},
            {"id": "o2", "label": "异步写", "sub": "入队即返回", "role": "accent"},
        ],
        "dimensions": [
            {"label": "延迟", "values": ["高（等落盘）", "低（只入队）"], "diff": True},
            {"label": "一致性", "values": ["强", "最终一致"], "diff": True},
            {"label": "实现复杂度", "values": ["低", "高（需补偿）"]},
            {"label": "失败处理", "values": ["直接报错", "需重试与死信"]},
        ],
        "verdict": {"text": "选择依据是能否接受最终一致，而不是单纯比快慢。"},
        "boundary": "未考虑批量写入场景。",
    },
    "sequence": {
        "title": "客户端与服务端的消息往来",
        "visual_type": "sequence",
        "core_message": "三次交互完成一次请求",
        "actors": [{"id": "c", "label": "客户端"}, {"id": "s", "label": "服务端"},
                   {"id": "d", "label": "存储"}],
        "messages": [
            {"from": "c", "to": "s", "label": "请求"},
            {"from": "s", "to": "d", "label": "查询"},
            {"from": "d", "to": "s", "label": "结果", "style": "weak"},
            {"from": "s", "to": "c", "label": "响应"},
        ],
        "activations": [{"actor": "s", "from": 0, "to": 3}],
    },
    "state": {
        "title": "TCP 连接的状态迁移",
        "visual_type": "state",
        "core_message": "四次挥手后连接才真正关闭",
        "states": [
            {"id": "st1", "label": "ESTABLISHED", "initial": True},
            {"id": "st2", "label": "FIN_WAIT_1", "role": "primary"},
            {"id": "st3", "label": "TIME_WAIT", "role": "warn"},
            {"id": "st4", "label": "CLOSED", "final": True},
        ],
        "transitions": [
            {"from": "st1", "to": "st2", "trigger": "主动关闭"},
            {"from": "st2", "to": "st3", "trigger": "收到 ACK"},
            {"from": "st3", "to": "st4", "trigger": "等待 2MSL"},
        ],
    },
    "causality": {
        "title": "为什么加缓存反而变慢",
        "visual_type": "causality",
        "core_message": "缓存未命中时多了一次无效查询",
        "causes": [{"id": "c1", "label": "缓存命中率低", "sub": "热点分散"}],
        "mechanism": [{"id": "m1", "label": "每次请求先查缓存", "sub": "多一次网络往返"},
                      {"id": "m2", "label": "再查数据库", "sub": "与原路径相同"}],
        "effects": [{"id": "e1", "label": "延迟上升", "role": "warn"}],
        "links": [
            {"from": "c1", "to": "m1"},
            {"from": "m1", "to": "m2"},
            {"from": "m2", "to": "e1"},
        ],
    },
}


def test_templates() -> None:
    for name, spec in SPECS.items():
        try:
            svg = render(spec)
        except Exception:
            FAILURES.append(f"templates/{name}: 渲染抛异常\n{traceback.format_exc()}")
            continue

        check(f"templates/{name}/nonempty", len(svg) > 500, f"输出只有 {len(svg)} 字节")
        check(f"templates/{name}/svg_tag", svg.lstrip().startswith("<svg"),
              "输出应以 <svg 开头（style 必须在 defs 内）")

        issues = validate.validate(svg, spec)
        errors = [i for i in issues if i.level == "error"]
        check(f"templates/{name}/valid", not errors,
              "校验有 error：" + "; ".join(str(e) for e in errors))


def test_validate_catches_problems() -> None:
    """校验器必须真的能抓到问题——否则它只是个摆设。"""
    bad_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<script>alert(1)</script>'
        '<rect x="0" y="0" width="50" height="50" fill="#fff"/>'
        '<rect x="200" y="200" width="50" height="50" fill="#fff"/>'
        "</svg>"
    )
    issues = validate.validate(bad_svg)
    kinds = {i.kind for i in issues}
    check("validate/catches_script", "element" in kinds, f"未抓到未允许元素：{issues}")
    check("validate/catches_bounds", "bounds" in kinds, f"未抓到越界：{issues}")

    broken = "<svg><rect"
    issues = validate.validate(broken)
    check("validate/catches_xml", any(i.kind == "xml" for i in issues), "未抓到 XML 错误")

    # 文字超出节点框必须被抓到
    overflow = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
        '<rect x="10" y="10" width="80" height="40" fill="#fff"/>'
        '<text class="t-node" x="50" y="35" text-anchor="middle">'
        "这是一段远超节点宽度的很长标签文字</text>"
        "</svg>"
    )
    issues = validate.validate(overflow)
    check("validate/catches_text_overflow", any(i.kind == "text" for i in issues),
          f"未抓到文字溢出：{issues}")


def test_no_black_background() -> None:
    """回归：CSS 变量曾因声明在 :root 而失效，导致整图黑底。"""
    for name, spec in SPECS.items():
        svg = render(spec)
        check(f"vars/{name}/no_root_block", ":root {" not in svg,
              ":root 变量块会失效（独立 SVG 文档里不生效），必须声明在 svg 上")
        check(f"vars/{name}/vars_on_svg", "--bg:" in svg.split("<style>")[1].split("}")[0],
              "CSS 变量应声明在 svg 选择器上")
        # 背景矩形必须用字面色值，不能用 var()
        check(f"vars/{name}/literal_bg", 'fill="var(--bg)"/>\n' not in svg,
              "画布背景矩形不能用 var(--bg)，会回退成黑色")


def test_css_is_wellformed() -> None:
    """样式表必须括号配平、没有游离在规则块外的声明。

    回归：把 font-family 从 `svg {{...}}` 里挪出来时漏了闭合括号，
    结果 `font-family: ...;` 变成了规则块外的裸声明，整条规则被浏览器丢弃，
    字体回退到默认衬线体——图还是能出，但字形全变了，属于静默失败。
    """
    global PASSES
    for name, spec in SPECS.items():
        svg = render(spec)
        css = svg.split("<style>")[1].split("</style>")[0]
        check(f"css/{name}/balanced", css.count("{") == css.count("}"),
              f"花括号不配平：{{ {css.count('{')} 个，}} {css.count('}')} 个")

        # 逐行检查：规则块外的行必须是选择器、注释、空行或 @ 规则
        depth = 0
        for lineno, line in enumerate(css.split("\n"), 1):
            s = line.strip()
            if not s or s.startswith("/*") or s.endswith("*/"):
                continue
            if depth == 0 and s.endswith(";"):
                FAILURES.append(
                    f"css/{name}: 第 {lineno} 行是规则块外的裸声明：{s!r}"
                    f"（缺了闭合括号？）"
                )
                break
            depth += line.count("{") - line.count("}")
        else:
            PASSES += 1

        check(f"css/{name}/font_family_inside",
              "font-family" not in css.split("svg {")[1].split("}")[1].split("text {")[0]
              if "svg {" in css else True,
              "font-family 应写在 svg 规则块内")


def main() -> int:
    for fn in (test_textmetrics, test_templates, test_validate_catches_problems,
               test_no_black_background, test_css_is_wellformed):
        fn()
    print(f"通过 {PASSES} 项")
    if FAILURES:
        print(f"\n失败 {len(FAILURES)} 项：")
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
