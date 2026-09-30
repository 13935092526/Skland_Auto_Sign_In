"""字体发现与加载：优先使用系统中文字体，兼容 Windows / macOS / Linux。

Linux 发行版通常把字体放在 /usr/share/fonts 的多层子目录里
（例如 .../opentype/noto/NotoSansCJK-Regular.ttc、.../truetype/wqy/wqy-zenhei.ttc）。
因此这里对字体目录做**递归索引**，避免只扫顶层目录而找不到中文字体——
那种情况下会退化成 PIL 默认位图字体（不含中文字形），导致中文渲染成乱码/豆腐块。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import ImageFont

# 常见字体族关键字 -> 候选字体文件名（按顺序尝试）
FONT_FAMILIES: dict[str, list[str]] = {
    "yahei":  ["msyh", "msyhbd", "Microsoft YaHei", "PingFang"],
    "hei":    ["simhei", "SimHei", "wqy-zenhei", "NotoSansCJK"],
    "song":   ["simsun", "SimSun", "NotoSerifCJK", "SourceHanSerif"],
    "kai":    ["simkai", "KaiTi", "STKaiti"],
    "deng":   ["Deng", "Dengxian"],
    "mono":   ["consola", "CascadiaMono", "DejaVuSansMono"],
    "arial":  ["arial", "Helvetica"],
}

_BOLD_OVERRIDES = {
    "yahei": "msyhbd",
    "hei":   "simhei",
    "song":  "simsun",
    "deng":  "Dengb",
    "mono":  "consolab",
    "arial": "arialbd",
}

# 兜底顺序（子串匹配、忽略大小写）：中英文都能覆盖，Windows 与开源/Linux 字体兼顾
_FALLBACKS: list[str] = [
    "msyh", "simhei", "simsun",
    "sourcehansans", "sourcehanserif",
    "wqy-zenhei", "wqy-microhei",
    "notosanscjk", "notoserifcjk", "notosanssc",
    "droidsansfallback", "pingfang", "hiragino",
]

_FONT_EXTS = (".ttf", ".ttc", ".otf")
_cache: dict[tuple[str | None, int], ImageFont.FreeTypeFont] = {}
_font_index: list[Path] | None = None


def _font_dirs() -> list[Path]:
    """返回各平台存在的字体目录。"""
    dirs: list[Path] = []
    if sys.platform == "win32":
        dirs.append(Path(os.environ.get("SystemRoot", "C:\\Windows")) / "Fonts")
    else:
        dirs += [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path(os.path.expanduser("~/.fonts")),
            Path(os.path.expanduser("~/.local/share/fonts")),
        ]
        if sys.platform == "darwin":
            dirs += [
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path(os.path.expanduser("~/Library/Fonts")),
            ]
    return [d for d in dirs if d.is_dir()]


def _all_fonts() -> list[Path]:
    """递归收集所有字体文件并按文件名排序，结果缓存（只扫描一次）。"""
    global _font_index
    if _font_index is None:
        files: list[Path] = []
        for d in _font_dirs():
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in _FONT_EXTS:
                    files.append(p)
        _font_index = sorted(files, key=lambda x: x.name.lower())
    return _font_index


def _match(candidate: str) -> Path | None:
    """在递归索引中查找候选字体（文件名子串匹配，忽略大小写）。"""
    cand = candidate.lower()
    for f in _all_fonts():
        if cand in f.name.lower():
            return f
    return None


def find_font(family: str | None = None, bold: bool = False) -> str | None:
    """返回字体文件绝对路径；family 可为关键字、字体名/文件名片段或完整路径。"""
    if family:
        p = Path(family)
        if p.is_file():
            return str(p)
        key = family.lower()
        if key in FONT_FAMILIES:
            names = ([_BOLD_OVERRIDES[key]] if bold and key in _BOLD_OVERRIDES else []) + FONT_FAMILIES[key]
            for n in names:
                hit = _match(n)
                if hit:
                    return str(hit)
        hit = _match(family)
        if hit:
            return str(hit)
    for n in _FALLBACKS:
        hit = _match(n)
        if hit:
            return str(hit)
    return None


def load_font(size: int, family: str | None = None, bold: bool = False) -> ImageFont.FreeTypeFont:
    """加载指定字号的字体（带缓存）。找不到系统中文字体时退回 PIL 默认字体。"""
    path = find_font(family, bold)
    key = (path, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
    return _cache[key]
