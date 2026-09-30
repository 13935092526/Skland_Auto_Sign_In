"""终末地签到处理器。

合并原项目中以下文件的能力：
- utils/format.ts            角色名格式化 / 隐私脱敏
- utils/attendance/shared.ts 签到状态判断、奖励文案
- utils/attendance/handlers/endfield.ts  终末地签到流程
- utils/attendance/index.ts + utils/retry.ts  重试封装

签到结果 AttendanceResult 额外携带服务端原始状态 status，供 report.py 渲染图片报告。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .client import SklandClient
from .constants import DEFAULT_MAX_RETRIES, ENDFIELD_APP_CODE, ENDFIELD_GAME_ID, RETRY_DELAY_SECONDS


# ---------- 角色名格式化（utils/format.ts） ----------

def mask_nickname(name: str) -> str:
    if len(name) <= 1:
        return '*'
    return name[0] + '*' * (len(name) - 1)


def format_privacy_name(character: 'EndfieldCharacter', anonymous: bool) -> str:
    """终末地的昵称在 defaultRole 里取（format.ts 中 gameId === 3 分支）。"""
    role = character.role or {}
    if anonymous:
        nickname = '管理员'
        level = '[等级占位符]'
    else:
        nickname = mask_nickname(role.get('nickname') or '')
        level = role.get('level') or 0
    return f'{nickname} lv.{level}'


def format_character_name(character: 'EndfieldCharacter', app_name: str | None = None, anonymous: bool = False) -> str:
    game_prefix = f'【{app_name}】' if app_name else ''
    return f'{game_prefix}{character.channel_name}角色 {format_privacy_name(character, anonymous)}'


# ---------- 签到结果 ----------

@dataclass
class AttendanceResult:
    success: bool
    message: str
    has_error: bool
    # 服务端签到状态原文（含 hasToday / calendar / resourceInfoMap），供图片报告使用；
    # 签到过程异常时拿不到，为 None
    status: dict[str, Any] | None = None


# ---------- 角色模型 ----------

@dataclass
class EndfieldCharacter:
    """终末地单个可签到角色。

    原实现中终末地按单个 role 展开：{ ...player, defaultRole: role, roles: [role] }
    """
    player: dict[str, Any]
    role: dict[str, Any] | None

    @property
    def game_id(self) -> int:
        return self.player.get('gameId', ENDFIELD_GAME_ID)

    @property
    def channel_name(self) -> str:
        return self.player.get('channelName') or '官服'

    @property
    def game_name(self) -> str:
        return self.player.get('gameName') or '明日方舟：终末地'


def build_endfield_character_list(binding_list: list[dict[str, Any]]) -> list[EndfieldCharacter]:
    """从 getBinding 的 list 中提取终末地角色，按单个 role 展开（tasks/attendance.ts 逻辑）。"""
    characters: list[EndfieldCharacter] = []
    for binding in binding_list:
        if binding.get('appCode') != ENDFIELD_APP_CODE:
            continue
        for player in binding.get('bindingList') or []:
            roles = player.get('roles') or []
            if roles:
                # 每个 role 需要独立签到
                characters.extend(EndfieldCharacter(player=player, role=role) for role in roles)
            else:
                characters.append(EndfieldCharacter(player=player, role=None))
    return characters


# ---------- 奖励文案（utils/attendance/shared.ts） ----------

def format_endfield_awards(award_ids: list[dict[str, Any]], resource_info_map: dict[str, dict[str, Any]]) -> str:
    parts = []
    for a in award_ids:
        award = resource_info_map.get(a.get('id', ''))
        if not award:
            parts.append('「未知奖励」1个')
        else:
            parts.append(f"「{award.get('name')}」{award.get('count') if award.get('count') is not None else 1}个")
    return ','.join(parts)


def is_today_attended(status: dict[str, Any]) -> bool:
    """终末地签到状态直接携带 hasToday 字段。"""
    return bool(status.get('hasToday'))


# ---------- 校验（endfield.ts validate） ----------

def validate_character(character: EndfieldCharacter) -> tuple[bool, str | None]:
    if character.role is None:
        return False, '没有角色'
    return True, None


# ---------- 签到主流程（endfield.ts handler） ----------

def _refresh_status(client: SklandClient, query: dict[str, Any], fallback: dict[str, Any] | None) -> dict[str, Any] | None:
    """签到后重新拉取状态，让图片报告里"今天"这一格显示为已签。

    刷新失败不影响签到结果，退回签到前的数据。
    """
    try:
        latest = client.get_endfield_attendance_status(**query)
    except Exception as error:
        print(f'签到后刷新签到状态失败，沿用签到前数据: {error}')
        return fallback
    return latest if isinstance(latest, dict) else fallback


def endfield_attendance_handler(
    client: SklandClient,
    character: EndfieldCharacter,
    character_label: str,
) -> AttendanceResult:
    role = character.role or {}
    query = {
        'game_id': character.game_id,
        'role_id': role.get('roleId'),
        'server_id': role.get('serverId'),
    }

    attendance_status = client.get_endfield_attendance_status(**query)

    if is_today_attended(attendance_status):
        return AttendanceResult(
            success=False,
            message=f'{character_label} 今天已经签到过了',
            has_error=False,
            status=attendance_status,
        )

    data = client.endfield_attendance(**query)
    awards = format_endfield_awards(data.get('awardIds') or [], data.get('resourceInfoMap') or {})

    return AttendanceResult(
        success=True,
        message=f'{character_label} 签到成功，获得了{awards}',
        has_error=False,
        status=_refresh_status(client, query, attendance_status),
    )


# ---------- 重试（utils/retry.ts + utils/attendance/index.ts） ----------

def retry(fn: Callable[[], AttendanceResult], retries: int = DEFAULT_MAX_RETRIES,
          delay: float = RETRY_DELAY_SECONDS,
          on_retry: Callable[[int], None] | None = None) -> AttendanceResult:
    try:
        return fn()
    except Exception as error:
        if retries > 0:
            if on_retry:
                on_retry(retries)
            time.sleep(delay)
            return retry(fn, retries - 1, delay, on_retry)
        raise


def attend_character(
    client: SklandClient,
    character: EndfieldCharacter,
    max_retries: int = DEFAULT_MAX_RETRIES,
    app_name: str | None = None,
    on_retry: Callable[[int], None] | None = None,
    anonymous: bool = False,
) -> AttendanceResult:
    """对应 utils/attendance/index.ts attendCharacter。"""
    character_label = format_character_name(character, app_name, anonymous)

    valid, reason = validate_character(character)
    if not valid:
        return AttendanceResult(
            success=False,
            message=f'{character_label} {reason or "验证失败"}，跳过签到',
            has_error=False,
        )

    try:
        return retry(
            lambda: endfield_attendance_handler(client, character, character_label),
            retries=max_retries,
            on_retry=on_retry,
        )
    except Exception as error:
        return AttendanceResult(
            success=False,
            message=f'{character_label} 签到过程中出现未知错误: {error}',
            has_error=True,
        )
