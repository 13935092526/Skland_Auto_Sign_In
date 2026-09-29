"""加密工具，对应 skland-kit 的 src/utils/crypto.ts。

- md5 / hmacSha256            -> hashlib / hmac
- encryptRSA (PKCS1 v1.5)     -> cryptography
- encryptDES (3DES-ECB 64位密钥) -> pycryptodome
- encryptAES (AES-CBC)        -> pycryptodome
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.serialization import load_der_public_key

# ---------- 基础散列 ----------

def md5(text: str) -> str:
    """md5(UTF8(text)) -> hex 小写"""
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()


def hmac_sha256_hex(key: str, data: str) -> str:
    """hmac(sha256, UTF8(key), UTF8(data)) -> hex 小写"""
    return hmac.new(str(key).encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()


# ---------- 时间 ----------

def shanghai_now() -> datetime:
    """当前北京时间（Asia/Shanghai，固定 UTC+8）。"""
    return datetime.now(timezone(timedelta(hours=8)))


def shanghai_date_str(dt: datetime | None = None) -> str:
    """YYYY-MM-DD（en-CA / Asia/Shanghai 格式），用于签到状态键与判断。"""
    d = dt if dt is not None else shanghai_now()
    return d.strftime('%Y-%m-%d')


# ---------- RSA ----------

def encrypt_rsa(message: str, public_key_b64: str) -> str:
    """RSA PKCS#1 v1.5 加密（对应 mima.pkcs1_es_1_5），输入为无-header 的 SPKI base64。"""
    der = base64.b64decode(public_key_b64)
    key = load_der_public_key(der)
    encrypted = key.encrypt(message.encode('utf-8'), PKCS1v15())
    return base64.b64encode(encrypted).decode('ascii')


# ---------- 3DES ----------

def encrypt_des(message: str | int | float, key: str) -> str:
    """3DES-ECB 加密（64 位密钥，NO_PAD，对应 mima.t_des(64) + ecb + NO_PAD）。

    mima-kit 将 8 字节密钥重复为 k1k2k3 = kk，此时 EDE(k,k,k) 在数学上等价于
    单次 DES 加密，而 pycryptodome 的 DES3 拒绝退化密钥，故直接用 DES。
    输入先做 \\0 补齐到 8 的倍数。
    """
    input_str = _pad_nulls(str(message))
    key_bytes = _pad_nulls_to(key, 8)
    cipher = DES.new(key_bytes, DES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(input_str.encode('utf-8'))).decode('ascii')


def _pad_nulls(data: str, block_size: int = 8) -> str:
    pad_len = block_size - (len(data) % block_size)
    return data + '\0' * pad_len


def _pad_nulls_to(data: str, size: int) -> bytes:
    raw = data.encode('utf-8')
    return raw[:size].ljust(size, b'\0')


# ---------- AES ----------

def encrypt_aes(message: str, key: str) -> str:
    """AES-CBC 加密，IV 固定为 ASCII '0102030405060708'，输出 hex。"""
    iv = b'0102030405060708'
    key_bytes = _pad_nulls_to(key, 16)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    data = pad(message.encode('utf-8'), AES.block_size)  # PKCS7
    return cipher.encrypt(data).hex()


# ---------- gzip ----------

def gzip_b64(obj: dict) -> str:
    """按 JS JSON.stringify 风格序列化后 gzip 压缩再 base64。

    注意：Python 默认 json separators (', ', ': ') 与 JS JSON.stringify 一致；
    gzip OS 字节需置为 19（Unknown），以对齐原实现中 compressedArray[9] = 19。
    """
    encoded = json.dumps(obj, ensure_ascii=False, separators=(', ', ': ')).encode('utf-8')
    compressed = bytearray(gzip.compress(encoded))
    compressed[9] = 19  # Python gzip OS FLG = Unknown
    return base64.b64encode(bytes(compressed)).decode('ascii')
