# -*- coding: utf-8 -*-
"""项目入口：编排 skland（签到取数）与 t2i（数据 → 图片 → 推送）两层。

推送策略：成功时 webhook 只发签到日历图片；执行日志/摘要写入 Job Summary。
签到失败时额外推送文字告警，并附失败原因分析；若原因是 SKLAND_TOKENS 失效，
告警中会明确说明并给出更换凭据的操作步骤。

用法：
    python run.py             # 签到 + 渲染图片 + 推送图片
    python run.py --preview   # 本地测试：照常签到与出图，但不推送（图片存 .cache/）

退出码：0 全部账号成功；1 存在失败账号。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from skland_endfield.main import RunResult, collect
from skland_endfield.crypto import shanghai_now
from t2i.report import build_account, push_alert, render_report, push_report

PREVIEW_OUTPUT = Path('.cache/endfield_checkin.png')


def failed_records(result: RunResult) -> list:
    return [record for record in result.records if record.has_error]


def build_alert_text(result: RunResult) -> str:
    """把失败记录汇总成告警文字，突出 SKLAND_TOKENS 失效的处理说明。"""
    failures = failed_records(result)
    lines = [f'⚠️ 终末地自动签到失败告警（{shanghai_now().strftime("%Y-%m-%d %H:%M")}）', '']

    token_invalid = [f for f in failures if f.failure and f.failure.kind == 'invalid_token']
    if token_invalid:
        lines.append(f'❗ 检测到 SKLAND_TOKENS 凭据失效（影响 {len(token_invalid)} 个账号），签到无法完成！')
        lines.append(f'➡️ {token_invalid[0].failure.hint}')
        lines.append('')

    lines.append('失败明细：')
    for record in failures:
        failure = record.failure
        reason = f'（原因：{failure.label}）' if failure else ''
        lines.append(f'· {record.message}{reason}')
        # SKLAND_TOKENS 失效已在顶部集中说明，避免重复刷屏
        if failure and failure.hint and failure.kind != 'invalid_token':
            lines.append(f'  ➡️ {failure.hint}')
    lines.append('')
    lines.append('详细日志见 GitHub Actions 运行汇总页；当天可手动 Run workflow 补签。')
    return '\n'.join(lines)


def write_actions_summary(result: RunResult) -> None:
    """把签到日志与执行摘要写入 GitHub Actions Job Summary；非 Actions 环境跳过。"""
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    lines = ['## 🛰️ 森空岛终末地自动签到', '']
    failures = failed_records(result)
    if result.failed_accounts and result.failed_accounts != [0]:
        lines.append(f'> ⚠️ 本次有 {len(result.failed_accounts)} 个账号失败：#{", #".join(map(str, result.failed_accounts))}')
    elif not result.records:
        lines.append('> ⚠️ 未处理任何角色（未配置账号或账号无终末地角色）')
    else:
        lines.append('> ✅ 全部账号处理成功')
    lines += ['', '### 签到明细', '']
    for record in result.records:
        suffix = f'（原因：{record.failure.label}）' if record.has_error and record.failure else ''
        lines.append(f'- {record.message}{suffix}')
    if not result.records:
        lines.append('- 无')
    # 失败原因集中展示，便于在汇总页直接定位处理方法
    if failures:
        lines += ['', '### 失败分析与处理建议', '']
        for record in failures:
            failure = record.failure
            if failure:
                lines.append(f'- **{failure.label}**')
                if failure.detail:
                    lines.append(f'  - 服务端信息：`{failure.detail[:200]}`')
                if failure.hint:
                    lines.append(f'  - 处理建议：{failure.hint}')
    lines += ['', '### 执行摘要', '', '```']
    lines += result.summary_lines
    lines += ['```', '']
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main(argv: list[str]) -> int:
    preview = '--preview' in argv

    # 1) skland：签到并取回各角色原始状态
    result = collect()

    # 2) 日志/摘要进 Actions 汇总页（webhook 不推文字）
    write_actions_summary(result)

    # 3) t2i：原始数据 -> 模板数据 -> 图片 -> 只推送图片
    accounts = [
        account
        for record in result.records
        if (account := build_account(record.role, record.status, result.anonymous))
    ]

    if preview:
        png = render_report(accounts, output=PREVIEW_OUTPUT)
        print(f'[preview] 图片已保存 {png}，本次不推送')
        if failed_records(result):
            print('\n===== 失败告警（preview 不推送）=====')
            print(build_alert_text(result))
        return result.exit_code

    push_report(render_report(accounts))

    # 签到失败：额外推送文字告警（含原因分析，SKLAND_TOKENS 失效会重点说明）
    if failed_records(result):
        alert = build_alert_text(result)
        print('\n' + alert)
        push_alert(alert)
    return result.exit_code


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
