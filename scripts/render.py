#!/usr/bin/env python3
"""tech-visual-explainer 渲染器入口。详见 tve/cli.py 的用法说明。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tve.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
