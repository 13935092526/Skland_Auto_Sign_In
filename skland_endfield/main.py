"""森空岛「明日方舟：终末地」每日自动签到 —— 数据层流程。

本模块只负责：登录 → 执行签到 → 采集结构化数据，不做渲染、不做推送。
出图与推送由 t2i 包负责，编排入口见项目根 run.py。

配置通过环境变量注入（见 README）：
    SKLAND_TOKENS       森空岛凭据（必填），多个用逗号分隔
    SKLAND_MAX_RETRIES  单角色签到失败最大重试次数（可选，默认 3）
    SKLAND_ANONYMOUS    设置任意值以隐藏角色名（可选）
    SKLAND_DID_FILE     设备指纹缓存文件（可选，由 workflow cache 跨运行保留）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .attendance import attend_character, build_endfield_character_list
from .client import SklandClient
from .constants import DEFAULT_MAX_RETRIES
from .errors import FailureInfo, classify_error


# ---------- 采集结果（交给 t2i 的原始数据） ----------

@dataclass
class SigninRecord:
    """单个角色的签到结果。status 为服务端原始签到状态，供 t2i 渲染日历。"""
    role: dict[str, Any] | None
    status: dict[str, Any] | None
    message: str
    success: bool
    has_error: bool
    # 失败原因分类（仅账号级失败或角色级异常时有值），供告警使用
    failure: FailureInfo | None = None


@dataclass
class RunResult:
    records: list[SigninRecord] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    failed_accounts: list[int] = field(default_factory=list)
    total_accounts: int = 0
    anonymous: bool = False

    @property
    def exit_code(self) -> int:
        return 1 if self.failed_accounts else 0


def get_split_by_comma(value: str | None) -> list[str]:
    return [v.strip() for v in value.split(',') if v.strip()] if value else []


def load_did() -> str | None:
    """从缓存文件读取设备指纹。"""
    path = os.environ.get('SKLAND_DID_FILE')
    if path and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            did = f.read().strip()
            if did:
                return did
    return None


def save_did(did: str) -> None:
    """将设备指纹写回缓存文件，供 Actions cache 跨运行复用。"""
    path = os.environ.get('SKLAND_DID_FILE')
    if not path:
        return
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(did)


def process_account(
    token: str,
    account_number: int,
    client: SklandClient,
    result: RunResult,
    stats: dict[int, list[int]],
    max_retries: int,
    total_accounts: int,
    anonymous: bool,
) -> bool:
    """处理单个账号，返回是否出现失败。stats: gameId -> [总数, 成功, 已签到, 失败]"""
    print(f'\n--- 账号 {account_number}/{total_accounts} ---')
    print('开始处理...')

    code = client.grant_authorize_code(token)
    client.sign_in(code)

    characters = build_endfield_character_list(client.get_binding())
    if not characters:
        print('该账号没有绑定的终末地角色')
        return False

    account_has_error = False
    for character in characters:
        game_stats = stats.setdefault(character.game_id, [0, 0, 0, 0])
        game_stats[0] += 1

        outcome = attend_character(
            client,
            character,
            max_retries,
            app_name=character.game_name,
            on_retry=lambda retries_left: print(f'操作失败，剩余重试次数: {retries_left}'),
            anonymous=anonymous,
        )

        result.records.append(SigninRecord(
            role=character.role,
            status=outcome.status,
            message=outcome.message,
            success=outcome.success,
            has_error=outcome.has_error,
            failure=outcome.failure,
        ))

        if outcome.has_error:
            print(f'[错误] {outcome.message}')
            game_stats[3] += 1
            account_has_error = True
        else:
            print(outcome.message)
            game_stats[1 if outcome.success else 2] += 1

    return account_has_error


def collect() -> RunResult:
    """按环境变量执行全部账号的签到，返回结构化采集结果。"""
    tokens = get_split_by_comma(os.environ.get('SKLAND_TOKENS'))
    result = RunResult(total_accounts=len(tokens))

    if not tokens:
        print('未配置任何账号（SKLAND_TOKENS），跳过签到任务')
        result.failed_accounts.append(0)
        return result

    max_retries = int(os.environ.get('SKLAND_MAX_RETRIES') or DEFAULT_MAX_RETRIES)
    anonymous = bool(os.environ.get('SKLAND_ANONYMOUS'))
    result.anonymous = anonymous
    stats: dict[int, list[int]] = {}

    print('## 森空岛每日签到')

    # 所有账号复用同一设备指纹；首次使用自动注册并写入缓存文件
    client = SklandClient(load_did())
    save_did(client.did)

    for index, token in enumerate(tokens):
        account_number = index + 1
        try:
            if process_account(token, account_number, client, result, stats, max_retries, len(tokens), anonymous):
                result.failed_accounts.append(account_number)
        except Exception as error:
            print(f'\n--- 账号 {account_number}/{len(tokens)} ---')
            failure = classify_error(error)
            print(f'[错误] 处理失败（{failure.label}）: {error}')
            if failure.hint:
                print(f'[提示] {failure.hint}')
            # 账号级失败也记入 records，让告警推送能携带原因
            result.records.append(SigninRecord(
                role=None,
                status=None,
                message=f'账号 {account_number} 处理失败: {error} {failure.detail}'.strip(),
                success=False,
                has_error=True,
                failure=failure,
            ))
            result.failed_accounts.append(account_number)

    # 执行摘要
    summary = ['========== 执行摘要 ==========', f'账号统计: 总数 {len(tokens)}，失败 {len(result.failed_accounts)}']
    if result.failed_accounts:
        summary.append(f'失败账号: #{", #".join(map(str, result.failed_accounts))}')
    for game_stats in stats.values():
        total, succeeded, already, failed = game_stats
        summary.append(f'角色统计: 总数 {total}，本次签到成功 {succeeded}，今天已签到 {already}，失败 {failed}')
    result.summary_lines = summary
    print('\n'.join(f'\n{line}' for line in summary))

    return result
