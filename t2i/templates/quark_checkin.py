# -*- coding: utf-8 -*-
"""夸克网盘签到报告模板 · 现代百科全书 × 博物图鉴 × 杂志级信息设计。

由 t2i 接口调用（不单独运行）：
  from t2i import render_template
  render_template("quark_checkin", data, output="checkin.png")

JSON 参数（需要发送的字段）:
{
  "accounts": [                           # 必填，1 个或多个账号，每个账号一张白色卡片
    {
      "phone":        "139 3509 2526",    # 必填，字符串，绑定手机号
      "total_cur":    19.12,              # 必填，数值，网盘当前总容量 (GB)
      "checkin_cur":  9.12,               # 必填，数值，其中签到获得容量 (GB)，须 <= total_cur
      "today_gain":   "+20.00 MB",        # 必填，字符串，今日新增容量（原样展示）
      "streak_done":  6                   # 必填，整数，连签已完成天数（周期固定 7 天）
    }
  ]
}

页眉标题与日期由模板固定生成（标题自带，日期为当天），无需传参。

版式：手机竖版长图，宽度固定 1080、高度随内容；账号多到超高时画布自动加长。
每账号一张白色圆角卡片，卡片内一律上下堆叠：HUD 序号 + 手机号 / 容量标签行 +
整行容量条 + 图例行 / 今日新增大字 + 连签标签行 + 整行七格胶囊。全中文，无百分比、无期号、无页脚。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from ..fonts import load_font
from ..image_io import save
from ._style import (
    PAPER, CARD, INK, MUTED, LINE, GREEN, TERRA, GOLD, TECH,
    W, VPAD, MARGIN, PAD_IN, GAP, RADIUS, HEADER_H, SEG_GAP, SEG_H,
    spaced, divider, seg_cells, card_box, page_frame,
)

# ---------------------------------------------------------------- 模板专属度量
TITLE = "夸克网盘 · 每日签到报告"
STREAK_TOTAL = 7                # 连签周期固定 7 天
SEC_TITLE_H = 104               # 小节标题（含短色标线）
CAP_H = 178                     # 容量：标签行 + 条 + 图例行
STREAK_H = 244                  # 今日签到：大字 + 标签行 + 胶囊行
GAP_LINE = 44                   # 分隔线上下留白
BAR_H = 44
HUD_PAD = 14
HUD_GAP = 40


def sub_header(d, x, y, cn, accent, fonts):
    d.text((x, y), cn, font=fonts["seccn"], fill=INK)
    d.line([x, y + 68, x + 62, y + 68], fill=accent, width=4)
    return y + SEC_TITLE_H


def hud_number(d, x, y, num, fonts, color=TECH):
    """HUD 取景框序号：四角直角标 + DIN 数字。返回 (宽, 高)。"""
    f = fonts["serial"]
    txt = f"{num:02d}"
    bb = d.textbbox((0, 0), txt, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x0, y0, x1, y1 = x, y, x + w + 2 * HUD_PAD, y + h + 2 * HUD_PAD
    L = 16
    for cx, cy, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([cx, cy, cx + dx * L, cy], fill=color, width=3)
        d.line([cx, cy, cx, cy + dy * L], fill=color, width=3)
    d.text((x + HUD_PAD - bb[0], y + HUD_PAD - bb[1]), txt, font=f, fill=color)
    return x1 - x0, y1 - y0


def hud_height(fonts):
    """HUD 取景框高度（测量用，与实际绘制一致）。"""
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bb = d.textbbox((0, 0), "01", font=fonts["serial"])
    return bb[3] - bb[1] + 2 * HUD_PAD


def card_height(fonts):
    return PAD_IN + hud_height(fonts) + HUD_GAP + GAP_LINE + SEC_TITLE_H + CAP_H + GAP_LINE \
        + SEC_TITLE_H + STREAK_H + PAD_IN


def draw_capacity(d, cx, cy, inner_w, fonts, total_cur, checkin):
    """标签行 + 整行容量条 + 图例行。整条=总容量，橙色段=签到获得。"""
    f_body, f_small = fonts["body"], fonts["small"]
    d.text((cx, cy), "网盘容量", font=f_body, fill=INK)
    val = f"签到 {checkin:.2f} / {total_cur:.2f} GB"
    d.text((cx + inner_w, cy + 25), val, font=f_small, fill=MUTED, anchor="rm")

    by = cy + 50 + 22
    pct_ck = min(checkin / total_cur, 1.0) if total_cur else 0.0
    d.rounded_rectangle([cx, by, cx + inner_w, by + BAR_H], radius=BAR_H // 2, fill=GREEN)
    cw = max(BAR_H, int(inner_w * pct_ck))
    d.rounded_rectangle([cx, by, cx + cw, by + BAR_H], radius=BAR_H // 2, fill=TERRA)

    ly = by + BAR_H + 22
    lx = cx
    d.rounded_rectangle([lx, ly + 4, lx + 28, ly + 28], radius=9, fill=TERRA)
    t1 = f"签到获得 {checkin:.2f} GB"
    d.text((lx + 38, ly), t1, font=f_small, fill=MUTED)
    lx += 38 + d.textlength(t1, font=f_small) + 48
    d.rounded_rectangle([lx, ly + 4, lx + 28, ly + 28], radius=9, fill=GREEN)
    d.text((lx + 38, ly), f"其他容量 {total_cur - checkin:.2f} GB", font=f_small, fill=MUTED)


def draw_account_card(img, d, fonts, acc, y, mx, mw, idx):
    """一张账号卡片。返回卡片高度。"""
    inner_w = mw - 2 * PAD_IN
    cx = mx + PAD_IN
    h = card_height(fonts)
    card_box(d, img, mx, y, mw, h)

    cy = y + PAD_IN
    _, bh = hud_number(d, cx, cy, idx, fonts)
    d.text((mx + mw - PAD_IN, cy + bh // 2), acc["phone"], font=fonts["phone"], fill=INK, anchor="rm")
    cy += bh + HUD_GAP
    divider(d, cx, cy, inner_w)
    cy += GAP_LINE

    cy = sub_header(d, cx, cy, "容量进度", GREEN, fonts)
    draw_capacity(d, cx, cy, inner_w, fonts, float(acc["total_cur"]), float(acc["checkin_cur"]))
    cy += CAP_H + GAP_LINE
    divider(d, cx, cy, inner_w)
    cy += GAP_LINE

    cy = sub_header(d, cx, cy, "今日签到", TERRA, fonts)
    gain = acc["today_gain"]
    d.text((cx, cy - 6), gain, font=fonts["big"], fill=TERRA)
    gw = d.textlength(gain, font=fonts["big"])
    d.text((cx + gw + 22, cy + 56), "今日新增容量", font=fonts["small"], fill=MUTED)

    sy = cy + 130
    d.text((cx, sy), "连签进度", font=fonts["small"], fill=MUTED)
    d.text((cx + inner_w, sy + 18), f'{acc["streak_done"]}/{STREAK_TOTAL}',
           font=fonts["small"], fill=TERRA, anchor="rm")
    seg_w = seg_cells(inner_w, STREAK_TOTAL)
    for i in range(STREAK_TOTAL):
        x0 = cx + i * (seg_w + SEG_GAP)
        box = [x0, sy + 54, x0 + seg_w, sy + 54 + SEG_H]
        if i < int(acc["streak_done"]):
            d.rounded_rectangle(box, radius=SEG_H // 2, fill=TERRA)
        else:
            d.rounded_rectangle(box, radius=SEG_H // 2, outline=LINE, width=2)
    return h


def render_card(data: dict, output) -> Path:
    fonts = {
        "eyebrow": load_font(24, "yahei"),
        "serial": load_font(52, "bahnschrift"),
        "phone": load_font(34, "yahei"),
        "seccn": load_font(40, "song", bold=True),
        "body": load_font(38, "yahei"),
        "small": load_font(27, "yahei"),
        "big": load_font(78, "times"),
    }

    mx = MARGIN
    mw = W - 2 * MARGIN
    acc_h = card_height(fonts)
    n = len(data["accounts"])
    content_h = HEADER_H + n * acc_h + (n - 1) * GAP
    H = content_h + VPAD * 2
    y = VPAD

    img = Image.new("RGBA", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # ---- 页眉（左侧系列名，右侧日期）
    spaced(d, (mx, y), TITLE, fonts["eyebrow"], MUTED)
    spaced(d, (W - mx, y), date.today().isoformat(), fonts["eyebrow"], GOLD, tracking=4, anchor_right=True)
    d.line([mx, y + 56, W - mx, y + 56], fill=LINE, width=1)
    y += HEADER_H

    # ---- 逐账号绘制白色卡片
    for i, acc in enumerate(data["accounts"], 1):
        y += draw_account_card(img, d, fonts, acc, y, mx, mw, i) + GAP

    # ---- 页面画框（双线 + 金角点，贴画布边缘）
    page_frame(d, W, H)
    return save(img, output)


REQUIRED = ("phone", "total_cur", "checkin_cur", "today_gain", "streak_done")


def validate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("顶层必须是 JSON 对象")
    accs = data.get("accounts")
    if not isinstance(accs, list) or not accs:
        raise ValueError("accounts 必须是非空数组")
    for i, acc in enumerate(accs, 1):
        missing = [k for k in REQUIRED if k not in acc]
        if missing:
            raise ValueError(f"accounts[{i}] 缺少字段: {', '.join(missing)}")
        if float(acc["checkin_cur"]) > float(acc["total_cur"]):
            raise ValueError(f"accounts[{i}] checkin_cur 不能大于 total_cur")
        if not 0 <= int(acc["streak_done"]) <= STREAK_TOTAL:
            raise ValueError(f"accounts[{i}] streak_done 须在 0-{STREAK_TOTAL} 之间")
    return data
