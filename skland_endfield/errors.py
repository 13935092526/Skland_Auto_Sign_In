"""签到失败原因分类：把链路各环节的异常归为可读的原因标签 + 处理建议。

分类依据：
- SklandApiError 的错误消息文案（client.py 各环节抛出时带有固定前缀）
- 服务端响应体中的 msg / code（挂在 SklandApiError.response 上）
- requests 网络层异常
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from .client import SklandApiError

# 各类原因的中文标签与处理建议
TOKEN_INVALID_HINT = (
    'SKLAND_TOKENS 中的鹰角登录凭据已失效或填写错误：请重新登录森空岛网页版，'
    '打开 web-api.skland.com/account/info/hg 复制新的 content，'
    '更新仓库 Secrets 中的 SKLAND_TOKENS 后手动重跑'
)
SKLAND_LOGIN_HINT = '森空岛服务端登录接口异常，通常是暂时性的；若持续失败请检查凭据是否被风控'
CRED_EXPIRED_HINT = '运行中森空岛登录态失效，一般下次定时运行自动重新登录即可恢复；反复出现时请更新 SKLAND_TOKENS'
NETWORK_HINT = '网络请求失败（超时/连接被拒），通常是暂时性故障，可手动重跑 workflow'


@dataclass
class FailureInfo:
    kind: str            # invalid_token / skland_login / cred_expired / network / api / unknown
    label: str           # 中文原因短语
    detail: str = ''     # 服务端返回的补充信息（如有）
    hint: str = ''       # 需要用户执行的处理建议；空串表示无需操作


def _response_field(response, *keys: str) -> str:
    """从服务端响应 dict 里取第一个非空字符串字段。"""
    if isinstance(response, dict):
        for key in keys:
            value = response.get(key)
            if isinstance(value, str) and value:
                return value
    return ''


def classify_error(exc: Exception) -> FailureInfo:
    """把异常归因。账号级/角色级失败都走这里，保证告警文案一致。"""
    message = str(exc)

    if isinstance(exc, SklandApiError):
        # 鹰角 OAuth 授权失败 —— SKLAND_TOKENS 凭据失效/错误的最典型特征
        if 'OAuth 登录凭证' in message:
            return FailureInfo(
                'invalid_token',
                'SKLAND_TOKENS 凭据失效（鹰角网络通行证验证未通过）',
                _response_field(exc.response, 'msg', 'message'),
                TOKEN_INVALID_HINT,
            )
        # 授权码换 cred 失败 —— 多为森空岛服务端问题
        if '森空岛登录错误' in message:
            return FailureInfo(
                'skland_login',
                '森空岛登录失败（授权码换取凭证出错）',
                _response_field(exc.response, 'msg', 'message'),
                SKLAND_LOGIN_HINT,
            )
        # 签名接口返回登录态失效（服务端 code/msg 特征）
        code = exc.response.get('code') if isinstance(exc.response, dict) else None
        resp_msg = _response_field(exc.response, 'msg', 'message')
        if code in (7, 401) or '登陆状态失效' in resp_msg or '登录状态失效' in resp_msg:
            return FailureInfo('cred_expired', '森空岛登录态失效', resp_msg, CRED_EXPIRED_HINT)
        return FailureInfo(
            'api',
            '森空岛接口返回错误',
            f'{message} {resp_msg}'.strip(),
            NETWORK_HINT,
        )

    if isinstance(exc, requests.RequestException):
        return FailureInfo('network', '网络请求失败', str(exc), NETWORK_HINT)
    if isinstance(exc, OSError):  # socket.timeout 等底层网络错误
        return FailureInfo('network', '网络请求失败', str(exc), NETWORK_HINT)

    return FailureInfo('unknown', '未知错误', message, '')
