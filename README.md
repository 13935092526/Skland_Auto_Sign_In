# Skland 终末地自动签到

[AEtherside/skland-daily-attendance](https://github.com/AEtherside/skland-daily-attendance)部分重写


## 部署步骤

1. Fork 本仓库到你的 GitHub 账号
2. 进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

   | Secret 名称 | 说明 | 必填 |
   | --- | --- | --- |
   | `SKLAND_TOKENS` | 森空岛凭据，多个用逗号分隔 | 是 |
   | `SKLAND_NOTIFICATION_URLS` | 通知 URL，多个逗号分隔（Server酱/Bark/pushplus/通用 webhook） | 否 |
   | `WX_WEBHOOK` | 企业微信群机器人 webhook，配置后额外推送签到日历**图片** | 否 |
   | `SKLAND_MAX_RETRIES` | 单角色失败最大重试次数（默认 3） | 否 |
   | `SKLAND_ANONYMOUS` | 设置任意值以隐藏角色名 | 否 |

3. 进入 **Actions** 标签页

之后每天 16:00 UTC（北京时间 00:00 后）自动签到；也可在 Actions 页面手动 `Run workflow`。

### 获取凭据

登录[森空岛网页版](https://www.skland.com/)（或鹰角网络通行证）后打开
<https://web-api.skland.com/account/info/hg>，复制整个响应 JSON 或其中的 `content` 值
（两种格式都支持，工具会自动提取）。

## 签到日历图片

配置 `WX_WEBHOOK` 后，每次运行会把各角色**当月签到状态**渲染成一张日历卡片图片推送到企业微信群
（图片上限 2MB，仅企业微信群机器人支持发图，Server酱/Bark 等仍只能收文字）。

- 每个终末地角色一张卡片：标题为**角色昵称 + UID**，右上角是**今日签到状态**
- 卡片主体是**当月日历**：已签的格子显示当天所得奖励，漏签显示「未签到」，未到期显示「可领取」，
  当天的格子带金框与「今」角标
- 数据取自签到接口返回的 `calendar` / `resourceInfoMap` / `hasToday`，月份以服务端 `currentTs`（东八区）为准
- `SKLAND_ANONYMOUS` 置任意值时，卡片上的昵称显示为「管理员」
- 渲染或推送失败只打日志，**不影响签到结果**与原有的文字通知渠道

实现位于 `skland_endfield/report.py`（数据 → 图片 → 推送）与内嵌的 `t2i/` 渲染库
（模板 `t2i/templates/endfield_checkin.py`，样式与字体发现均在库内）。本地调试时把 webhook 放进
项目根的 `.env`（`WX_WEBHOOK=...`，已被 `.gitignore` 忽略）即可，无需导出环境变量。

## 工作原理

- 每天定时执行一次，服务端会返回"今天已经签到过了"，因此**无需本地签到状态存储**（原版为每 2 小时重试的常驻服务才需要）
- 签到链路：鹰角 OAuth 授权 → 森空岛换取 cred/token → 数美设备指纹（通过 Actions cache 跨运行复用）→ 签名请求 → 终末地按角色逐个签到
- 签到过程中顺带收集每个角色的签到状态，运行结束时统一出图推送
- 签到失败不会使 workflow 报错（与原版一致），仅输出 `::warning::`，可手动重跑
