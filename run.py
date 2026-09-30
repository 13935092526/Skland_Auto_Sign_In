# -*- coding: utf-8 -*-
"""项目入口：编排 skland（签到取数）与 t2i（数据 → 图片 → 推送）两层。

用法：
    python run.py             # 签到 + 渲染图片 + 推送
    python run.py --preview   # 本地测试：照常签到与出图，但不推送（图片存 .cache/）

退出码：0 全部账号成功；1 存在失败账号。
"""

from __future__ import annotations

import sys
from pathlib import Path

from skland_endfield.main import collect
from t2i.report import build_account, render_report, push_report

PREVIEW_OUTPUT = Path('.cache/endfield_checkin.png')


def main(argv: list[str]) -> int:
    preview = '--preview' in argv

    # 1) skland：签到并取回各角色原始状态
    result = collect()

    # 2) t2i：原始数据 -> 模板数据 -> 图片 -> 推送
    accounts = [
        account
        for record in result.records
        if (account := build_account(record.role, record.status, result.anonymous))
    ]
    text = result.summary_text

    if preview:
        png = render_report(accounts, output=PREVIEW_OUTPUT)
        print(f'[preview] 图片已保存 {png}，本次不推送')
        return result.exit_code

    push_report(render_report(accounts), text=text)
    return result.exit_code


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
