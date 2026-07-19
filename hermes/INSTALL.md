# Hermes Skill 与 Reminder Consumer 安装

本目录是 Subscription Manager 的 Hermes 集成包。安装者必须先阅读 `SKILL.md`，将 `tools.json` 注册为函数契约，并保留 `scripts/call_tool.py` 与 `references/`、`examples/` 的相对结构。

## 1. 安装位置

不同 Hermes 发行版的 Skill 目录和注册命令可能不同。执行者应先检查当前 Hermes 的官方/本地配置，使用其受支持的 Skill 安装机制，将整个仓库 `hermes/` 目录复制或链接为一个 Skill；不得只复制 `SKILL.md` 或 `tools.json`。

安装后 Hermes 必须能够读取：

```text
hermes/
├─ SKILL.md
├─ INSTALL.md
├─ tools.json
├─ scripts/call_tool.py
├─ references/api.md
├─ references/errors.md
└─ examples/conversations.md
```

调用脚本只依赖 Python 3 标准库，不需要安装 Backend Python 依赖。

## 2. 密钥配置

在 Hermes 的 service environment、credential store 或 secret manager 中配置：

```text
HERMES_SUBSCRIPTION_API_URL=https://subscriptions.example.com
HERMES_SUBSCRIPTION_API_TOKEN=<one-time-revealed token>
```

URL 是用户访问 Subscription Manager 的 HTTPS origin，不含 `/api/v1`，也不是 Backend 容器地址。Token 使用稳定、唯一的 Hermes Actor ID，推荐 scopes：

```text
subscriptions:read subscriptions:write payments:write analytics:read audit:read reminders:consume
```

不要把 Token 写入 Skill 文件、仓库 `.env`、定时任务文本、命令历史或聊天消息。更新 Hermes 服务环境后，按该发行版要求安全 reload/restart，并确认其他用户无法读取 secret。

## 3. 连通性与 Tool 验收

在加载了上述两个环境变量的 Hermes 运行身份下执行：

```bash
python3 /path/to/hermes/scripts/call_tool.py upcoming_events --arguments '{"days":30}'
python3 /path/to/hermes/scripts/call_tool.py analytics_summary --arguments '{}'
```

成功响应包含 `"ok":true`、HTTP status 和 request ID。若失败，先按 `references/errors.md` 判断是 URL、TLS、代理重定向、scope、Token 撤销还是 API 校验问题。禁止临时关闭 TLS 校验或改用数据库直连。

随后让 Hermes 通过自然语言查找一条订阅。写操作必须先复述实际参数并获得用户明确确认；不得为了测试跳过确认。

## 4. 唯一 Reminder Consumer

Subscription Manager 的 Scheduler 只维护 Reminder Outbox，不会直接发送通知。使用 Hermes 自己的周期任务/自动化机制创建恰好一个任务，建议每 5 分钟运行一次，任务身份使用上述 Token。

推荐任务指令：

```text
执行 Subscription Manager 到期提醒消费。调用 reminders_claim，limit=20。
对每一条领取结果，通过当前 Hermes 为所有者配置的默认通知渠道发送用户可读消息，
内容包含订阅名称、事件类型、事件日期、金额与币种（如有）、自动续费状态以及是否补发。
只有渠道明确返回成功后才调用 reminder_ack。
渠道失败、超时或结果不确定时调用 reminder_fail，并传递不含凭据和隐私数据的简短错误。
没有待处理项时安静结束，不发送“无提醒”消息。
不得在发送前 ack，不得自行修改订阅，不得并发启动第二个消费者。
```

首次启用时观察至少一次任务运行和 Subscription Manager 审计。若 Hermes 任务可能运行超过 `REMINDER_LEASE_SECONDS`，应减少 claim limit 或缩短单次发送链路，而不是启动并发消费者。

## 5. 功能边界

- Hermes 可查询、创建、编辑、计划取消/撤销取消、归档/恢复订阅，维护提醒规则，记录/查询付款，查看事件、统计和审计。
- “计划取消”只更新本系统生命周期，不会替用户登录供应商并取消外部订阅。
- `payment_record` 只有关联当前 planned billing event 且明确 `advance_schedule=true` 时才推进账期；历史补录使用 false。
- Token 管理、管理员密码恢复、备份恢复和基础设施变更不暴露为日常 Hermes Tool。

## 6. 升级和 Token 轮换

升级仓库后重新加载整个 `hermes/` 目录，并执行两条只读验收命令。Token 轮换顺序为：创建最小权限新 Token → 更新 Hermes secret → 验证只读调用和 Reminder Consumer → 撤销旧 Token。不得先撤销仍在运行任务使用的 Token。
