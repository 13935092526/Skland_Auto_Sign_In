# -*- coding: utf-8 -*-
"""t2i 展示层：森空岛签到原始数据 → endfield_checkin 模板图片 → 群机器人推送。

skland_endfield 只负责签到并把服务端原始状态交出来，本模块完成剩下的事：

    accounts = [build_account(record.role, record.status) for record in result.records]
    png      = render_report(accounts)          # t2i 模板出图
    push_report(png)                            # 企业微信群机器人只发 image，文字日志走 Actions 汇总

send_report() 是「数据 → 图片 → 推送」的一站式入口，run.py 直接调用。
推送密钥解析顺序（见 t2i/notify.py）：显式 webhook 参数 > 环境变量 WX_WEBHOOK
（兼容 WECOM_WEBHOOK / SKLAND_NOTIFICATION_URLS 首个 URL），本地开发时放项目根 .env。
"""

from __future__ import annotations

import calendar as _calendar
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .notify import push, send_wecom_text
from .registry import render_template

# 森空岛/终末地按东八区结算，签到状态里的 currentTs 为秒级时间戳
CN_TZ = timezone(timedelta(hours=8))
TEMPLATE_NAME = "endfield_checkin"


def _award_label(award_id: str, resource_info: dict[str, dict[str, Any]]) -> str:
    """把 awardId 映射成「奖励名×数量」，查不到时保留占位。"""
    info = resource_info.get(award_id or "") or {}
    name = info.get("name") or "未知奖励"
    count = info.get("count")
    return f"{name}×{count}" if isinstance(count, int) and count > 1 else name


def _month_start(status: dict[str, Any]) -> datetime:
    """报告所属月份：优先用服务端 currentTs（实测为秒级，兼容毫秒），缺失时退回本地东八区时间。"""
    ts = status.get("currentTs")
    if ts:
        try:
            value = int(ts)
            if value > 10 ** 11:  # 毫秒级时间戳
                value //= 1000
            return datetime.fromtimestamp(value, CN_TZ)
        except (ValueError, OSError, OverflowError):
            pass
    return datetime.now(CN_TZ)


def resolve_webhook(explicit: str | None = None) -> str:
    """按优先级解析推送 webhook：显式参数 > WX_WEBHOOK/WECOM_WEBHOOK > SKLAND_NOTIFICATION_URLS 首个。"""
    if explicit:
        return explicit
    from .notify import env_secret, WECOM_ENV
    url = env_secret(WECOM_ENV)
    if url:
        return url
    urls = [u.strip() for u in os.environ.get('SKLAND_NOTIFICATION_URLS', '').split(',') if u.strip()]
    return urls[0] if urls else ''


def build_account(
    role: dict[str, Any] | None,
    status: dict[str, Any] | None,
    anonymous: bool = False,
    fallback_name: str = "终末地角色",
) -> dict[str, Any] | None:
    """把单个角色的签到原始状态转成 endfield_checkin 模板的账号数据。

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
        print("[t2i] 没有可用的签到状态数据，跳过图片报告")
        return None
    target = Path(output) if output else Path(tempfile.gettempdir()) / "endfield_checkin.png"
    try:
        png = render_template(TEMPLATE_NAME, {"accounts": accounts}, output=target)
    except Exception as error:  # 渲染异常不能影响签到
        print(f"[t2i] 图片渲染失败: {error!r}")
        return None
    print(f"[t2i] 已生成签到日历报告: {png} ({png.stat().st_size} bytes)")
    return png


def push_report(png: Path | None, webhook: str | None = None) -> bool:
    """只把图片推送到企业微信群机器人（不推文字，日志留给 Actions 汇总）；未解析到 webhook 时跳过。"""
    url = resolve_webhook(webhook)
    if not url:
        print("[t2i] 未配置推送地址（WX_WEBHOOK / SKLAND_NOTIFICATION_URLS），跳过推送")
        return False
    if png is None:
        return False
    ok = push([png], webhook=url, wecom_only=True)
    print(f"[t2i] 图片推送{'成功' if ok else '未全部成功（详见上方通道日志）'}")
    return ok


def push_alert(text: str, webhook: str | None = None) -> bool:
    """签到失败时推送文字告警（唯一会推文字的场景，正常结果仍只发图片）。"""
    url = resolve_webhook(webhook)
    if not url:
        print("[t2i] 未配置推送地址，跳过失败告警推送（详见日志/Actions 汇总）")
        return False
    return send_wecom_text(text, url)


def send_report(accounts: list[dict[str, Any]], webhook: str | None = None,
                output: str | Path | None = None) -> bool:
    """数据 → 图片 → 推送的一站式入口（仅推送图片）。"""
    return push_report(render_report(accounts, output=output), webhook=webhook)
