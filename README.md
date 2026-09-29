# Skland 终末地自动签到（Python + GitHub Actions）

提取自 [AEtherside/skland-daily-attendance](https://github.com/AEtherside/skland-daily-attendance)
中的**明日方舟：终末地**签到部分，用纯 Python 重写，通过 GitHub Actions 定时运行，
无需服务器，已去除多账号 KV 存储、Nitro/Cloudflare 部署、多通知渠道适配等不必要代码。

## 部署步骤

1. Fork 本仓库到你的 GitHub 账号
2. 进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

   | Secret 名称 | 说明 | 必填 |
   | --- | --- | --- |
   | `SKLAND_TOKENS` | 森空岛凭据，多个用逗号分隔 | 是 |
   | `SKLAND_NOTIFICATION_URLS` | 通知 URL，多个逗号分隔（Server酱/Bark/pushplus/通用 webhook） | 否 |
   | `SKLAND_MAX_RETRIES` | 单角色失败最大重试次数（默认 3） | 否 |
   | `SKLAND_ANONYMOUS` | 设置任意值以隐藏角色名 | 否 |

3. 进入 **Actions** 标签页，点击 *I understand my workflows, go ahead and enable them* 启用工作流

之后每天 16:00 UTC（北京时间 00:00 后）自动签到；也可在 Actions 页面手动 `Run workflow`。

### 获取凭据

登录[森空岛网页版](https://www.skland.com/)（或鹰角网络通行证）后打开
<https://web-api.skland.com/account/info/hg>，复制整个响应 JSON 或其中的 `content` 值
（两种格式都支持，工具会自动提取）。

## 工作原理

- 每天定时执行一次，服务端会返回"今天已经签到过了"，因此**无需本地签到状态存储**（原版为每 2 小时重试的常驻服务才需要）
- 签到链路：鹰角 OAuth 授权 → 森空岛换取 cred/token → 数美设备指纹（通过 Actions cache 跨运行复用）→ 签名请求 → 终末地按角色逐个签到
- 签到失败不会使 workflow 报错（与原版一致），仅输出 `::warning::`，可手动重跑

## 代码结构

```
.github/workflows/attendance.yml   定时签到工作流
skland_endfield/
  constants.py                     常量（appCode、API 地址、UA 等）
  crypto.py                        md5 / hmac-sha256 / RSA / DES / AES / gzip
  device.py                        数美设备指纹 did 注册
  client.py                        森空岛 API 客户端（登录、签名请求、终末地签到）
  attendance.py                    终末地签到流程（角色展开、校验、重试、奖励文案）
  notify.py                        消息收集与推送通知
  main.py                          入口（读取环境变量、多账号处理、执行摘要）
```

本地调试（可选）：`pip install -r requirements.txt` 后设置 `SKLAND_TOKENS` 环境变量，
运行 `python -m skland_endfield`。

## 注意

- 仅供学习和研究使用，请勿频繁调用 API，以免影响账号安全
- 仓库长期无提交/无活动时 GitHub 会自动停用 Actions，需保持仓库有一定活跃度或手动重启用
