"""消息收集与推送通知。

对应原项目 utils/message.ts 的 MessageCollector（通知渠道原为 Statocysts 格式，
这里改为直接支持常见的几种 webhook 格式）：

- SCTxxx 或 https://sctapi.ftqq.com/...        Server酱
- https://api.day.app/<key>/...                 Bark
- https://www.pushplus.plus/send/<token>        pushplus
- 其他 http(s) URL                              通用 webhook，POST JSON {title, body/content}
"""

from __future__ import annotations

import requests

from .constants import REQUEST_TIMEOUT_SECONDS

NOTIFY_TITLE = '【森空岛每日签到】'


class MessageCollector:
    """log 仅控制台；notify 仅通知；info 两者兼有（与原实现一致）。"""

    def __init__(self, notification_urls: list[str] | None = None) -> None:
        self.notification_urls = notification_urls or []
        self._messages: list[str] = []
        self.has_error = False

    # 仅控制台
    def log(self, message: str) -> None:
        print(message)

    def error(self, message: str) -> None:
        print(message)
        self.has_error = True

    # 仅通知
    def notify(self, message: str) -> None:
        self._messages.append(message)

    def notify_error(self, message: str) -> None:
        self._messages.append(message)
        self.has_error = True

    # 控制台 + 通知
    def info(self, message: str) -> None:
        print(message)
        self._messages.append(message)

    def info_error(self, message: str) -> None:
        print(message)
        self._messages.append(message)
        self.has_error = True

    # 推送收集到的消息
    def push(self) -> None:
        if not self.notification_urls:
            return
        content = '\n\n'.join(self._messages)
        for url in self.notification_urls:
            try:
                _send_notification(url, NOTIFY_TITLE, content)
            except Exception as e:  # 通知失败不影响签到结果
                print(f'[notify] 推送失败 {url}: {e}')


def _send_notification(url: str, title: str, body: str) -> None:
    if url.startswith('sct'):
        # Statocysts 风格的 sct key
        url = f'https://sctapi.ftqq.com/{url.removeprefix("sct")}.send'

    if url.startswith('bark://') or 'api.day.app' in url or 'bark.tech' in url:
        url = url.removeprefix('bark://').rstrip('/')
        requests.post(url, json={'title': title, 'body': body}, timeout=REQUEST_TIMEOUT_SECONDS).raise_for_status()
    elif 'sctapi.ftqq.com' in url or 'sc.ftqq.com' in url:
        requests.post(url, data={'title': title, 'desp': body}, timeout=REQUEST_TIMEOUT_SECONDS).raise_for_status()
    elif 'pushplus' in url:
        requests.post(url, json={'title': title, 'content': body}, timeout=REQUEST_TIMEOUT_SECONDS).raise_for_status()
    else:
        requests.post(url, json={'title': title, 'body': body, 'content': body}, timeout=REQUEST_TIMEOUT_SECONDS).raise_for_status()
