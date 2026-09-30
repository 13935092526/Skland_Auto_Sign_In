# -*- coding: utf-8 -*-
"""模板共享美术主题：纸质浅底 + 双线画框 + 白色圆角卡片 + 柔和高级配色。

所有模板从这里取用统一的颜色、竖屏长图度量与基础绘制工具，保证出图风格一致；
新增模板复用本模块即可自动继承同一套主题。
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------- 配色（柔和高级）
PAPER = "#F7F4ED"   # 纸质浅底
CARD  = "#FFFFFF"   # 白色卡片
INK   = "#2E2C27"   # 主文字
MUTED = "#8A8578"   # 次要文字
LINE  = "#DCD5C6"   # 分隔线/描边
GREEN = "#5E8C61"   # 苔绿
TERRA = "#C0704A"   # 陶土橙（强调）
GOLD  = "#B99150"   # 金
TECH  = "#3E5C76"   # 深钢蓝

# ---------------------------------------------------------------- 手机竖版长图度量
W = 1080            # 宽度固定，高度随内容
VPAD = 80           # 页面上下留白（画框内）
MARGIN = 56
PAD_IN = 56         # 卡片内边距
GAP = 48            # 卡片间距
RADIUS = 26         # 卡片圆角
FRAME = 34          # 画框内缩
HEADER_H = 112      # 页眉文字 + 分隔线
SEG_GAP, SEG_H = 12, 40   # 分段胶囊间距 / 高度


def spaced(d: ImageDraw.ImageDraw, xy, text, font, fill, tracking=8, anchor_right=False):
    """带字间距的绘制（用于页眉标题/日期），返回结束 x。anchor_right 时 xy 为右端点。"""
    x, y = xy
    widths = [d.textlength(c, font=font) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    if anchor_right:
        x -= total
    for c, w in zip(text, widths):
        d.text((x, y), c, font=font, fill=fill)
        x += w + tracking
    return x


def shadow_card(layer: Image.Image, box, radius=RADIUS, blur=16, alpha=38, offset=(0, 10)):
    """在卡片位置下方绘制柔和投影并合成到 layer（RGBA）。"""
    ox, oy = offset
    sh = Image.new("RGBA", layer.im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy], radius=radius, fill=(60, 50, 30, alpha)
    )
    layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


def divider(d: ImageDraw.ImageDraw, x, y, w):
    """带三点的细分隔线。"""
    d.line([x, y, x + w, y], fill="#EAE3D4", width=1)
    cx = x + w // 2
    for i in (-16, 0, 16):
        d.ellipse([cx + i - 2, y - 2, cx + i + 2, y + 2], fill="#E3DBC8")


def seg_cells(inner_w, total):
    """整行铺满的分段胶囊宽度。"""
    return max(20, int((inner_w - (total - 1) * SEG_GAP) / total))


def page_frame(d: ImageDraw.ImageDraw, w: int, h: int):
    """页面双线画框 + 四角金点，贴画布边缘。"""
    d.rectangle([FRAME, FRAME, w - FRAME, h - FRAME], outline=LINE, width=2)
    d.rectangle([FRAME + 10, FRAME + 10, w - FRAME - 10, h - FRAME - 10], outline="#EAE3D4", width=1)
    for cx, cy in [(FRAME, FRAME), (w - FRAME, FRAME), (FRAME, h - FRAME), (w - FRAME, h - FRAME)]:
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=GOLD)


def card_box(d: ImageDraw.ImageDraw, img: Image.Image, x, y, w, h):
    """一张白色圆角卡片：投影 + 描边底。"""
    shadow_card(img, (x, y, x + w, y + h))
    d.rounded_rectangle([x, y, x + w, y + h], radius=RADIUS, fill=CARD, outline="#EFE9DC", width=1)
