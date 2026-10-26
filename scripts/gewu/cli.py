"""命令行入口：渲染、校验、预览。

用法：
    python3 scripts/render.py diagram.yaml -o out.svg        # 渲染
    python3 scripts/render.py diagram.yaml --check           # 渲染并校验，有 error 则退出码 1
    python3 scripts/render.py diagram.yaml --png out.png     # 渲染后转 PNG（需 rsvg-convert 或 Chrome）
    python3 scripts/render.py --list                         # 列出可用模板
    python3 scripts/render.py --schema                       # 打印 VEM 字段说明
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 允许 `python3 scripts/render.py` 直接跑（把 scripts/ 加进 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gewu import templates, validate  # noqa: E402


def load_spec(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            sys.exit("需要 PyYAML 读取 YAML：pip3 install --user pyyaml\n"
                     "（或把 VEM 写成 .json）")
        return yaml.safe_load(text)
    return json.loads(text)


def render_png(svg_path: Path, png_path: Path, scale: int = 2) -> None:
    """SVG → PNG。优先 rsvg-convert，退回 Chrome 无头截图。

    走 Chrome 时必须把 SVG 包进 HTML 再用 --screenshot —— 直接把 .svg 文件
    交给 Chrome 截图会得到一张接近空白的图（Chrome 对独立 SVG 文档的
    headless 截图行为与 HTML 文档不同）。
    """
    if _which("rsvg-convert"):
        args = ["rsvg-convert", "-o", str(png_path)]
        if scale != 1:
            args += ["-z", str(scale)]
        subprocess.run([*args, str(svg_path)], check=True)
        return

    chrome = _find_chrome()
    if not chrome:
        sys.exit("转 PNG 需要 rsvg-convert 或 Chrome/Chromium（设 CHROME_PATH）")

    svg = svg_path.read_text(encoding="utf-8")
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    w, h = (int(float(m.group(1))), int(float(m.group(2)))) if m else (1200, 900)
    # 用 CSS 把 SVG 放大 scale 倍，截图分辨率随之提高（文字更清晰）
    html = (
        f'<!doctype html><meta charset="utf-8">'
        f'<style>html,body{{margin:0;padding:0;background:#fff}}'
        f'svg{{display:block;width:{w * scale}px;height:{h * scale}px}}</style>'
        f"{svg}"
    )
    tmp_html = svg_path.with_suffix(".preview.html")
    tmp_html.write_text(html, encoding="utf-8")
    try:
        subprocess.run([
            chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
            f"--screenshot={png_path}", f"--window-size={w * scale},{h * scale}",
            "--force-device-scale-factor=1",
            f"--default-background-color=FFFFFFFF", tmp_html.resolve().as_uri(),
        ], check=True, capture_output=True)
    finally:
        tmp_html.unlink(missing_ok=True)


def _which(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None


def _find_chrome() -> str | None:
    import os
    for p in (
        os.environ.get("CHROME_PATH"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome", "/usr/bin/chromium-browser",
    ):
        if p and Path(p).exists():
            return p
    return None


def cmd_schema() -> None:
    print("""VEM（Visual Explanation Model）字段说明

必填：
  title         一句话说明这张图要解释什么
  visual_type   七选一：flow | mechanism | structure | comparison | sequence | state | causality
  core_message  一句话结论（读者看完这张图应得到的判断）

强烈建议：
  question      这张图回答的问题（用于自检「问题是否明确」）
  scope         {system, version} —— 版本相关的技术必须写，避免把某版本实现泛化
  evidence      [{source_ref, supports}] —— 每条关键关系的原文依据
  unknowns      [str] —— 原文没说明、图里也不该编的部分
  boundary      图上要标出的适用边界/假设

各 visual_type 的专属字段见 references/visual-model-schema.md。
""")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="渲染 VEM 为 SVG 原理图")
    ap.add_argument("spec", nargs="?", help="VEM 文件（.yaml/.yml/.json）")
    ap.add_argument("-o", "--out", help="输出 SVG 路径（默认与输入同名）")
    ap.add_argument("--png", help="同时导出 PNG 到这个路径")
    ap.add_argument("--scale", type=int, default=2, help="PNG 导出倍率（默认 2）")
    ap.add_argument("--check", action="store_true", help="渲染后校验，有 error 则退出码 1")
    ap.add_argument("--list", action="store_true", help="列出可用模板")
    ap.add_argument("--schema", action="store_true", help="打印 VEM 字段说明")
    ap.add_argument("--json-issues", action="store_true", help="校验结果以 JSON 输出")
    args = ap.parse_args(argv)

    if args.list:
        for name, fn in sorted(templates.TEMPLATES.items()):
            doc = (fn.__doc__ or "").strip().split("\n")[0]
            print(f"  {name:12s} {doc}")
        return 0
    if args.schema:
        cmd_schema()
        return 0
    if not args.spec:
        ap.print_help()
        return 2

    spec_path = Path(args.spec)
    if not spec_path.exists():
        sys.exit(f"找不到文件：{spec_path}")

    spec = load_spec(spec_path)
    try:
        svg = templates.render(spec)
    except ValueError as e:
        sys.exit(str(e))

    out = Path(args.out) if args.out else spec_path.with_suffix(".svg")
    out.write_text(svg, encoding="utf-8")
    print(f"已渲染 → {out}  ({len(svg)} 字节)")

    if args.png:
        render_png(out, Path(args.png), args.scale)
        print(f"已导出 → {args.png}")

    if args.check:
        issues = validate.validate(svg, spec)
        if args.json_issues:
            print(json.dumps([i.__dict__ for i in issues], ensure_ascii=False, indent=2))
        else:
            print(validate.format_report(issues, str(out)))
        return 1 if any(i.level == "error" for i in issues) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
