# -*- coding: utf-8 -*-
"""项目入口：编排 skland（签到取数）与 t2i（数据 → 图片 → 推送）两层。

推送策略：webhook 只发签到日历图片；执行日志/摘要在 GitHub Actions 环境下
写入 Job Summary（$GITHUB_STEP_SUMMARY 汇总页），不再推送文字消息。

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
from t2i.report import build_account, render_report, push_report

PREVIEW_OUTPUT = Path('.cache/endfield_checkin.png')


def write_actions_summary(result: RunResult) -> None:
    """把签到日志与执行摘要写入 GitHub Actions Job Summary；非 Actions 环境跳过。"""
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    lines = ['## 🛰️ 森空岛终末地自动签到', '']
    if result.failed_accounts and result.failed_accounts != [0]:
        lines.append(f'> ⚠️ 本次有 {len(result.failed_accounts)} 个账号失败：#{", #".join(map(str, result.failed_accounts))}')
    elif not result.records:
        lines.append('> ⚠️ 未处理任何角色（未配置账号或账号无终末地角色）')
    else:
        lines.append('> ✅ 全部账号处理成功')
    lines += ['', '### 签到明细', '']
    lines += [f'- {record.message}' for record in result.records] or ['- 无']
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
        return result.exit_code

    push_report(render_report(accounts))
    return result.exit_code


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
