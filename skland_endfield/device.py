"""数美科技设备指纹（did）生成，对应 skland-kit 的 src/utils/env.ts。

流程与 TS 版一致：
1. 生成 UUID uid，priId = md5(uid)[:16]
2. RSA 加密 uid -> ep
3. 组装浏览器环境数据，计算 tn / smid
4. 按 DES 规则加密字段并重命名 -> gzip -> AES 加密
5. POST 数美 /deviceprofile/v4，取 deviceId，did = 'B' + deviceId

在 GitHub Actions 中通过 cache 跨运行复用，避免每天重复注册设备。
"""

from __future__ import annotations

import uuid
from typing import Any

import requests

from .constants import REQUEST_TIMEOUT_SECONDS
from .crypto import encrypt_aes, encrypt_des, encrypt_rsa, gzip_b64, md5, shanghai_now

# 数美科技配置（window._smConf）
SKLAND_SM_CONFIG = {
    'organization': 'UWXspnCCJN4sfYlNfqps',
    'appId': 'default',
    'publicKey': (
        'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCmxMNr7n8ZeT0tE1R9j/mPixoinPke'
        'M+k4VGIn/s0k7N5rJAfnZ0eMER+QhwFvshzo0LNmeUkpR8uIlU/GEVr8mN28sKmwd2gp'
        'ygqj0ePnBmOW4v0ZVwbSYK+izkhVFk2V/doLoMbWy6b+UnA8mkjvg0iYWRByfRsK2gdl'
        '7llqCwIDAQAB'
    ),
    'protocol': 'https',
    'apiHost': 'fp-it.portal101.cn',
    'apiPath': '/deviceprofile/v4',
}

DEVICES_INFO_URL = f"{SKLAND_SM_CONFIG['protocol']}://{SKLAND_SM_CONFIG['apiHost']}{SKLAND_SM_CONFIG['apiPath']}"

# 字段 DES 加密规则（obfuscated_name -> 加密 key）
DES_RULE: dict[str, dict[str, Any]] = {
    'appId': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'uy7mzc4h', 'obfuscated_name': 'xx'},
    'box': {'is_encrypt': 0, 'obfuscated_name': 'jf'},
    'canvas': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'snrn887t', 'obfuscated_name': 'yk'},
    'clientSize': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'cpmjjgsu', 'obfuscated_name': 'zx'},
    'organization': {'cipher': 'DES', 'is_encrypt': 1, 'key': '78moqjfc', 'obfuscated_name': 'dp'},
    'os': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'je6vk6t4', 'obfuscated_name': 'pj'},
    'platform': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'pakxhcd2', 'obfuscated_name': 'gm'},
    'plugins': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'v51m3pzl', 'obfuscated_name': 'kq'},
    'pmf': {'cipher': 'DES', 'is_encrypt': 1, 'key': '2mdeslu3', 'obfuscated_name': 'vw'},
    'protocol': {'is_encrypt': 0, 'obfuscated_name': 'protocol'},
    'referer': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'y7bmrjlc', 'obfuscated_name': 'ab'},
    'res': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'whxqm2a7', 'obfuscated_name': 'hf'},
    'rtype': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'x8o2h2bl', 'obfuscated_name': 'lo'},
    'sdkver': {'cipher': 'DES', 'is_encrypt': 1, 'key': '9q3dcxp2', 'obfuscated_name': 'sc'},
    'status': {'cipher': 'DES', 'is_encrypt': 1, 'key': '2jbrxxw4', 'obfuscated_name': 'an'},
    'subVersion': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'eo3i2puh', 'obfuscated_name': 'ns'},
    'svm': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'fzj3kaeh', 'obfuscated_name': 'qr'},
    'time': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'q2t3odsk', 'obfuscated_name': 'nb'},
    'timezone': {'cipher': 'DES', 'is_encrypt': 1, 'key': '1uv05lj5', 'obfuscated_name': 'as'},
    'tn': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'x9nzj1bp', 'obfuscated_name': 'py'},
    'trees': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'acfs0xo4', 'obfuscated_name': 'pi'},
    'ua': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'k92crp1t', 'obfuscated_name': 'bj'},
    'url': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'y95hjkoo', 'obfuscated_name': 'cf'},
    'version': {'is_encrypt': 0, 'obfuscated_name': 'version'},
    'vpw': {'cipher': 'DES', 'is_encrypt': 1, 'key': 'r9924ab5', 'obfuscated_name': 'ca'},
}

BROWSER_ENV: dict[str, Any] = {
    'plugins': (
        'MicrosoftEdgePDFPluginPortableDocumentFormatinternal-pdf-viewer1,'
        'MicrosoftEdgePDFViewermhjfbmdgcfjbbpaeojofohoefgiehjai1'
    ),
    'canvas': '259ffe69',
    'timezone': -480,
    'platform': 'Win32',
    'url': 'https://www.skland.com/',
    'referer': '',
    'res': '1920_1080_24_1.25',
    'clientSize': '0_0_1080_1920_1920_1080_1920_1080',
    'status': '0011',
    # 基于浏览器的 canvas 值等与 TS 版 BROWSER_ENV 保持一致
    'ua': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0'
    ),
}


def _js_number_str(v: float | int) -> str:
    """模拟 JS String(number)，保证 tn 计算与原实现逐字节一致。"""
    if v != v:
        return 'NaN'
    if v == float('inf'):
        return 'Infinity'
    if v == float('-inf'):
        return '-Infinity'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int) or float(v).is_integer():
        return str(int(v))
    return repr(float(v))


def get_tn(o: dict[str, Any]) -> str:
    """对应 env.ts 的 getTn：按 key 排序拼接值，数字 *10000，对象递归。"""
    result = []
    for key in sorted(o.keys()):
        v = o[key]
        if isinstance(v, bool):
            v = 'true' if v else 'false'
        elif isinstance(v, (int, float)):
            v = _js_number_str(v * 10000)
        elif isinstance(v, dict):
            v = get_tn(v)
        result.append(str(v))
    return ''.join(result)


def get_sm_id() -> str:
    """对应 env.ts 的 getSmId。"""
    now = shanghai_now()
    _time = now.strftime('%Y%m%d%H%M%S')
    uid = str(uuid.uuid4())
    uid_md5 = md5(uid)
    v = f'{_time}{uid_md5}00'
    smsk_web = md5(f'smsk_web_{v}')[0:14]
    return f'{v}{smsk_web}0'


def encrypt_object_by_des_rules(obj: dict[str, Any], rules: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """对应 encryptObjectByDESRules：按规则加密并重命名为混淆字段。"""
    result: dict[str, Any] = {}
    for k, value in obj.items():
        rule = rules.get(k)
        if rule is not None:
            if rule['is_encrypt'] == 1:
                result[rule['obfuscated_name']] = encrypt_des(value, rule['key'])
            else:
                result[rule['obfuscated_name']] = value
        else:
            result[k] = value
    return result


def request_new_did() -> str:
    """向数美接口注册设备，返回 `B<deviceId>`。"""
    uid = str(uuid.uuid4())
    pri_id = md5(uid)[0:16]
    ep = encrypt_rsa(uid, SKLAND_SM_CONFIG['publicKey'])

    now_ms = int(shanghai_now().timestamp() * 1000)
    browser = {
        **BROWSER_ENV,
        'vpw': str(uuid.uuid4()),
        'svm': now_ms,
        'trees': str(uuid.uuid4()),
        'pmf': now_ms,
    }

    des_target: dict[str, Any] = {
        **browser,
        'protocol': 102,
        'organization': SKLAND_SM_CONFIG['organization'],
        'appId': SKLAND_SM_CONFIG['appId'],
        'os': 'web',
        'version': '3.0.0',
        'sdkver': '3.0.0',
        'box': '',
        'rtype': 'all',
        'smid': get_sm_id(),
        'subVersion': '1.0.0',
        'time': 0,
    }
    des_target['tn'] = md5(get_tn(des_target))

    des_result = encrypt_object_by_des_rules(des_target, DES_RULE)
    gzip_result = gzip_b64(des_result)
    aes_result = encrypt_aes(gzip_result, pri_id)

    body = {
        'appId': 'default',
        'compress': 2,
        'data': aes_result,
        'encode': 5,
        'ep': ep,
        'organization': SKLAND_SM_CONFIG['organization'],
        'os': 'web',
    }

    resp = requests.post(
        DEVICES_INFO_URL,
        json=body,
        headers={'Content-Type': 'application/json', 'user-agent': BROWSER_ENV['ua']},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') != 1100:
        raise RuntimeError(f'did 计算失败: {data}')
    return f"B{data['detail']['deviceId']}"
