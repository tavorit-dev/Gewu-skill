#!/usr/bin/env python3
"""格物 Gewu 渲染器入口。详见 gewu/cli.py 的用法说明。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gewu.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
