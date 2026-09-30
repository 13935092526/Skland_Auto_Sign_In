# -*- coding: utf-8 -*-
"""签到状态数据 → 图片报告 → 企业微信推送（使用仓库内嵌的 t2i 渲染库）。

三段职责都在本模块，main.py 只在签到过程中把每个角色拿到的原始签到状态交过来：

    account = build_account(character.role, result.status)   # API 数据 -> 模板数据
    png     = render_report(accounts)                        # t2i 模板 endfield_checkin 出图
    push_report(png, text_summary)                           # 企业微信群机器人 image

推送密钥由 t2i.notify 统一解析：显式参数 > 环境变量 WX_WEBHOOK（兼容 WECOM_WEBHOOK），
本地开发时也可放项目根 .env。未配置密钥、渲染或推送失败都只打日志，
不影响签到结果，也不影响原有的 SKLAND_NOTIFICATION_URLS 文字通知。
"""

from __future__ import annotations

import calendar as _calendar
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from t2i import render_template

# 森空岛/终末地按东八区结算，签到状态里的 currentTs 为毫秒时间戳
CN_TZ = timezone(timedelta(hours=8))
TEMPLATE_NAME = "endfield_checkin"
REPORT_TITLE = "终末地 · 每日签到报告"


def _award_label(award_id: str, resource_info: dict[str, dict[str, Any]]) -> str:
    """把 awardId 映射成「奖励名×数量」，查不到时保留占位。"""
    info = resource_info.get(award_id or "") or {}
    name = info.get("name") or "未知奖励"
    count = info.get("count")
    return f"{name}×{count}" if isinstance(count, int) and count > 1 else name


def _month_start(status: dict[str, Any]) -> datetime:
    """报告所属月份：优先用服务端 currentTs，缺失时退回本地东八区时间。"""
    ts = status.get("currentTs")
    if ts:
        try:
            return datetime.fromtimestamp(int(ts) / 1000, CN_TZ)
        except (ValueError, OSError, OverflowError):
            pass
    return datetime.now(CN_TZ)


def build_account(
    role: dict[str, Any] | None,
    status: dict[str, Any] | None,
    anonymous: bool = False,
    fallback_name: str = "终末地角色",
) -> dict[str, Any] | None:
    """把单个角色的签到状态转成 endfield_checkin 模板的账号数据。

    服务端 calendar 是「当月按日期顺序」的列表，故下标 +1 即日期：
      done  -> 已签到，格子里显示当日所得奖励
      其余  -> item 留空，由模板按已过/未到自动显示 未签到 / 可领取
    数据缺失（如签到接口异常）时返回 None，调用方跳过该角色。
    """
    if not isinstance(status, dict):
        return None
    days = status.get("calendar")
    if not isinstance(days, list) or not days:
        return None

    now = _month_start(status)
    dim = _calendar.monthrange(now.year, now.month)[1]
    resource_info = status.get("resourceInfoMap") or {}

    entries: list[dict[str, Any]] = []
    for index, item in enumerate(days, 1):
        if index > dim or not isinstance(item, dict):
            break
        done = bool(item.get("done"))
        entries.append({
            "day": index,
            "signed": done,
            "item": _award_label(item.get("awardId"), resource_info) if done else "",
        })
    if not entries:
        return None

    role = role or {}
    nickname = "管理员" if anonymous else (role.get("nickname") or fallback_name)
    return {
        "nickname": nickname,
        "uid": str(role.get("roleId") or "未知"),
        "hasToday": bool(status.get("hasToday")),
        "month": f"{now.year:04d}-{now.month:02d}",
        "calendar": entries,
    }


def render_report(accounts: list[dict[str, Any]], output: str | Path | None = None) -> Path | None:
    """渲染签到日历报告图片；失败只打日志并返回 None（不影响签到结果）。"""
    if not accounts:
        print("[report] 没有可用的签到状态数据，跳过图片报告")
        return None
    target = Path(output) if output else Path(tempfile.gettempdir()) / "endfield_checkin.png"
    try:
        png = render_template(TEMPLATE_NAME, {"accounts": accounts}, output=target)
    except Exception as error:  # 渲染异常不能影响签到
        print(f"[report] 图片渲染失败: {error!r}")
        return None
    print(f"[report] 已生成签到日历报告: {png} ({png.stat().st_size} bytes)")
    return png


def push_report(png: Path | None, text: str = "", webhook: str | None = None) -> bool:
    """把图片推送到企业微信群机器人；未配置 webhook 时跳过。"""
    if png is None:
        return False
    from t2i import push
    ok = push([png], title=REPORT_TITLE, text=text, webhook=webhook, wecom_only=True)
    print(f"[report] 图片推送{'成功' if ok else '未全部成功（详见上方通道日志）'}")
    return ok


def send_report(accounts: list[dict[str, Any]], text: str = "") -> bool:
    """数据 → 图片 → 推送的一站式入口。"""
    return push_report(render_report(accounts), text=text)
