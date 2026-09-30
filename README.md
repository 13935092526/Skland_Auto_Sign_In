# Skland 终末地自动签到

[AEtherside/skland-daily-attendance](https://github.com/AEtherside/skland-daily-attendance)部分重写

每月15日进行保活提交


## 部署步骤

1. Fork 本仓库到你的 GitHub 账号
2. 进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

   | Secret 名称 | 说明                                    | 必填 |
   | --- |---------------------------------------| --- |
   | `SKLAND_TOKENS` | 森空岛凭据，多个用逗号分隔                         | 是 |
   | `WX_WEBHOOK` | 企业微信群机器人 webhook，**只推送签到日历图片**（日志不推送） | 否 |
   | `SKLAND_NOTIFICATION_URLS` | 未设 `WX_WEBHOOK` 时取其中首个 URL 作为推送地址     | 否 |
   | `SKLAND_MAX_RETRIES` | 单角色失败最大重试次数（默认 3）                     | 否 |
   | `SKLAND_ANONYMOUS` | 设置任意值以隐藏角色名为管理员                       | 否 |

3. 进入 **Actions** 标签页

之后每天 16:00 UTC（北京时间 00:00 后）自动签到；也可在 Actions 页面手动 `Run workflow`。
日志与摘要显示在 Actions 运行汇总页；正常只推送图片，**签到失败时额外推送文字告警**（含原因分析，
若是 `SKLAND_TOKENS` 失效会明确提示重新获取凭据的步骤）。

### 获取凭据

登录[森空岛网页版](https://www.skland.com/)（或鹰角网络通行证）后打开
<https://web-api.skland.com/account/info/hg>，复制整个响应 JSON 或其中的 `content` 值
。

## 项目结构

两层职责分离，根入口 `run.py` 只做编排：

```
run.py                    # 入口：签到取数 → 出图 → 推送（--preview 只出图不推送）
skland_endfield/          # 数据层：只负责签到与获取数据，不依赖 t2i
├─ client.py  crypto.py  device.py  constants.py   # 登录/签名/设备指纹
├─ errors.py              # 失败原因分类（凭据失效/登录态/网络等）+ 处理建议
├─ attendance.py          # 终末地签到执行（含重试），返回原始状态数据
└─ main.py                # 多账号编排 collect()，输出结构化 RunResult
t2i/                      # 展示层：数据 → 图片 → 推送
├─ report.py              # 适配入口：build_account / render_report / push_report / send_report
├─ registry.py  fonts.py  image_io.py              # 模板注册/字体发现/落盘
├─ notify.py                                       # 推送通道（企业微信 text+image，Server酱文字）
└─ templates/endfield_checkin.py                   # 签到日历卡片模板
.github/workflows/attendance.yml                   # 每日定时：安装中文字体后执行 python run.py
.github/workflows/keepalive.yml                    # 每周空 commit 保活，防止 schedule 被 60 天无活动停用
```

本地运行：

```bash
python run.py             # 真实签到 + 推送（凭据/webhook 读 .env 或环境变量）
python run.py --preview   # 测试：照常签到取数出图到 .cache/，不推送
```
