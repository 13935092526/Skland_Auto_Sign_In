# -*- coding: utf-8 -*-
"""明日方舟：终末地签到日历报告模板 · 与夸克签到同风格（纸质浅底 + 白色卡片 + 双线画框）。

由 t2i 接口调用（不单独运行）：
  from t2i import render_template
  render_template("endfield_checkin", data, output="endfield.png")

JSON 参数（需要发送的字段）:
{
  "accounts": [                           # 必填，1 个或多个账号，每个账号一张白色卡片
    {
      "nickname":  "深巡的罗德岛",         # 必填，字符串，账号昵称（卡片头部大字）
      "uid":       "100012345",           # 必填，字符串或整数，账号 UID
      "hasToday":  true,                  # 必填，布尔，今日是否已签到
      "month":     "2026-09",             # 选填，YYYY-MM；缺省取服务器当月
      "days_in_month": 30,                # 选填，本月天数（28-31），缺省按日历推算
      "calendar": [                       # 必填，非空；本月每天签到所得（可只给已签的日期）
        {"day": 1, "signed": true,  "item": "基准寻访参"},   # day 必填(1-31)、
        {"day": 2, "signed": true,  "item": "息壤样本"},     # signed 必填布尔、
        {"day": 3, "signed": false, "item": "合成材料"}      # item 选填，缺省时格子自动显示
                                                              # 已签到/未签到/可领取
      ]
    }
  ]
}

日历格子规则：
  - signed=true            → 陶土橙实底 + 白色奖励名（今天额外加金框）
  - signed=false 且已过    → 描边空格 + 灰字"未签到"（item 存在时仍显示 item）
  - signed=false 且在未来  → 描边空格 + 金棕"可领取"（item 存在时仍显示 item）
  - calendar 未覆盖的日期  → 纸质色空格（未追踪）
页眉标题与日期由模板固定生成（日期为当天），无需传参。
"""
from __future__ import annotations

import calendar as _calendar
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from ..fonts import load_font
from ..image_io import save
from ._style import (
    PAPER, CARD, INK, MUTED, LINE, GREEN, TERRA, GOLD, TECH,
    W, VPAD, MARGIN, PAD_IN, GAP, HEADER_H,
    spaced, divider, card_box, page_frame,
)

# ---------------------------------------------------------------- 模板专属度量
TITLE = "终末地 · 每日签到报告"
COLS = 7                       # 星期一 ~ 星期日
CELL_GAP = 10                  # 格子间距
CELL_H = 118                   # 格子高度（日期号 + 奖励名）
CELL_LINE_H = 34               # 奖励名折行行高
WEEK_H = 46                    # 星期表头高度
SEC_TITLE_H = 104
GAP_LINE = 44
HUD_PAD = 14
HUD_GAP = 40
HEAD_H = 96                    # 昵称行 + UID 行
SUMMARY_H = 52                 # 月份/已签天数摘要行

_WEEKDAYS = ("一", "二", "三", "四", "五", "六", "日")


def sub_header(d, x, y, cn, accent, fonts):
    d.text((x, y), cn, font=fonts["seccn"], fill=INK)
    d.line([x, y + 68, x + 62, y + 68], fill=accent, width=4)
    return y + SEC_TITLE_H


def hud_number(d, x, y, num, fonts, color=TECH):
    """HUD 取景框序号：四角直角标 + 数字。返回 (宽, 高)。"""
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


def truncate(d, text, font, max_w):
    """按像素宽度截断文本，超出加省略号。"""
    if d.textlength(text, font=font) <= max_w:
        return text
    out = ""
    for ch in text:
        if d.textlength(out + ch + "…", font=font) > max_w:
            break
        out += ch
    return out + "…"


def wrap_lines(d, text, font, max_w, max_lines=2):
    """把文本按像素宽度折成最多 max_lines 行，装不下的部分以 … 结尾。"""
    lines, rest = [], text
    while rest and len(lines) < max_lines:
        if d.textlength(rest, font=font) <= max_w:
            lines.append(rest)
            break
        n = len(rest)
        while n > 1 and d.textlength(rest[:n], font=font) > max_w:
            n -= 1
        if len(lines) == max_lines - 1:            # 最后一行：给省略号留位
            while n > 1 and d.textlength(rest[:n] + "…", font=font) > max_w:
                n -= 1
            lines.append(rest[:n] + "…")
            rest = ""
        else:
            lines.append(rest[:n])
            rest = rest[n:]
    return lines or [""]


def status_pill(d, right_x, cy, done, fonts):
    """右上角今日状态胶囊（右对齐到 right_x）。"""
    label = "今日已签到" if done else "今日未签到"
    color = GREEN if done else TERRA
    f = fonts["phone"]
    tw = d.textlength(label, font=f)
    pad_x, h = 26, 56
    x1 = right_x
    x0 = x1 - tw - pad_x * 2
    y0, y1 = cy, cy + h
    if done:
        d.rounded_rectangle([x0, y0, x1, y1], radius=h // 2, fill=color)
    else:
        d.rounded_rectangle([x0, y0, x1, y1], radius=h // 2, outline=color, width=2)
    d.text(((x0 + x1) // 2, y0 + 9), label, font=f, fill=CARD if done else color, anchor="ma")
    return x0, y1


def cell_layout(inner_w):
    cw = int((inner_w - (COLS - 1) * CELL_GAP) / COLS)
    return cw, inner_w - (cw * COLS + (COLS - 1) * CELL_GAP)


def month_days(acc: dict) -> int:
    if acc.get("days_in_month"):
        return int(acc["days_in_month"])
    y, m = acc["_month"]
    return _calendar.monthrange(y, m)[1]


def card_height(fonts, inner_w, rows):
    _, extra = cell_layout(inner_w)
    return (PAD_IN + HEAD_H + GAP_LINE
            + SEC_TITLE_H + SUMMARY_H + WEEK_H + rows * CELL_H + (rows - 1) * CELL_GAP
            + PAD_IN + extra)


def draw_calendar(d, cx, gy, inner_w, fonts, acc, today, days):
    """7 列月历签到表；gy 为星期表头顶部。返回表格底部 y。"""
    y, m = acc["_month"]
    cw, extra = cell_layout(inner_w)

    # ---- 星期表头（整行铺满）
    for i, wd in enumerate(_WEEKDAYS):
        x0 = cx + i * (cw + CELL_GAP)
        d.rounded_rectangle([x0, gy, x0 + cw + (extra if i == COLS - 1 else 0), gy + WEEK_H],
                            radius=12, fill="#EFE9DC")
        d.text((x0 + cw // 2, gy + 9), wd, font=fonts["small"], fill=MUTED, anchor="ma")
    gy += WEEK_H + CELL_GAP

    first_wd = date(y, m, 1).weekday()          # 0=周一
    day_map = {int(e["day"]): e for e in acc["calendar"]}
    rows = -(-(first_wd + days) // COLS)        # 向上取整
    is_this_month = (y, m) == (today.year, today.month)
    is_past = (y, m) < (today.year, today.month)

    for day in range(1, days + 1):
        entry = day_map.get(day)
        if entry is None:
            continue
        idx = first_wd + day - 1
        col, row = idx % COLS, idx // COLS
        x0 = cx + col * (cw + CELL_GAP)
        y0 = gy + row * (CELL_H + CELL_GAP)
        box = [x0, y0, x0 + cw, y0 + CELL_H]
        signed = bool(entry["signed"])
        is_today = is_this_month and day == today.day

        if signed:
            d.rounded_rectangle(box, radius=16, fill=TERRA)
            day_fill, item_fill = "#F6E3D6", CARD
            label = entry["item"] or "已签到"
        else:
            d.rounded_rectangle(box, radius=16, fill=PAPER, outline=LINE, width=2)
            day_fill = MUTED
            # 已过未签 → 未签到；未到期 → 可领取
            missed = is_past or (is_this_month and day <= today.day)
            label = entry["item"] or ("未签到" if missed else "可领取")
            item_fill = MUTED if missed else GOLD
        d.text((x0 + 14, y0 + 8), str(day), font=fonts["mini"], fill=day_fill)
        lines = wrap_lines(d, label, fonts["cell"], cw - 14)
        block = len(lines) * CELL_LINE_H
        top = y0 + 30 + ((CELL_H - 30) - block) // 2
        for k, ln in enumerate(lines):
            d.text((x0 + cw // 2, top + k * CELL_LINE_H + CELL_LINE_H // 2), ln,
                   font=fonts["cell"], fill=item_fill, anchor="mm")

        if is_today:
            d.rounded_rectangle([x0 - 3, y0 - 3, x0 + cw + 3, y0 + CELL_H + 3],
                                radius=19, outline=GOLD, width=3)
            d.rounded_rectangle([x0 + cw - 40, y0 + 4, x0 + cw - 8, y0 + 32],
                                radius=12, fill=GOLD)
            d.text((x0 + cw - 24, y0 + 8), "今", font=fonts["mini"], fill=CARD, anchor="ma")

    return gy + rows * (CELL_H + CELL_GAP)


def draw_account_card(img, d, fonts, acc, y, mx, mw, idx, today):
    """一张账号卡片（头部 + 月历签到表）。返回卡片高度。"""
    inner_w = mw - 2 * PAD_IN
    cx = mx + PAD_IN
    h = card_height(fonts, inner_w, acc["_rows"])
    card_box(d, img, mx, y, mw, h)

    cy = y + PAD_IN
    hw, _hh = hud_number(d, cx, cy + 4, idx, fonts)
    nx = cx + hw + HUD_GAP
    # 昵称预留右侧胶囊空间，过长截断
    name_w = max(120, (mx + mw - PAD_IN) - nx - 260)
    d.text((nx, cy), truncate(d, acc["nickname"], fonts["phone"], name_w), font=fonts["phone"], fill=INK)
    d.text((nx, cy + 52), f'UID {acc["uid"]}', font=fonts["small"], fill=MUTED)
    status_pill(d, mx + mw - PAD_IN, cy + 14, acc["_has_today"], fonts)
    cy += HEAD_H
    divider(d, cx, cy, inner_w)
    cy += GAP_LINE

    cy = sub_header(d, cx, cy, f'{acc["_month_label"]}签到日历', GREEN, fonts)
    days = month_days(acc)
    signed_n = sum(1 for e in acc["calendar"] if e["signed"])
    d.text((cx, cy + 6), f"已签 {signed_n}/{days} 天", font=fonts["body"], fill=INK)
    gain = sum(1 for e in acc["calendar"] if e["signed"] and e["item"])
    d.text((cx + inner_w, cy + 12), f"已获得奖励 {gain} 项",
           font=fonts["small"], fill=MUTED, anchor="rm")
    cy += SUMMARY_H

    bottom = draw_calendar(d, cx, cy, inner_w, fonts, acc, today, days)
    return max(h, bottom - y + PAD_IN)


def render_card(data: dict, output) -> Path:
    fonts = {
        "eyebrow": load_font(24, "yahei"),
        "serial": load_font(44, "yahei", bold=True),
        "phone": load_font(34, "yahei"),
        "seccn": load_font(40, "song", bold=True),
        "body": load_font(32, "yahei"),
        "small": load_font(27, "yahei"),
        "mini": load_font(24, "yahei"),
        "cell": load_font(24, "yahei"),
    }
    today = date.today()

    mx = MARGIN
    mw = W - 2 * MARGIN
    inner_w = mw - 2 * PAD_IN
    n = len(data["accounts"])
    heights = [card_height(fonts, inner_w, acc["_rows"]) for acc in data["accounts"]]
    H = HEADER_H + VPAD * 2 + sum(heights) + (n - 1) * GAP
    y = VPAD

    img = Image.new("RGBA", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # ---- 页眉（左侧系列名，右侧日期）
    spaced(d, (mx, y), TITLE, fonts["eyebrow"], MUTED)
    spaced(d, (W - mx, y), today.isoformat(), fonts["eyebrow"], GOLD, tracking=4, anchor_right=True)
    d.line([mx, y + 56, W - mx, y + 56], fill=LINE, width=1)
    y += HEADER_H

    # ---- 逐账号绘制白色卡片
    for i, acc in enumerate(data["accounts"], 1):
        y += draw_account_card(img, d, fonts, acc, y, mx, mw, i, today) + GAP

    # ---- 页面画框（双线 + 金角点，贴画布边缘）
    page_frame(d, W, H)
    return save(img, output)


REQUIRED = ("nickname", "uid", "hasToday", "calendar")


def _truthy_flag(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on", "已签到", "是")
    return False


def validate(data: dict) -> dict:
    """校验并补全：把账号数据清洗成渲染就绪形态（带下划线的键为本函数派生）。"""
    if not isinstance(data, dict):
        raise ValueError("顶层必须是 JSON 对象")
    accs = data.get("accounts")
    if not isinstance(accs, list) or not accs:
        raise ValueError("accounts 必须是非空数组")

    today = date.today()
    out = []
    for i, acc in enumerate(accs, 1):
        if not isinstance(acc, dict):
            raise ValueError(f"accounts[{i}] 必须是对象")
        missing = [k for k in REQUIRED if acc.get(k) in (None, "")]
        if missing:
            raise ValueError(f"accounts[{i}] 缺少字段: {', '.join(missing)}")
        if not isinstance(acc["calendar"], list) or not acc["calendar"]:
            raise ValueError(f"accounts[{i}] calendar 必须是非空数组")

        month = str(acc.get("month") or f"{today.year:04d}-{today.month:02d}")
        try:
            y, m = (int(p) for p in month.split("-")[:2])
            if not (1 <= m <= 12):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError(f"accounts[{i}] month 须为 YYYY-MM 格式，当前 {month!r}") from None

        entries = []
        for j, e in enumerate(acc["calendar"], 1):
            if not isinstance(e, dict) or "day" not in e or "signed" not in e:
                raise ValueError(f"accounts[{i}] calendar[{j}] 必须含 day 与 signed")
            day = int(e["day"])
            if not 1 <= day <= 31:
                raise ValueError(f"accounts[{i}] calendar[{j}] day 须在 1-31 之间")
            entries.append({"day": day, "signed": _truthy_flag(e["signed"]),
                            "item": (str(e["item"]).strip() if e.get("item") else "")})

        dim = acc.get("days_in_month")
        dim = int(dim) if dim else _calendar.monthrange(y, m)[1]
        if not 28 <= dim <= 31:
            raise ValueError(f"accounts[{i}] days_in_month 须在 28-31 之间")
        bad = [e["day"] for e in entries if e["day"] > dim]
        if bad:
            raise ValueError(f"accounts[{i}] calendar 日期超出本月天数({dim}): {bad}")

        # 今日状态以 calendar 中"今天"那条为准，避免胶囊与日历矛盾
        has_today = _truthy_flag(acc["hasToday"])
        if (y, m) == (today.year, today.month):
            tday = next((e for e in entries if e["day"] == today.day), None)
            if tday is not None:
                has_today = tday["signed"]
            elif has_today:
                raise ValueError(f"accounts[{i}] hasToday=true 但 calendar 中没有今天({today.day}日)的记录")

        rows = -(-(date(y, m, 1).weekday() + dim) // COLS)   # 月历实际行数（向上取整）
        out.append({**acc, "days_in_month": dim, "calendar": entries,
                    "_month": (y, m), "_month_label": f"{y}年{m}月",
                    "_rows": rows, "_has_today": has_today})
    return {"accounts": out}
