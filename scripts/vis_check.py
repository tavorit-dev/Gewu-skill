#!/usr/bin/env python3
"""图产物的程序化校验：确定性部分。

这是**渲染后**的复核，与 render.py --check（渲染前的结构与几何校验）互补：
render.py 检查 SVG 源码，本脚本检查真正渲染出来的像素。

用法:
    python3 scripts/vis_check.py diagram.png
    python3 scripts/vis_check.py diagram.gif          # 自动带抽帧动效检查
    python3 scripts/vis_check.py diagram.png --expect "标签A" "标签B"

**本脚本能验的**：尺寸、墨色占比、内容包围盒、留白分布、文字是否渲染出来（OCR）、
GIF 是否真的在动。
**验不了的**：文字是否糊、是否重叠、中文是否正确渲染（本机 tesseract 无中文包）、
技术语义是否正确。这些必须人眼终检——**不要把本脚本通过说成「图没问题」**。
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile


def load_gray(path: str):
    from PIL import Image
    import numpy as np
    return np.array(Image.open(path).convert("L")).astype(int)


def report_basic(path: str) -> dict:
    import numpy as np
    a = load_gray(path)
    h, w = a.shape
    ink = (a < 128).mean() * 100
    print(f"尺寸:        {w}x{h}")
    print(f"墨色占比:    {ink:.2f}%")

    # 内容包围盒：确认内容没有贴边、也没有大片偏移
    nz = np.argwhere(a < 245)
    if len(nz):
        y0, x0 = nz.min(axis=0)
        y1, x1 = nz.max(axis=0)
        print(f"内容包围盒:  x {x0}..{x1}  y {y0}..{y1}"
              f"  (左 {x0}px / 右 {w - x1}px / 上 {y0}px / 下 {h - y1}px 留白)")
    else:
        print("内容包围盒:  !! 整张图是纯色，没有内容 !!")
        return {"ink": ink, "empty": True}

    # 空格子：把画布切成 6x6，统计墨色 < 0.3% 的格子
    # 注意：几何风格本身留白多，空格子数只是「有没有大片死白」的参考，不是硬指标
    g = 6
    empty = []
    for i in range(g):
        for j in range(g):
            blk = a[i * h // g:(i + 1) * h // g, j * w // g:(j + 1) * w // g]
            if (blk < 128).mean() < 0.003:
                empty.append((j, i))
    print(f"空区块:      {len(empty)}/{g * g}"
          + (f" -> {empty}" if empty else "  (内容分布均匀)"))
    return {"ink": ink, "empty_cells": empty, "h": h, "w": w}


def report_ocr(path: str, expect: list[str]) -> None:
    """用 tesseract 确认文字真的渲染出来了。

    本机只装了 eng 语言包，**中文会被识别成乱码**——所以这里只对 ASCII 标签
    做断言。中文渲染是否正确只能人眼验，不要用 OCR 结果反推中文没问题。
    """
    if not shutil.which("tesseract"):
        print("OCR:         跳过（未安装 tesseract）")
        return
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        big = os.path.join(d, "big.png")
        im = Image.open(path)
        im.resize((im.width * 2, im.height * 2), Image.LANCZOS).save(big)
        try:
            out = subprocess.run(["tesseract", big, "-", "--psm", "11"],
                                 capture_output=True, text=True, timeout=60).stdout
        except subprocess.TimeoutExpired:
            print("OCR:         超时")
            return
    hits = [e for e in expect if e in out]
    misses = [e for e in expect if e not in out]
    if expect:
        print(f"OCR 断言:    命中 {len(hits)}/{len(expect)}" +
              (f"  未命中 {misses}" if misses else "  ✓"))
    else:
        print("OCR:         已运行（未指定 --expect，仅作参考）")
    print("             (tesseract 无中文包，中文标签必然乱码，属正常)")


def report_motion(path: str) -> None:
    """GIF 抽帧比对：确认动画真的在动，而不是静止的 GIF。"""
    if not path.lower().endswith(".gif"):
        return
    if not shutil.which("ffmpeg"):
        print("动效:        跳过（未安装 ffmpeg）")
        return
    import numpy as np
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(
            # 本机 ffmpeg 不认 -vsync，用 -fps_mode passthrough
            ["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
             "select='not(mod(n,25))'", "-fps_mode", "passthrough",
             os.path.join(d, "f%d.png")],
            check=True, capture_output=True)
        frames = sorted(glob.glob(os.path.join(d, "f*.png")),
                        key=lambda x: int("".join(filter(str.isdigit, os.path.basename(x)))))
        if len(frames) < 2:
            print(f"动效:        !! GIF 只抽出 {len(frames)} 帧，无法判定 !!")
            return
        prev, moves = None, []
        for f in frames[:6]:
            cur = load_gray(f)
            if prev is not None:
                moves.append(100 * (np.abs(cur - prev) > 20).mean())
            prev = cur
    print(f"动效:        抽 {len(frames)} 帧，相邻帧 motion "
          + ", ".join(f"{m:.3f}%" for m in moves))
    print("             " + ("在动 ✓" if max(moves) > 0.02 else "!! 疑似静止 !!"))


def main() -> int:
    ap = argparse.ArgumentParser(description="渲染产物的程序化校验")
    ap.add_argument("image")
    ap.add_argument("--expect", nargs="*", default=[],
                    help="期望在图中 OCR 到的 ASCII 标签（中文无法断言）")
    args = ap.parse_args()

    if not os.path.exists(args.image):
        sys.exit(f"找不到文件：{args.image}")

    print(f"校验对象:    {args.image}\n")
    report_basic(args.image)
    report_ocr(args.image, args.expect)
    report_motion(args.image)
    print()
    print("以上只覆盖确定性项。文字清晰度、重叠观感、中文渲染、技术语义正确性")
    print("本脚本验不了 —— 必须人眼终检，不要把这句通过当成「图没问题」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
