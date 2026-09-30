# Skland 终末地自动签到

[AEtherside/skland-daily-attendance](https://github.com/AEtherside/skland-daily-attendance)部分重写


## 部署步骤

1. Fork 本仓库到你的 GitHub 账号
2. 进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

   | Secret 名称 | 说明 | 必填 |
   | --- | --- | --- |
   | `SKLAND_TOKENS` | 森空岛凭据，多个用逗号分隔 | 是 |
   | `WX_WEBHOOK` | 企业微信群机器人 webhook，**只推送签到日历图片**（日志不推送） | 否 |
   | `SKLAND_NOTIFICATION_URLS` | 兼容旧配置：未设 `WX_WEBHOOK` 时取其中首个 URL 作为推送地址 | 否 |
   | `SKLAND_MAX_RETRIES` | 单角色失败最大重试次数（默认 3） | 否 |
   | `SKLAND_ANONYMOUS` | 设置任意值以隐藏角色名 | 否 |

3. 进入 **Actions** 标签页

之后每天 16:00 UTC（北京时间 00:00 后）自动签到；也可在 Actions 页面手动 `Run workflow`。
签到日志与执行摘要写在每次运行的 **Job Summary 汇总页**（`$GITHUB_STEP_SUMMARY`），不推送文字消息。

### 获取凭据

登录[森空岛网页版](https://www.skland.com/)（或鹰角网络通行证）后打开
<https://web-api.skland.com/account/info/hg>，复制整个响应 JSON 或其中的 `content` 值
（两种格式都支持，工具会自动提取）。

## 项目结构

两层职责分离，根入口 `run.py` 只做编排：

```
run.py                    # 入口：签到取数 → 出图 → 推送（--preview 只出图不推送）
skland_endfield/          # 数据层：只负责签到与获取数据，不依赖 t2i
├─ client.py  crypto.py  device.py  constants.py   # 登录/签名/设备指纹
├─ attendance.py          # 终末地签到执行（含重试），返回原始状态数据
└─ main.py                # 多账号编排 collect()，输出结构化 RunResult
t2i/                      # 展示层：数据 → 图片 → 推送
├─ report.py              # 适配入口：build_account / render_report / push_report / send_report
├─ registry.py  fonts.py  image_io.py              # 模板注册/字体发现/落盘
├─ notify.py                                       # 推送通道（企业微信 text+image，Server酱文字）
└─ templates/endfield_checkin.py                   # 签到日历卡片模板
.github/workflows/attendance.yml                   # 每日定时：安装中文字体后执行 python run.py
```

本地运行：

```bash
python run.py             # 真实签到 + 推送（凭据/webhook 读 .env 或环境变量）
python run.py --preview   # 测试：照常签到取数出图到 .cache/，不推送
```

## 签到日历图片

配置 `WX_WEBHOOK` 后，每次运行会把各角色**当月签到状态**渲染成一张日历卡片图片推送到企业微信群；
**webhook 通道只发图片，不推文字**，执行日志在 Actions 汇总页查看
（图片上限 2MB，仅企业微信群机器人支持发图）。

- 每个终末地角色一张卡片：标题为**角色昵称 + UID**，右上角是**今日签到状态**
- 卡片主体是**当月日历**：已签的格子显示当天所得奖励，漏签显示「未签到」，未到期显示「可领取」，
  当天的格子带金框与「今」角标
- 数据取自签到接口返回的 `calendar` / `resourceInfoMap` / `hasToday`，月份以服务端 `currentTs`（东八区）为准
- `SKLAND_ANONYMOUS` 置任意值时，卡片上的昵称显示为「管理员」
- 渲染或推送失败只打日志，**不影响签到结果**

实现位于 `t2i/report.py`（数据适配 → 图片 → 推送）与 `t2i/templates/endfield_checkin.py`（卡片样式），
字体发现、企业微信/Server酱推送通道均在 `t2i` 包内。本地调试时把 webhook 放进
项目根的 `.env`（`WX_WEBHOOK=...`，已被 `.gitignore` 忽略）即可，无需导出环境变量。

## 工作原理

- 每天定时执行一次，服务端会返回"今天已经签到过了"，因此**无需本地签到状态存储**（原版为每 2 小时重试的常驻服务才需要）
- 签到链路：鹰角 OAuth 授权 → 森空岛换取 cred/token → 数美设备指纹（通过 Actions cache 跨运行复用）→ 签名请求 → 终末地按角色逐个签到
- 签到过程中顺带收集每个角色的签到状态，运行结束时统一出图推送图片；日志/摘要写入 Actions Job Summary
- 签到失败不会使 workflow 报错（与原版一致），仅输出 `::warning::`，可手动重跑
