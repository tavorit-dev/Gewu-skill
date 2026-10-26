"""文字测量：内置字符宽度表，不依赖 fontTools 或字体文件。

为什么需要它：程序化渲染的核心承诺是「文字一定装得下」。要判断一个标签是否
超出节点框，必须在渲染前知道它有多宽。用固定宽度的字符表估算，误差约 ±5%，
足够做「装不装得下」的判定（判定时另留 PAD 余量，见 tokens.TEXT_PAD）。

宽度单位是 em（相对字号的比例），基于常见无衬线字体的 advance width：
    CJK 全角        1.0
    拉丁大写        0.62
    拉丁小写        0.52
    数字            0.55
    空格            0.28
"""
from __future__ import annotations

import unicodedata

# 拉丁小写字母的逐字宽度（比一律 0.52 更准，尤其 i/l/j 与 m/w 差异很大）
_LOWER = {
    "i": 0.24, "j": 0.24, "l": 0.24, "f": 0.30, "t": 0.34, "r": 0.35,
    "m": 0.84, "w": 0.75, "s": 0.48, "c": 0.50, "z": 0.48, "x": 0.50,
    "v": 0.52, "y": 0.52, "k": 0.52, "a": 0.55, "b": 0.56, "d": 0.56,
    "e": 0.55, "g": 0.56, "h": 0.56, "n": 0.56, "o": 0.56, "p": 0.56,
    "q": 0.56, "u": 0.56,
}
_UPPER = {
    "I": 0.28, "J": 0.45, "L": 0.52, "T": 0.58, "W": 0.90, "M": 0.85,
    "A": 0.65, "B": 0.62, "C": 0.65, "D": 0.67, "E": 0.58, "F": 0.56,
    "G": 0.70, "H": 0.70, "K": 0.65, "N": 0.72, "O": 0.72, "P": 0.60,
    "Q": 0.72, "R": 0.63, "S": 0.58, "U": 0.70, "V": 0.65, "X": 0.62,
    "Y": 0.60, "Z": 0.58,
}
_DIGIT = 0.55
_PUNCT = {
    " ": 0.28, ".": 0.28, ",": 0.28, ":": 0.28, ";": 0.28, "!": 0.28,
    "|": 0.26, "'": 0.20, '"': 0.38, "`": 0.30, "(": 0.33, ")": 0.33,
    "[": 0.33, "]": 0.33, "{": 0.35, "}": 0.35, "-": 0.35, "_": 0.55,
    "/": 0.35, "\\": 0.35, "<": 0.58, ">": 0.58, "=": 0.58, "+": 0.58,
    "*": 0.42, "&": 0.70, "%": 0.85, "#": 0.58, "@": 0.95, "$": 0.55,
    "~": 0.58, "^": 0.48, "?": 0.48,
}

# 等宽字体（代码、命令片段）
_MONO = 0.60


def char_width(ch: str, mono: bool = False) -> float:
    """单个字符的宽度，单位 em。"""
    if mono:
        return _MONO
    if ch in _PUNCT:
        return _PUNCT[ch]
    if ch.isdigit():
        return _DIGIT
    if ch in _LOWER:
        return _LOWER[ch]
    if ch in _UPPER:
        return _UPPER[ch]
    # 东亚全角（CJK 汉字、假名、全角标点）
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 1.0
    # 其余（带变音符的拉丁字母、希腊字母等）按小写估
    if ch.isalpha():
        return 0.58
    return 0.55


def text_width(text: str, font_size: float, mono: bool = False) -> float:
    """一段文字的像素宽度。"""
    return sum(char_width(c, mono) for c in text) * font_size


def wrap(text: str, max_width: float, font_size: float, mono: bool = False) -> list[str]:
    """按像素宽度折行。

    优先在空格处断行；CJK 没有空格，退化为逐字断行。
    单字宽度超过 max_width 时无法再断，原样返回该字（由调用方决定是否缩字号）。
    """
    if not text:
        return []
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        cur = ""
        # 先按空格切成 token，但 CJK 字符本身是可断点，需拆出来
        tokens: list[str] = []
        buf = ""
        for ch in paragraph:
            if ch == " ":
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(" ")
            elif unicodedata.east_asian_width(ch) in ("W", "F"):
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(ch)
            else:
                buf += ch
        if buf:
            tokens.append(buf)

        for tok in tokens:
            trial = cur + tok
            if cur and text_width(trial.strip(), font_size, mono) > max_width:
                lines.append(cur.rstrip())
                cur = "" if tok == " " else tok
            else:
                cur = trial
        lines.append(cur.rstrip())
    return lines or [""]


def fits(text: str, max_width: float, font_size: float, mono: bool = False) -> bool:
    """文字是否装得下给定宽度。"""
    return text_width(text, font_size, mono) <= max_width


def shrink_to_fit(
    text: str, max_width: float, font_size: float, min_size: float = 11.0, mono: bool = False
) -> float:
    """逐档缩小字号直到装得下，返回最终字号。

    到 min_size 仍装不下就返回 min_size —— 此时调用方应当拆图或改写标签，
    而不是继续缩小（PRD 8.3：不得为了塞进画布而不断缩小字体）。
    """
    size = font_size
    while size > min_size and not fits(text, max_width, size, mono):
        size -= 0.5
    return size
