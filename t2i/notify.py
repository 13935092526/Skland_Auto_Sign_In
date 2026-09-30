# -*- coding: utf-8 -*-
"""推送通道：企业微信群机器人（text / image）+ Server酱（markdown）。

除 python-dotenv 外仅用标准库 urllib，作为接口被任意项目调用：
  from t2i import push
  push([Path("a.png")], title="签到报告", text="今日已签到")

密钥解析顺序（适配"作为 utils 库被不同项目引入"）：
  1. 调用 push 时显式传入 webhook= / sendkey=
  2. 环境变量（import 时由 python-dotenv 自动从项目 .env 载入）：
       企业微信 webhook  -> WX_WEBHOOK（兼容 WECOM_WEBHOOK）
       Server酱 SendKey  -> SERVERCHAN_KEY
不要把密钥硬编码或提交进仓库（.env 应加入 .gitignore）。

注意：企业微信机器人只支持 text 与 image 两种 msgtype（不支持 markdown）；
Server酱 的 desp 支持 markdown，但图片需要公网 URL，本地图片无法内嵌，
因此 Server酱 只收文字摘要，图片由企业微信通道送达。缺哪个密钥就跳过哪个通道。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Sequence

try:  # 可选依赖：装了就读 .env，没装也能靠系统环境变量
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

WECOM_TEXT_LIMIT = 2000   # 企微 text 上限 2048 字节，留余量
WECOM_IMAGE_LIMIT = 2 * 1024 * 1024   # 企微 image 内容上限 2MB

# 每个密钥可接受的环境变量名（按优先级）
WECOM_ENV = ("WX_WEBHOOK", "WECOM_WEBHOOK")
SERVERCHAN_ENV = ("SERVERCHAN_KEY",)


def env_secret(names: Sequence[str]) -> str:
    """按候选环境变量名顺序取第一个非空值。"""
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def fit_utf8(text: str, limit: int = WECOM_TEXT_LIMIT) -> str:
    tail = "\n...(内容过长已截断)"
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[: limit - len(tail.encode("utf-8"))].decode("utf-8", "ignore") + tail


def send_wecom_text(text: str, webhook: str) -> bool:
    resp = post_json(webhook, {"msgtype": "text", "text": {"content": fit_utf8(text)}})
    ok = resp.get("errcode") == 0
    print(f"企业微信文字 {'成功' if ok else '异常: ' + json.dumps(resp, ensure_ascii=False)[:160]}")
    return ok


def send_wecom_image(path: Path, webhook: str) -> bool:
    raw = path.read_bytes()
    if len(raw) > WECOM_IMAGE_LIMIT:
        print(f"企业微信图片 跳过（{path.name} 超过 2MB）")
        return False
    resp = post_json(webhook, {"msgtype": "image", "image": {
        "base64": base64.b64encode(raw).decode(),
        "md5": hashlib.md5(raw).hexdigest(),
    }})
    ok = resp.get("errcode") == 0
    print(f"企业微信图片 {path.name} {'成功' if ok else '异常: ' + json.dumps(resp, ensure_ascii=False)[:160]}")
    return ok


def send_serverchan(title: str, desp: str, key: str) -> bool:
    data = urllib.parse.urlencode({"title": title, "desp": desp}).encode()
    req = urllib.request.Request(f"https://sctapi.ftqq.com/{key}.send", data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8", "ignore"))
    ok = resp.get("code") == 0
    print(f"Server酱 {'成功' if ok else '异常: ' + json.dumps(resp, ensure_ascii=False)[:160]}")
    return ok


def push(images: Sequence[str | Path], title: str = "", text: str = "",
         *, webhook: str | None = None, sendkey: str | None = None,
         wecom_only: bool = False) -> bool:
    """推送图片/文字。webhook/sendkey 缺省时从环境变量（.env）解析；wecom_only=True 跳过 Server酱。

    返回是否全部已启用的通道都成功；无任何通道可用时返回 False。
    """
    imgs = [Path(i) for i in images]
    webhook = webhook if webhook is not None else env_secret(WECOM_ENV)
    sckey = "" if wecom_only else (sendkey if sendkey is not None else env_secret(SERVERCHAN_ENV))
    results = []

    if webhook:
        if text:
            results.append(send_wecom_text(f"{title}\n{text}" if title else text, webhook))
        for img in imgs:
            results.append(send_wecom_image(img, webhook))
    else:
        print("未配置企业微信 webhook（参数/WX_WEBHOOK 均缺），跳过企业微信")

    if sckey:
        desp = text or ""
        if imgs:
            desp += ("\n\n" if desp else "") + "图片已推送至企业微信群：\n" + "\n".join(f"- {i.name}" for i in imgs)
        results.append(send_serverchan(title or "text2img 推送", desp, sckey))
    elif not wecom_only:
        print("未配置 Server酱 SendKey（参数/SERVERCHAN_KEY 均缺），跳过 Server酱")

    return all(results) if results else False
