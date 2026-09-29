"""森空岛「明日方舟：终末地」每日自动签到入口（GitHub Actions 版）。

配置通过环境变量注入（见 README）：
    SKLAND_TOKENS            森空岛凭据（必填），多个用逗号分隔
    SKLAND_NOTIFICATION_URLS 通知 URL（可选），多个用逗号分隔
    SKLAND_MAX_RETRIES       单角色签到失败最大重试次数（可选，默认 3）
    SKLAND_ANONYMOUS         设置任意值以隐藏角色名（可选）
    SKLAND_DID_FILE          设备指纹缓存文件（可选，由 workflow cache 跨运行保留）
"""

from __future__ import annotations

import os

from .attendance import attend_character, build_endfield_character_list
from .client import SklandClient
from .constants import DEFAULT_MAX_RETRIES
from .notify import MessageCollector


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
    collector: MessageCollector,
    stats: dict[int, list[int]],
    max_retries: int,
    total_accounts: int,
    anonymous: bool,
) -> bool:
    """处理单个账号，返回是否出现失败。stats: gameId -> [总数, 成功, 已签到, 失败]"""
    collector.notify(f'\n--- 账号 {account_number}/{total_accounts} ---')
    collector.info('开始处理...')

    code = client.grant_authorize_code(token)
    client.sign_in(code)

    characters = build_endfield_character_list(client.get_binding())
    if not characters:
        collector.info('该账号没有绑定的终末地角色')
        return False

    account_has_error = False
    for character in characters:
        game_stats = stats.setdefault(character.game_id, [0, 0, 0, 0])
        game_stats[0] += 1

        result = attend_character(
            client,
            character,
            max_retries,
            app_name=character.game_name,
            on_retry=lambda retries_left: collector.log(f'操作失败，剩余重试次数: {retries_left}'),
            anonymous=anonymous,
        )

        if result.has_error:
            collector.info_error(result.message)
            game_stats[3] += 1
            account_has_error = True
        else:
            collector.info(result.message)
            game_stats[1 if result.success else 2] += 1

    return account_has_error


def main() -> int:
    tokens = get_split_by_comma(os.environ.get('SKLAND_TOKENS'))
    collector = MessageCollector(get_split_by_comma(os.environ.get('SKLAND_NOTIFICATION_URLS')))

    if not tokens:
        collector.log('未配置任何账号（SKLAND_TOKENS），跳过签到任务')
        return 1

    max_retries = int(os.environ.get('SKLAND_MAX_RETRIES') or DEFAULT_MAX_RETRIES)
    anonymous = bool(os.environ.get('SKLAND_ANONYMOUS'))
    stats: dict[int, list[int]] = {}
    failed_indexes: list[int] = []

    # 所有账号复用同一设备指纹；首次使用自动注册并写入缓存文件
    client = SklandClient(load_did())
    save_did(client.did)

    collector.notify('## 森空岛每日签到')

    for index, token in enumerate(tokens):
        account_number = index + 1
        try:
            if process_account(token, account_number, client, collector, stats, max_retries, len(tokens), anonymous):
                failed_indexes.append(account_number)
        except Exception as error:
            collector.notify(f'\n--- 账号 {account_number}/{len(tokens)} ---')
            collector.info_error(f'处理失败: {error}')
            failed_indexes.append(account_number)

    # 执行摘要
    summary = ['\n========== 执行摘要 ==========', f'账号统计: 总数 {len(tokens)}，失败 {len(failed_indexes)}']
    if failed_indexes:
        summary.append(f'失败账号: #{", #".join(map(str, failed_indexes))}')
    for game_name_stats in stats.values():
        total, succeeded, already, failed = game_name_stats
        summary.append(f'角色统计: 总数 {total}，本次签到成功 {succeeded}，今天已签到 {already}，失败 {failed}')
    for line in summary:
        collector.notify(line)
    print('\n'.join(summary))

    collector.push()
    return 1 if failed_indexes else 0


if __name__ == '__main__':
    raise SystemExit(main())
