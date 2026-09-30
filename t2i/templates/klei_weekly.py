# -*- coding: utf-8 -*-
"""科雷游戏掉落报告模板 · 现代百科全书 × 博物图鉴 × 杂志级信息设计（与夸克签到模板同系列）。

由 t2i 接口调用（不单独运行）：
  from t2i import render_template
  render_template("klei_weekly", data, output="klei.png")

JSON 参数（需要发送的字段）:
{
  "deadline": "2026-10-01T18:00:00",        # 必填，本周掉落截止时间（ISO 本地时间），用于算剩余时长
  "games": [                                # 必填，1 个或多个游戏，每个两行：名称+计数 / 胶囊独占整行
    {"name": "饥荒", "weekly_done": 4, "weekly_total": 8}
  ],
  "gifts": [                                # 必填，当天收获的礼物，可为空数组，每个两行：名称+时间 / 标签
    {"item": "Smelter's Boots", "game": "饥荒", "kind": "每周", "time": "10:32"}
  ]
}

页眉标题与日期由模板固定生成，无需传参。不显示线轴、线卷、科雷点数等账户货币。

版式：手机竖版长图，宽度固定 1080、高度随内容；内容超高时画布自动加长。游戏配色按
games 顺序取自色板（陶土橙/深钢蓝/苔绿/金）。
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw

from ..fonts import load_font
from ..image_io import save
from ._style import (
    PAPER, INK, MUTED, LINE, GREEN, TERRA, GOLD, TECH,
    W, VPAD, MARGIN, PAD_IN, GAP, HEADER_H, SEG_GAP, SEG_H,
    spaced, divider, seg_cells, card_box, page_frame,
)

# ---------------------------------------------------------------- 模板专属配色与度量
TITLE = "科雷游戏 · 每周掉落报告"
KIND_COLOR = {"每日": GREEN, "每周": TERRA}
GAME_PALETTE = [TERRA, TECH, GREEN, GOLD]
CHIP = "#F2EEE4"   # 浅色标签底

ROW_H = 150                     # 礼物块：名称行 + 标签行
ROW_GAP = 150                   # 游戏块：名称行 + 胶囊行
DEADLINE_H = 140                # 截止块：标签行 + 数值行


def card_title(d, x, y, cn, accent, fonts):
    d.text((x, y), cn, font=fonts["seccn"], fill=INK)
    d.line([x, y + 68, x + 62, y + 68], fill=accent, width=4)
    return y + 104


def chip(d, x, cy, text, font, fg, bg):
    """左对齐圆角标签，返回右边缘 x。"""
    w = d.textlength(text, font=font) + 34
    d.rounded_rectangle([x, cy - 22, x + w, cy + 22], radius=22, fill=bg)
    d.text((x + w / 2, cy), text, font=font, fill=fg, anchor="mm")
    return x + w


def weekly_card(img, d, fonts, data, y, mx, mw, game_colors):
    inner_w = mw - 2 * PAD_IN
    cx = mx + PAD_IN
    n = len(data["games"])
    h = PAD_IN + 104 + n * ROW_GAP + 44 + DEADLINE_H + PAD_IN
    card_box(d, img, mx, y, mw, h)

    cy = y + PAD_IN
    cy = card_title(d, cx, cy, "每周掉落", TERRA, fonts)
    for g in data["games"]:
        color = game_colors[g["name"]]
        seg_w = seg_cells(inner_w, int(g["weekly_total"]))
        d.text((cx, cy), g["name"], font=fonts["body"], fill=INK)
        d.text((cx + inner_w, cy + 25), f'{g["weekly_done"]} / {g["weekly_total"]}',
               font=fonts["body"], fill=color, anchor="rm")
        for i in range(int(g["weekly_total"])):
            x0 = cx + i * (seg_w + SEG_GAP)
            box = [x0, cy + 62, x0 + seg_w, cy + 62 + SEG_H]
            if i < int(g["weekly_done"]):
                d.rounded_rectangle(box, radius=SEG_H // 2, fill=color)
            else:
                d.rounded_rectangle(box, radius=SEG_H // 2, outline=LINE, width=2)
        cy += ROW_GAP

    divider(d, cx, cy + 4, inner_w)
    dy = cy + 44
    d.text((cx, dy), "本周掉落截止", font=fonts["small"], fill=MUTED)
    d.text((cx, dy + 50), data["deadline_cn"], font=fonts["body"], fill=INK)
    d.text((cx + inner_w, dy + 75), data["remaining"], font=fonts["small"], fill=TERRA, anchor="rm")
    return h


def gift_card(img, d, fonts, data, y, mx, mw, game_colors):
    inner_w = mw - 2 * PAD_IN
    cx = mx + PAD_IN
    gifts = data["gifts"]
    last_row = (len(gifts) - 1) * ROW_H + 114 if gifts else 48
    h = PAD_IN + 104 + last_row + PAD_IN
    card_box(d, img, mx, y, mw, h)

    cy = y + PAD_IN
    cy = card_title(d, cx, cy, "今日收获", GREEN, fonts)
    if not gifts:
        d.text((cx, cy + 8), "今日暂无礼物收获", font=fonts["body"], fill=MUTED)
        return h

    for i, g in enumerate(gifts):
        ry = cy + i * ROW_H
        d.text((cx, ry), g["item"], font=fonts["body"], fill=INK)
        d.text((cx + inner_w, ry + 25), g["time"], font=fonts["small"], fill=MUTED, anchor="rm")
        tx = chip(d, cx, ry + 92, g["game"], fonts["chip"], "#FFFFFF", game_colors[g["game"]])
        chip(d, tx + 14, ry + 92, g["kind"], fonts["chip"], KIND_COLOR[g["kind"]], CHIP)
        if i < len(gifts) - 1:
            d.line([cx, ry + ROW_H - 26, cx + inner_w, ry + ROW_H - 26], fill="#F4F0E7", width=1)
    return h


def render_card(data: dict, output) -> Path:
    game_colors = {g["name"]: GAME_PALETTE[i % len(GAME_PALETTE)] for i, g in enumerate(data["games"])}
    data = dict(data, game_colors=game_colors, **fmt_deadline(data["deadline"]))

    fonts = {
        "eyebrow": load_font(24, "yahei"),
        "seccn": load_font(40, "song", bold=True),
        "body": load_font(38, "yahei"),
        "small": load_font(27, "yahei"),
        "chip": load_font(25, "yahei"),
    }

    n_games, n_gifts = len(data["games"]), len(data["gifts"])
    card1_h = PAD_IN + 104 + n_games * ROW_GAP + 44 + DEADLINE_H + PAD_IN
    card2_h = PAD_IN + 104 + ((n_gifts - 1) * ROW_H + 114 if n_gifts else 48) + PAD_IN
    content_h = HEADER_H + card1_h + GAP + card2_h
    H = content_h + VPAD * 2
    y = VPAD

    img = Image.new("RGBA", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # ---- 页眉（左侧标题，右侧日期）
    x = MARGIN
    spaced(d, (x, y), TITLE, fonts["eyebrow"], MUTED)
    spaced(d, (W - x, y), date.today().isoformat(), fonts["eyebrow"], GOLD, tracking=4, anchor_right=True)
    d.line([x, y + 56, W - x, y + 56], fill=LINE, width=1)
    y += HEADER_H

    mx, mw = x, W - 2 * x
    y += weekly_card(img, d, fonts, data, y, mx, mw, game_colors) + GAP
    gift_card(img, d, fonts, data, y, mx, mw, game_colors)

    # ---- 页面画框（双线 + 金角点，贴画布边缘）
    page_frame(d, W, H)
    return save(img, output)


def fmt_deadline(iso: str) -> dict:
    dt = datetime.fromisoformat(iso)
    delta = dt - datetime.now()
    if delta.total_seconds() <= 0:
        remaining = "本周掉落已结束"
    else:
        mins = int(delta.total_seconds() // 60)
        days, rem = divmod(mins, 1440)
        hours, mins = divmod(rem, 60)
        remaining = (f"剩余 {days}天{hours}小时" if days else f"剩余 {hours}小时{mins}分")
    return {
        "deadline_cn": f"{dt.year}年{dt.month:02d}月{dt.day:02d}日 {dt.hour:02d}:{dt.minute:02d}",
        "remaining": remaining,
    }


def validate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("顶层必须是 JSON 对象")
    games = data.get("games")
    if not isinstance(games, list) or not games:
        raise ValueError("games 必须是非空数组")
    for g in games:
        missing = [k for k in ("name", "weekly_done", "weekly_total") if k not in g]
        if missing:
            raise ValueError(f"games[{g.get('name', '?')}] 缺少字段: {', '.join(missing)}")
        if not 1 <= int(g["weekly_total"]) <= 12:
            raise ValueError(f"games[{g['name']}] weekly_total 须在 1-12 之间")
        if not 0 <= int(g["weekly_done"]) <= int(g["weekly_total"]):
            raise ValueError(f"games[{g['name']}] weekly_done 须在 0-{g['weekly_total']} 之间")
    gifts = data.get("gifts")
    if not isinstance(gifts, list):
        raise ValueError("gifts 必须是数组（当天无收获时传空数组）")
    names = {g["name"] for g in games}
    for gft in gifts:
        missing = [k for k in ("item", "game", "kind", "time") if k not in gft]
        if missing:
            raise ValueError(f"gifts[{gft.get('item', '?')}] 缺少字段: {', '.join(missing)}")
        if gft["kind"] not in KIND_COLOR:
            raise ValueError(f'gifts[{gft["item"]}] kind 只能是 "每日" 或 "每周"')
        if gft["game"] not in names:
            raise ValueError(f'gifts[{gft["item"]}] game "{gft["game"]}" 未出现在 games 中')
    try:
        fmt_deadline(data["deadline"])
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"deadline 缺失或不是 ISO 时间格式: {e}")
    return data
