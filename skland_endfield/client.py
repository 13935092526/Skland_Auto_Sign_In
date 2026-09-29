"""森空岛 API 客户端，对应 skland-kit 的 src/client 下核心逻辑。

仅保留终末地签到所需能力：
- grant_authorize_code  鹰角通行证 OAuth 授权（hypergryph.ts）
- sign_in               用授权码换取 cred/token（core.ts signIn）
- _signed_request       zonai 签名请求（signature.ts signRequest）
- get_binding           账号绑定的角色列表（player.ts getBinding）
- get_attendance_status / attendance  终末地签到状态与签到（game.ts）
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .constants import (
    DESKTOP_UA,
    HYPERGRYPH_BASE_URL,
    MOBILE_UA,
    REQUEST_TIMEOUT_SECONDS,
    SERVER_TIMESTAMP_OFFSET_MS,
    SIGN_PLATFORM,
    SIGN_VNAME,
    SKLAND_APP_CODE,
    SKLAND_BASE_URL,
    X_REQUESTED_WITH,
)
from .crypto import hmac_sha256_hex, md5
from .device import request_new_did


class SklandApiError(RuntimeError):
    def __init__(self, message: str, response: Any = None) -> None:
        super().__init__(message)
        self.response = response


def parse_oauth_token(input_str: str) -> str:
    """对应 hypergrayph.ts 的 parseOAuthToken。

    支持直接传入 content 值，也支持粘贴整个 https://web-api.skland.com/account/info/hg
    （或 hypergryph 同款接口）的 JSON 响应，自动提取 data.content。
    """
    token = input_str.strip()
    try:
        parsed = json.loads(token)
        content = parsed.get('data', {}).get('content')
        if isinstance(content, str):
            return content
    except (json.JSONDecodeError, AttributeError):
        pass
    return token


class SklandClient:
    def __init__(self, did: str | None = None) -> None:
        self.did = did or request_new_did()
        self.session = requests.Session()
        self.token: str | None = None
        self.cred: str | None = None

    # ---------- 基础请求 ----------

    def _send(
        self,
        method: str,
        url: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        full_url = url + ('?' + urlencode(query) if query else '')
        resp = self.session.request(
            method,
            full_url,
            data=json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8') if body is not None else None,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, None

    # ---------- 鹰角通行证 ----------

    def grant_authorize_code(self, token_input: str, app_code: str = SKLAND_APP_CODE, grant_type: int = 0) -> str:
        """对应 hypergrayph.ts grantAuthorizeCode，返回授权 code。"""
        status, res = self._send(
            'POST',
            f'{HYPERGRYPH_BASE_URL}/user/oauth2/v2/grant',
            body={'appCode': app_code, 'token': parse_oauth_token(token_input), 'type': grant_type},
            headers={
                'content-type': 'application/json',
                'user-agent': MOBILE_UA,
                'dId': self.did,
                'x-requested-with': X_REQUESTED_WITH,
            },
        )
        # 对应 isSuccessResponse：status===0 && msg==='OK' 且结构完整
        if (
            status != 200 or not isinstance(res, dict)
            or res.get('data') is None or res.get('status') is None or res.get('type') is None
            or res.get('msg') != 'OK' or res.get('status') != 0
        ):
            raise SklandApiError('【skland-kit】通过 OAuth 登录凭证验证鹰角网络通行证错误', res)
        code = res['data'].get('code')
        if not code:
            raise SklandApiError('【skland-kit】通过 OAuth 登录凭证验证鹰角网络通行证错误', res)
        return code

    # ---------- 森空岛登录 ----------

    def sign_in(self, authorize_code: str) -> dict[str, str]:
        """对应 core.ts signIn：授权码换 cred/token/userId（仅内存持有）。"""
        status, res = self._send(
            'POST',
            f'{SKLAND_BASE_URL}/web/v1/user/auth/generate_cred_by_code',
            body={'code': authorize_code, 'kind': 1},
            headers={
                'content-type': 'application/json',
                'user-agent': DESKTOP_UA,
                'referer': 'https://www.skland.com/',
                'origin': 'https://www.skland.com',
                'dId': self.did,
                'platform': SIGN_PLATFORM,
                'timestamp': str(int(time.time())),
                'vName': SIGN_VNAME,
            },
        )
        if status != 200 or not isinstance(res, dict) or res.get('code') != 0:
            raise SklandApiError('【skland-kit】森空岛登录错误', res)
        data = res['data']
        self.token = data['token']
        self.cred = data['cred']
        return data

    # ---------- 签名请求 ----------

    def _sign_headers(self, path: str, query: dict[str, Any] | None, body: dict[str, Any] | None) -> dict[str, str]:
        """对应 signature.ts signRequest。

        签名串 = pathname + queryString + JSON(body) + timestamp + JSON(signatureHeaders)
        sign = md5(hmacSha256(token, 签名串))
        """
        if not self.token:
            raise SklandApiError('【skland-kit】森空岛 token 未设置')
        if not self.cred:
            raise SklandApiError('【skland-kit】森空岛 cred 未获取')

        query_str = urlencode(query or {})
        timestamp = str((int(time.time() * 1000) - SERVER_TIMESTAMP_OFFSET_MS) // 1000)
        signature_headers = {
            'platform': SIGN_PLATFORM,
            'timestamp': timestamp,
            'dId': self.did,
            'vName': SIGN_VNAME,
        }
        body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':')) if body is not None else ''
        headers_str = json.dumps(signature_headers, ensure_ascii=False, separators=(',', ':'))
        str_to_sign = f'{path}{query_str}{body_str}{timestamp}{headers_str}'
        sign = md5(hmac_sha256_hex(self.token, str_to_sign))

        headers = {
            'user-agent': MOBILE_UA,
            'accept-encoding': 'gzip',
            'connection': 'close',
            'x-requested-with': X_REQUESTED_WITH,
            'sign': sign,
            'cred': self.cred,
            **signature_headers,
        }
        return headers

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        error_message: str = '请求错误',
    ) -> Any:
        headers = self._sign_headers(path, query, body)
        headers.setdefault('content-type', 'application/json')
        if extra_headers:
            headers.update(extra_headers)

        status, res = self._send(method, SKLAND_BASE_URL + path, query=query, body=body, headers=headers)
        # 对应 onResponseError / code !== 0 检查
        if status >= 400:
            raise SklandApiError(f'【skland-kit】{error_message}', res)
        if not isinstance(res, dict) or res.get('code') != 0:
            raise SklandApiError(f'【skland-kit】{error_message}', res)
        return res['data']

    # ---------- 玩家绑定 ----------

    def get_binding(self) -> list[dict[str, Any]]:
        """对应 player.ts getBinding，返回 list（各 app 的绑定信息）。"""
        data = self._signed_request(
            'GET', '/api/v1/game/player/binding',
            error_message='获取游戏绑定信息错误',
        )
        return data.get('list', [])

    # ---------- 终末地签到 ----------

    def _endfield_role_header(self, game_id: int, role_id: str, server_id: str) -> dict[str, str]:
        return {'sk-game-role': f'{game_id}_{role_id}_{server_id}'}

    def get_endfield_attendance_status(self, game_id: int, role_id: str, server_id: str) -> dict[str, Any]:
        """对应 game.ts getAttendanceStatus（终末地分支），GET /api/v1/game/endfield/attendance。"""
        return self._signed_request(
            'GET', '/api/v1/game/endfield/attendance',
            extra_headers=self._endfield_role_header(game_id, role_id, server_id),
            error_message='获取签到状态错误',
        )

    def endfield_attendance(self, game_id: int, role_id: str, server_id: str) -> dict[str, Any]:
        """对应 game.ts attendance（终末地分支），POST /api/v1/game/endfield/attendance。"""
        return self._signed_request(
            'POST', '/api/v1/game/endfield/attendance',
            extra_headers={
                **self._endfield_role_header(game_id, role_id, server_id),
                'referer': 'https://game.skland.com/',
                'origin': 'https://game.skland.com/',
            },
            error_message='获取签到信息错误',
        )
