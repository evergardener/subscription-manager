<!--
  Source: Hermes_Subscription_Manager_Development_Spec.docx
  Converted to Markdown for ongoing maintenance.
-->

# Hermes 订阅与数字服务管理系统

> 产品需求与技术开发规格说明书（交付 Codex 实施）

版本：v1.1
日期：2026-07-16
定位：Self-hosted-first / API-first / Hermes-first

文档目标

本文件用于指导 Codex 从零实现一套独立的个人订阅与数字服务生命周期管理系统。系统以 Web/PWA 为人工操作界面，以 REST API 为稳定边界，以 Hermes Tool/Skill 为自然语言入口，由独立 Scheduler 维护提醒 Outbox、Hermes 完成最终通知。

### 文档状态与规范用语

- 本版本由原 v1.0 Word 规格转换并增补，作为后续维护的唯一主文档；原 DOCX 仅作为历史来源保留。
- “必须/不得”表示 MVP 验收的强制要求；“应”表示默认必须满足，除非在决策记录中说明偏离原因；“建议/可”不阻断 MVP 验收。
- `DEC-*` 用于记录已经确认的关键产品/架构决策；实现不得在未新增决策记录的情况下偏离。
- 规格优先级：数据正确性 > 安全边界 > 可审计与可恢复 > API 兼容性 > 使用便利性。

## 1. 项目概述

### 1.1 项目背景

现有 Android 订阅管理产品通常侧重普通消费订阅，缺少适合 AI 服务、VPS、域名、软件授权、云服务、证书、会员和自托管外围服务的字段、自动化接口与审计能力。本项目不追求复制 Pandora 的全部商业产品能力，而是构建一个可长期演进、可被 Hermes 稳定调用的个人数字服务管理底座。

### 1.2 产品定位

- 独立服务：订阅系统不依赖 Hermes 存活，Hermes 只是主要交互入口之一。

- Self-hosted-first：业务数据默认保存在用户自有 PostgreSQL 中，不依赖第三方 SaaS。MVP 不承诺客户端本地副本、离线写入或多端同步，因此不使用严格意义上的 local-first 数据模型。

- API-first：所有核心操作均通过受控 API 完成，Web UI、Hermes 和 Scheduler 共用同一业务层。

- 生命周期管理：除金额与续费外，还管理试用、到期、取消截止、自动续费、授权数量、使用价值和归档。

- 可审计：所有由 Hermes 或自动化执行的写操作必须可追踪、可回滚或至少可人工修正。

### 1.3 成功标准

| 目标 | 验收标准 |
| --- | --- |
| 可替代普通订阅 App | 可以在手机 PWA 中完成新增、编辑、续费查看、提醒配置和统计。 |
| Hermes 可用 | MVP 中 Hermes 能可靠执行查询、新增、修改、归档和记录付款；月度复盘属于第二阶段。 |
| 提醒可靠 | 相同提醒不重复发送；错过执行窗口后可补发；提醒记录可查询。 |
| 数据准确 | 预计账单与实际付款分离；周期计算覆盖月末、闰年和自定义周期。 |
| 可维护 | 提供 Alembic migration、结构化日志、备份说明、健康检查和基础测试。 |

## 2. 范围定义

### 2.1 MVP 必须实现

- 订阅/服务 CRUD、软删除与归档。

- 分类、标签、供应商、官网、Logo URL、备注。

- 固定周期：日、周、月、季度、半年、年；自定义 interval_count。

- 下次账单日、服务到期日、试用结束日、取消截止日。

- 自动续费状态、付款方式描述、预计金额与币种。

- 多提前量提醒，例如 30/7/3/1 天。

- 月度与年度预计支出统计；MVP 按币种分别汇总，不在缺少汇率时跨币种相加。

- 实际付款记录。

- Hermes Tool/Skill：查询、新增、修改、归档、记录付款。

- 独立 scheduler 维护事件和可靠 Reminder Outbox；Hermes 负责最终通知并通过领取/确认接口反馈结果。第一版不绑定 ntfy 或具体通知供应商。

- 响应式 Web UI，可安装为 PWA。

- 操作审计日志。

### 2.2 第二阶段建议实现

- 汇率换算和统一基准币种统计。

- 价格历史与涨价标记。

- 月度使用价值评价。

- CSV/JSON 导入导出。

- 日历视图。

- 模板库与 Logo 缓存。

- 月度订阅复盘报告。

- 邮件账单抽取接口。

### 2.3 明确不在 MVP 范围

- 银行卡直连和自动抓取银行流水。

- Play Store 正式上架的 Android 原生客户端。

- 多人团队、企业审批和复杂 RBAC。

- 自动登录第三方网站取消订阅。

- 基于使用行为的全自动取消决策。

- 完整 OCR 票据识别。

### 2.4 MVP 范围矩阵

| 能力 | MVP | 第二阶段 | 说明 |
| --- | --- | --- | --- |
| 订阅、计费计划、关键日期、分类、标签 | 必须 | 增强 | MVP 覆盖完整 CRUD、归档与恢复。 |
| 提醒与投递记录 | 必须 | 增强渠道 | MVP 提供 external Outbox，必须支持幂等、失败记录和补发。 |
| 实际付款与基础统计 | 必须 | 对账增强 | MVP 按币种输出预计与实际，不进行隐式汇率换算。 |
| Dashboard、列表、详情、表单、Settings 基础项 | 必须 | 增强 | Settings 的导入导出、OIDC 管理界面不属于 MVP。 |
| Calendar 页面 | 否 | 是 | MVP 通过 Upcoming Events 列表展示未来事件。 |
| 汇率与统一基准币种统计 | 基础版 | 增强 | Dashboard 使用 ECB 最新工作日参考汇率估算下月人民币总额，必须显示来源与日期；缺失任何币种汇率时不得生成不完整总额。 |
| Usage Review、月度复盘 | 否 | 是 | MVP 不实现对应 API、Tool 和 UI。 |
| CSV/JSON 导入导出、价格历史、邮件解析 | 否 | 是 | 不创建仅供占位的未完成入口。 |

## 3. 总体架构

```text
Android / Desktop Browser
          │
          ▼
     React PWA
          │ HTTPS / JSON
          ▼
       FastAPI ◄──────── Hermes Tool/Skill
          │                    │
  ┌───────┴───────────┐        ├─ Natural-language operations
  ▼                   ▼        └─ Recurring reminder consumer
PostgreSQL         Scheduler
  ▲                   │
  └──── Reminder Outbox maintenance
```

### 3.1 组件职责

| 组件 | 职责 | 禁止事项 |
| --- | --- | --- |
| React PWA | 人工录入、编辑、筛选、统计、移动端使用 | 不得直接访问数据库 |
| FastAPI | 鉴权、校验、业务规则、周期计算、审计、API | 不得把业务逻辑散落在 Router |
| PostgreSQL | 主数据、账单、提醒、付款、审计 | 不得由 Hermes 直接写 SQL |
| Scheduler | 独立进程扫描到期事件、生成 Reminder Outbox、维护重试和补偿状态 | 不得自行发送最终通知或绕过 service 层修改订阅核心数据 |
| Hermes Tool/Skill | 自然语言解析、调用 API、组织回复，并由单一周期任务消费 Reminder Outbox | 不得绕过 API、自行推断写入关键日期或在未确认投递时 ack |

### 3.2 推荐技术栈

| 层 | 推荐 | 说明 |
| --- | --- | --- |
| Backend | Python 3.12 + FastAPI + Pydantic v2 | 开发效率高，适合 Hermes Tool 与自动化。 |
| ORM | SQLAlchemy 2.x | 使用 typed declarative model。 |
| Migration | Alembic | 所有 schema 变更必须 migration 化。 |
| Database | PostgreSQL 16+ | 可使用用户现有 PostgreSQL。 |
| Frontend | React + TypeScript + Vite | 响应式 PWA。 |
| UI | shadcn/ui + Tailwind CSS | 现代、可控、适合移动端。 |
| Query | TanStack Query | 缓存、失效与 API 状态管理。 |
| Scheduler | APScheduler 独立进程/容器 | MVP 的唯一事件与 Outbox 维护责任方。 |
| Tests | pytest + httpx + Playwright | 后端单元/集成测试，前端关键流程 E2E。 |
| Deployment | Docker Compose 优先；同时提供 systemd 文档 | 服务独立部署。 |

## 4. 领域模型与数据结构

### 4.1 核心概念

| 概念 | 定义 |
| --- | --- |
| Subscription | 一个持续付费或有明确生命周期的数字服务。 |
| Billing Plan | 当前预计计费规则，不代表实际已付款。 |
| Billing Event | 根据计划生成的某次预期扣费/到期事件。 |
| Payment | 实际付款记录，可与 Billing Event 关联。 |
| Reminder Rule | 相对某类事件的提前提醒配置。 |
| Reminder Delivery | 某次提醒的实际发送结果，用于幂等与审计。 |
| Usage Review | 按月或自定义周期记录使用价值与保留决策。 |
| Audit Log | 所有关键写操作的 before/after 记录。 |

### 4.2 数据库表

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| subscriptions | id, name, vendor, category_id, status, website, logo_url, description, start_date, archived_at | 服务主表。 |
| billing_plans | subscription_id, amount, currency, interval_unit, interval_count, anchor_date, next_billing_date, auto_renew, billing_mode | 当前计费规则。 |
| billing_events | subscription_id, billing_plan_id, event_type, event_date, amount, currency, status | 持久化预期账单与生命周期事件。 |
| service_dates | subscription_id, trial_end_date, service_expiry_date, cancellation_deadline, contract_end_date | 每个订阅最多一条当前记录。 |
| payments | id, subscription_id, amount, currency, paid_at, tax_amount, source, external_ref, billing_event_id | 实际付款；可关联一个 Billing Event。 |
| reminder_rules | id, subscription_id, event_type, offset_days, channel, enabled | 支持多规则。 |
| reminder_deliveries | event_key, rule_id, scheduled_for, sent_at, status, attempt_count, error | 幂等与补偿。 |
| categories | name, icon, sort_order | 用户可维护。 |
| tags / subscription_tags | tag name 与关联表 | 多标签。 |
| usage_reviews（第二阶段） | period, usage_level, value_rating, decision, notes | 不进入 MVP migration。 |
| audit_logs | actor_type, actor_id, action, entity_type, entity_id, before_json, after_json, request_id | 写操作审计。 |

### 4.3 枚举建议

```text
subscription_status: active | trial | pending_cancel | paused | cancelled | expired
interval_unit: day | week | month | year
billing_mode: fixed | usage_based | one_time | free
reminder_event_type: billing | expiry | trial_end | cancellation_deadline | contract_end
billing_event_status: planned | reconciled | superseded | cancelled
usage_level: unused | low | medium | high
review_decision: keep | review | downgrade | cancel
actor_type: user | hermes | system | import
```

### 4.4 关键约束

- 金额使用 NUMERIC(18,6)，严禁 float。

- 币种使用 ISO 4217 三字符代码。

- 业务日期使用 DATE；发送时间和审计时间使用 TIMESTAMPTZ。

- 删除默认软删除，核心记录不执行物理 DELETE。

- reminder_deliveries.event_key 必须唯一，建议格式：subscription_id:event_type:event_date:offset_days:channel。

- 每个 subscription 同一时间仅允许一个 active billing_plan；历史计划可保留 valid_from/valid_to。

- 所有外部写请求支持 Idempotency-Key。

### 4.5 所有核心表的通用字段与约束

- 主键统一使用 UUID；API 中按不透明字符串处理，不暴露数据库自增规律。
- 可变核心资源必须包含 `created_at`、`updated_at` 和整数 `version`；更新时间使用 `TIMESTAMPTZ`，乐观锁以 `version` 为准。
- 所有外键必须显式定义删除行为。订阅归档不得级联物理删除计划、付款、投递或审计记录。
- `billing_plans` 必须包含 `id`、`valid_from`、`valid_to`；通过数据库约束或事务锁保证每个订阅最多一个当前有效计划。
- `categories.name`、`tags.name` 在大小写归一化后唯一；名称必须去除首尾空白且不能为空。
- `amount`、`tax_amount` 必须有明确正负规则；MVP 的普通付款金额大于零，退款/冲销在第二阶段建模，不允许用负付款绕过业务规则。
- `interval_count` 必须为正整数，并设置合理上限；`offset_days` 必须为非负整数。
- URL 字段只允许 `http`/`https`。后端不得在未做 SSRF 防护时主动抓取用户提供的 Logo URL。
- 审计日志为追加写；普通业务 API 不提供修改或删除审计记录的能力。

### 4.6 Subscription 状态机

归档是由 `archived_at` 表示的正交状态，不再使用 `status=archived`，从而避免丢失归档前的业务状态。

| 当前状态 | 可转换到 | 触发条件/副作用 |
| --- | --- | --- |
| trial | active | 试用转付费或用户确认继续；保留试用历史。 |
| trial | pending_cancel | 用户决定试用结束后不续费；设置 `auto_renew=false`。 |
| active | pending_cancel | 已提交取消或决定不再续费；必须记录预计权益失效日。 |
| active/trial | paused | 服务暂停；暂停期间默认不生成 billing 事件，但保留 expiry/contract 提醒。 |
| paused | active/trial | 人工恢复；恢复目标必须显式指定并审计。 |
| pending_cancel | active | 撤销取消计划；必须显式恢复 `auto_renew` 选择。 |
| pending_cancel | cancelled | 到达 `service_expiry_date`，或用户确认权益已终止。 |
| active/trial/paused | expired | 非用户主动取消且权益自然失效。 |
| cancelled/expired | active | 重新订阅；必须创建新 Billing Plan，不复用已关闭计划。 |

- `pending_cancel` 在 `service_expiry_date` 前仍被视为可使用，但不得生成失效日之后的 billing 事件。
- archive/restore 不改变上述业务状态；恢复后回到归档前状态。
- 所有状态转换必须经过 domain service，校验必需日期并写入审计日志；不得用通用 PATCH 绕过转换规则。

## 5. 核心业务规则

### 5.1 周期计算

- 月度周期使用“日历月”而不是固定 30 天。

- 锚定日期为 29/30/31 日时，目标月份无该日期则使用当月最后一天。

- 从短月进入长月时应保留原始 anchor_day，不能永久漂移到 28 日。

- 年度周期必须覆盖 2 月 29 日；非闰年默认落到 2 月最后一天。

- 季度和半年以 interval_unit=month、interval_count=3/6 表达。

- 按量付费允许 next_billing_date 为空，但可设置账单结算提醒。

### 5.2 日期语义

| 字段 | 含义 |
| --- | --- |
| next_billing_date | 预计下一次扣费日期。 |
| service_expiry_date | 当前权益真正失效日期。 |
| trial_end_date | 试用结束日期，可能与首次扣费日期不同。 |
| cancellation_deadline | 必须在此日期前取消，避免下一周期扣费。 |
| contract_end_date | 长期合同或年约结束日期。 |

- 所有业务日期按部署配置时区解释，默认 `Asia/Shanghai`；数据库中的发送和审计时间统一存 UTC。
- `cancellation_deadline` 在 MVP 中按“截止日当天仍可操作”解释；提醒日等于 `deadline - offset_days`。
- 周末和法定节假日不自动顺延；若以后需要工作日规则，应作为独立功能实现。

### 5.3 提醒幂等与补偿

1. 调度器每天至少运行一次，扫描未来 N 天内的事件。

2. 生成稳定 event_key，并先尝试插入 reminder_deliveries。

3. 若唯一键冲突且状态为 sent 或仍待处理，则跳过重复生成。

4. Hermes 以 `reminders:consume` Token 原子领取 due delivery；领取记录 actor 所有权和有限租约。

5. 若系统停机导致错过发送，恢复后在 grace_window_days 内补发，并在文案中标识“补发”。

6. 领取必须使用数据库原子操作或等价锁机制；只有领取 actor 可在租约内 ack/fail。租约过期的 processing 项可重新领取，避免消费者故障导致永久丢失。

7. 默认 `max_attempts=5`，采用指数退避并设置上限；超过上限进入 `dead` 状态，仍可人工重试并保留历史错误。

8. 默认 `grace_window_days=3`；超过窗口的提醒不补发，但必须记录为 `expired` 以便审计。

### 5.4 多币种与统计规则

- MVP 的所有汇总响应按币种分组，例如 `USD 100` 与 `CNY 50` 必须分别展示。
- 未提供受信汇率及汇率日期时，系统不得输出跨币种“总计”。Dashboard 可使用 ECB 最新工作日欧元参考汇率交叉换算人民币估算值，必须同时显示来源、汇率日期，并在任一币种缺少参考汇率时停止合计。
- 预计统计基于计费计划或预期事件；实际统计只基于 Payment。二者必须分别返回，不得用实际付款覆盖历史预计值。
- 金额计算全程使用 Decimal；API 使用十进制字符串，展示层按币种规则格式化，但不得因此丢失数据库精度。

### 5.5 付款与计划推进

Payment 创建请求显式支持 `billing_event_id` 和 `advance_schedule`：

- 当前周期的正常付款默认 `advance_schedule=true`；历史补录默认 `false`。
- `advance_schedule=true` 仅适用于当前有效 fixed Billing Plan，且付款必须关联当前 `next_billing_date` 对应的 Billing Event。
- 推进时从原始 anchor 计算下一个周期，不能以实际付款日作为新 anchor，也不能因月末回退产生永久日期漂移。
- 同一 Billing Event 的重复付款请求必须由 Idempotency-Key 阻止重复推进。计划已经推进后再次请求推进，返回幂等结果或 409，不得推进第二次。
- 历史补录、未关联事件、按量付费或存在多个候选事件时不得自动推进；若调用方仍请求推进，返回 422 并要求明确选择。
- 实际付款金额可以与预计金额不同；原 Billing Event 的预计金额保持不变，Payment 保存实际金额。
- 一个 Billing Event 可以关联零或多笔 Payment。存在关联 Payment 后事件状态变为 `reconciled`，但 MVP 不推断“足额/部分付款”。
- Payment 服务和周期推进必须在同一事务中完成，并分别写入审计变更；不得使用 ORM hook 隐式推进。
- Hermes 在记录付款前必须复述金额、币种、付款时间、关联事件以及是否推进账期。

### 5.6 Billing Event 生成与变更

- Billing Event 持久化保存，默认生成未来 366 天范围内的事件；订阅或计划创建/修改后立即补齐，scheduler 每日继续滚动补齐。
- billing、expiry、trial_end、cancellation_deadline、contract_end 使用统一事件结构；非 billing 事件的 amount/currency 可以为空。
- 同一来源计划、事件类型和事件日期必须唯一，重复生成必须幂等。
- 已发生、已 reconciled 或已被通知引用的历史事件不可覆盖或物理删除。
- 修改计费计划时，将尚未发生且未 reconciled 的旧计划未来事件标记为 `superseded`，再根据新计划生成事件；审计必须能关联新旧计划和事件。
- `pending_cancel` 不生成权益失效日之后的 billing 事件；已有未来事件标记为 `cancelled`。撤销取消计划后按当前有效计划重新生成。
- Upcoming Events 默认仅返回 `planned` 事件；审计/历史查询可以显式包含其他状态。

## 6. API 设计

### 6.1 通用规范

- Base path：/api/v1。

- 统一 JSON error schema：code、message、details、request_id。

- MVP 分页统一使用 `page/page_size`，`page` 从 1 开始，默认 `page_size=20`，最大 100；响应包含 `items`、`page`、`page_size`、`total`。

- 所有写接口返回更新后的完整资源。

- 危险操作采用 archive/restore，不提供普通硬删除接口。

- 支持 `Idempotency-Key`。`X-Actor-Type`、`X-Actor-Id` 仅允许由受信认证中间件生成；不得信任外部请求自行提交的 Actor Header。
- 所有可变资源返回 `version`；PATCH 必须携带 `expected_version` 或 `If-Match`，版本冲突返回 HTTP 409 和当前版本摘要。
- Idempotency-Key 按“认证主体 + Method + Path + Key”确定作用域，至少保留 24 小时；同一 Key 但请求体哈希不同返回 HTTP 409。
- 错误状态至少统一覆盖：400 格式错误、401 未认证、403 无权限、404 不存在、409 幂等/版本冲突、422 业务校验失败、429 限流、500 内部错误。

### 6.2 MVP Endpoint

| Method | Path | 用途 |
| --- | --- | --- |
| GET | /subscriptions | 列表、筛选、搜索、排序。 |
| POST | /subscriptions | 创建订阅及初始计费计划。 |
| GET | /subscriptions/{id} | 详情。 |
| PATCH | /subscriptions/{id} | 部分更新；不得直接变更 status 或 archived_at。 |
| POST | /subscriptions/{id}/status-transitions | 执行受控状态转换，输入 target_status、reason 和必需日期。 |
| POST | /subscriptions/{id}/archive | 归档。 |
| POST | /subscriptions/{id}/restore | 恢复。 |
| GET | /subscriptions/{id}/payments | 付款历史。 |
| POST | /subscriptions/{id}/payments | 记录实际付款；支持 billing_event_id 和 advance_schedule。 |
| GET/PUT | /subscriptions/{id}/reminder-rules | 查询或整体替换提醒规则；PUT 支持乐观锁。 |
| GET/POST/PATCH | /categories | 分类查询与维护。 |
| GET/POST/PATCH | /tags | 标签查询与维护。 |
| GET | /events/upcoming | 未来账单、到期、试用和取消截止。 |
| POST | /reminders/scan | 管理员或兼容调用者手动触发事件/Outbox 维护；正常运行由 scheduler 周期执行。 |
| POST | /reminders/claim | Hermes 使用 `reminders:consume` Token 原子领取到期 Outbox。 |
| POST | /reminders/deliveries/{id}/ack | 领取 actor 确认最终通知成功。 |
| POST | /reminders/deliveries/{id}/fail | 领取 actor 报告失败并进入退避重试或 dead。 |
| GET | /analytics/summary | 月度/年度预计和实际支出。 |
| GET | /audit-logs | 审计查询。 |
| GET | /health/live | 进程存活检查，不依赖数据库。 |
| GET | /health/ready | 就绪检查，验证数据库与必要依赖。 |
| POST | /auth/login | 本地管理员登录，建立同源 HttpOnly Session。 |
| POST | /auth/logout | 注销当前 Session 并清除 Cookie。 |
| GET | /auth/session | 返回当前会话主体和 CSRF 信息。 |
| GET/POST/DELETE | /api-tokens | 查询、创建和撤销 scoped API Token；明文只在创建时返回一次。 |

第二阶段 Endpoint：`/subscriptions/{id}/reviews`、导入导出、汇率和价格历史接口。MVP OpenAPI 中不得暴露返回 501 的占位业务接口。

### 6.3 创建订阅示例

```text
POST /api/v1/subscriptions
{
  "name": "Claude Max",
  "vendor": "Anthropic",
  "category": "AI",
  "status": "active",
  "website": "https://claude.ai",
  "billing_plan": {
    "amount": "100.00",
    "currency": "USD",
    "interval_unit": "month",
    "interval_count": 1,
    "anchor_date": "2026-07-21",
    "next_billing_date": "2026-08-21",
    "auto_renew": true,
    "billing_mode": "fixed"
  },
  "service_dates": {
    "cancellation_deadline": "2026-08-20"
  },
  "reminder_rules": [
    {"event_type": "billing", "offset_days": 5, "channel": "external"},
    {"event_type": "billing", "offset_days": 1, "channel": "external"}
  ]
}
```

### 6.4 记录当前周期付款示例

```json
POST /api/v1/subscriptions/{id}/payments
Idempotency-Key: 8d7c8b65-...

{
  "billing_event_id": "4e8f...",
  "amount": "100.00",
  "currency": "USD",
  "paid_at": "2026-08-21T09:30:00+08:00",
  "advance_schedule": true,
  "expected_version": 7
}
```

成功响应必须同时返回 `payment`、更新后的 `billing_plan`、被 reconciliation 的 `billing_event`、`schedule_advanced=true` 和新的资源版本。历史补录将 `advance_schedule` 设为 false；存在歧义时返回 422，并在 details 中给出候选 Billing Event，不得猜测。

## 7. Hermes 集成规格

### 7.1 集成原则

- Hermes 不直接连接 PostgreSQL。

- Hermes 所有写操作必须调用 API，并使用绑定 `actor_type=hermes` 的专用凭据；Actor 身份由服务端认证层产生。

- 涉及金额、币种、周期、日期不明确时，Tool 应返回 validation error，而不是猜测。

- 归档、修改金额、修改续费周期属于重要写操作，Hermes 应在自然语言层向用户复述关键字段后再执行。

- API 本身仍需校验，不能只依赖 Prompt。

### 7.2 Tool 列表

| Tool | 输入 | 输出 |
| --- | --- | --- |
| subscription_search | query, status, category, date range | 匹配订阅简表。 |
| subscription_get | subscription_id | 完整详情。 |
| subscription_create | 结构化创建参数 | 创建结果与 warnings。 |
| subscription_update | id + patch + expected_version | 更新结果；支持乐观锁。 |
| subscription_archive | id + reason | 归档结果。 |
| payment_record | id + amount/currency/paid_at + billing_event_id + advance_schedule | 付款记录与账期推进结果。 |
| upcoming_events | days, event_types | 未来事件。 |
| analytics_summary | period, currencies | 按币种分组的预计与实际统计。 |

`usage_review_upsert` 属于第二阶段，不进入 MVP Tool 清单。

### 7.3 对话行为示例

```text
用户：把 Claude Max 加入订阅，100 美元一个月，每月 21 日续费，提前 5 天提醒。
Hermes：准备创建：Claude Max，USD 100/月，下次续费 2026-08-21，自动续费，提前 5 天提醒。确认后调用 subscription_create。

用户：下个月有哪些订阅续费？
Hermes：调用 upcoming_events，按日期和金额分组，不做数据库外推断。

用户：Claude 太贵了，帮我取消。
Hermes：不得自动登录第三方网站取消。应说明只能将本系统状态改为“计划取消/已取消”，并可记录取消截止日。
```

## 8. Web/PWA 产品规格

### 8.1 页面

| 页面 | 阶段 | 核心内容 |
| --- | --- | --- |
| Dashboard | MVP | 本月/下月按币种预计支出、年度支出、最近续费、即将到期。 |
| Subscriptions | MVP | 卡片/表格切换、搜索、分类、状态、币种、价格筛选。 |
| Subscription Detail | MVP | 基础信息、计费计划、关键日期、付款历史、提醒、审计。 |
| Upcoming Events | MVP | 未来 billing/expiry/trial/cancellation 事件列表。 |
| Analytics | MVP 基础版 | 按币种展示预计 vs 实际、分类和供应商统计。 |
| Settings | MVP 基础版 | 可选币种、提醒规则、Session 信息和 API Token 管理。 |
| Calendar | 第二阶段 | 按日历展示各类事件。 |
| Usage Review / Import / Export | 第二阶段 | 使用评价、复盘和数据交换。 |

### 8.2 视觉与交互要求

- 移动端优先，360px 宽度下不出现横向滚动。

- 支持 light/dark mode。

- 使用 Material 3 风格的信息层级，但不要求完全复制 Pandora。

- 金额、续费日期、状态必须在卡片首屏可见。

- 危险操作使用二次确认；归档可恢复。

- 加载、空状态、错误状态、离线状态均需设计。

- Service Worker 只缓存应用壳和静态资源；最近一次成功读取的数据可持久化到 IndexedDB，离线时以明确的“数据可能已过期”状态只读展示。

- 离线状态禁止创建、编辑、归档和记录付款，不实现写入队列、后台同步或冲突合并。

- IndexedDB 不得保存 Session Cookie、API Token 或通知凭据；注销时清除本地业务缓存，并提供关闭持久缓存的设置。

- PWA manifest、service worker、主屏图标和独立窗口模式必须可用。

## 9. 通知与自动化

- `NOTIFICATION_MODE=external` 时 Scheduler 生成可靠 Reminder Outbox；`disabled` 时只维护业务事件，不生成投递项。

- Outbox 消息至少包含：服务名、事件类型、日期、金额、自动续费状态和详情定位信息。

- Hermes 使用 `reminders:consume` Token 执行 claim → 最终渠道投递 → ack/fail；Skill 本身不是后台进程，生产必须配置恰好一个周期消费任务。

- 通知失败写入 `reminder_deliveries.error`，按指数退避重试并最终进入 dead，不能静默丢失。

- Subscription Manager 第一版不保存最终通知渠道凭据，也不实现 ntfy、WxPusher、钉钉等供应商协议。未来 webhook 应采用标准签名 JSON 合约；供应商特有协议应实现独立 Adapter。

## 10. 安全与权限

- Web UI 使用同源 HttpOnly Session；Hermes 和 scheduler 使用各自独立、可撤销、带 scope 的 API Token。反向代理 OIDC 是可选部署增强。

- Token 仅保存哈希；前端不得把长期管理 Token 写入 localStorage。

- CORS 默认关闭或限制到明确域名。

- 所有输入使用 Pydantic 校验；SQL 只通过 ORM/参数化查询。

- 审计日志禁止记录完整 Authorization header、密码、银行卡号。

- 提供 rate limit、request_id 和结构化 JSON 日志。

- 数据库使用最小权限专用账号。

- UI、Hermes、scheduler 以及可选 n8n 必须使用可区分的凭据；凭据至少包含主体、用途、创建时间、最后使用时间、撤销状态和权限范围。

- API Token 只在创建时显示一次，数据库只保存强哈希；必须支持轮换和撤销。

- 若 Web UI 使用 Cookie，必须启用 `HttpOnly`、`Secure`、适当的 `SameSite` 并实施 CSRF 防护；若使用 Bearer Token，仍不得将长期管理 Token 保存到 localStorage。

- 应配置安全响应头，包括 CSP、`X-Content-Type-Options` 和合理的 frame 限制。

- 本地管理员账号通过一次性 bootstrap 命令创建，密码使用 Argon2id 哈希；启动后不得继续从环境变量读取明文管理员密码。

- Session 使用服务端存储或可撤销会话记录，必须设置空闲和绝对过期时间；修改密码或执行“注销全部设备”时撤销已有 Session。

- MVP scope 至少包括 `subscriptions:read`、`subscriptions:write`、`payments:write`、`reminders:scan`、`reminders:consume`、`audit:read`、`tokens:manage`。Hermes 不得拥有 `tokens:manage`；日常 Hermes Token 可按需具有 `reminders:consume`。

## 11. 部署与运维

| 项目 | 要求 |
| --- | --- |
| Docker Compose | backend、frontend、scheduler；PostgreSQL 可使用外部实例。n8n 不属于必需服务。 |
| Environment | 提供 .env.example，不提交真实 secret。 |
| Health Check | /health/live 与 /health/ready，ready 检查数据库。 |
| Backup | 至少包含 PostgreSQL dump；默认每日备份、保留 7 日，文档说明加密、恢复步骤和恢复验证。 |
| Migration | 容器启动前显式执行 alembic upgrade head，不允许自动建表替代 migration。 |
| Logging | JSON 日志，包含 request_id、actor、entity_id。 |
| Reverse Proxy | 不内置具体反向代理、域名或证书配置；仅将 Frontend 默认发布到宿主机回环地址，并记录通用代理要求。 |

Scheduler 与 backend 使用相同代码镜像但不同启动命令。任一环境只能配置一个主动 scheduler 实例，或必须启用数据库领导者锁；水平扩展 backend 不得导致调度任务重复执行。

## 12. 测试与质量门槛

### 12.1 后端必测场景

- 1 月 31 日按月续费到 2 月、3 月时的 anchor 行为。

- 2 月 29 日年度续费。

- 季度/半年周期。

- 同一 Idempotency-Key 重复创建。

- 同一 event_key 不重复发送。

- 停机后 grace window 补发。

- 预计金额与实际付款不相等。

- 归档后默认列表不显示，恢复后重新显示。

- Hermes actor 的审计日志完整。

- 并发更新触发 optimistic lock 冲突。

- 创建/修改 Billing Plan 后生成未来 366 天事件；旧计划未发生事件标记 superseded，历史/reconciled 事件保持不变。

- 当前周期付款在 `advance_schedule=true` 时只推进一次；历史补录不推进；歧义请求返回 422。

- `pending_cancel` 不生成权益失效日后的 billing 事件，撤销取消后按当前计划恢复生成。

- 并发运行两个 scheduler worker 时，同一投递最多发送一次；processing 租约超时后可恢复。

- Session CSRF 校验、API Token scope 隔离、Token 撤销、Session 过期及伪造 Actor Header 均按预期拒绝。

### 12.2 前端关键 E2E

- 创建月付订阅。

- 编辑金额和下次续费日期。

- 添加两条提醒。

- 记录实际付款。

- 查看未来 30 天事件。

- 归档与恢复。

- 移动端视口下完成完整流程。

- 将订阅置为 pending_cancel、撤销取消，并验证状态、日期和未来事件变化。

- 断网后可查看带“可能已过期”标识的缓存数据，所有写入口禁用且请求不会进入离线队列。

- 注销后 IndexedDB 业务缓存被清除，重新打开应用不显示上一会话数据。

- 创建 scoped API Token、确认明文只显示一次并可撤销；低权限 Token 无法访问审计或管理 Token。

### 12.3 质量门槛

- 核心 domain/service 层单元测试覆盖率不得低于 80%，且周期、幂等、审计和权限测试不得以覆盖率豁免。

- CI 必须执行 lint、type check、unit test、migration smoke test。

- API OpenAPI 文档可访问。

- 不得存在明文 secret、硬编码域名或数据库密码。

- README 能在空白环境中完成部署。

- 目标环境下，除通知发送外的普通 API 在 1 万条订阅数据规模下 P95 响应时间应小于 500 ms；未来 30 天事件查询 P95 应小于 1 s。

- 360 px、768 px 和桌面视口必须通过关键流程 E2E；支持当前稳定版及前一个稳定版的 Chrome/Edge，Firefox 做基本兼容验证。

- 所有备份与迁移验收必须包含实际恢复到空数据库并运行 ready check，而不只是生成 dump 文件。

## 13. Codex 实施顺序

| 阶段 | 任务 | 交付物 |
| --- | --- | --- |
| P0 初始化 | Monorepo、backend/frontend、Compose、CI、配置管理 | 可启动空项目。 |
| P1 Domain + DB | 模型、migration、周期计算、审计基础 | 数据库与单元测试。 |
| P2 Core API | 订阅、计划、付款、事件、统计接口 | OpenAPI 与集成测试。 |
| P3 Reminder | 扫描、幂等、通知 adapter、dry-run | 可靠提醒链路。 |
| P4 PWA | Dashboard、列表、详情、表单、PWA | 移动端可用 UI。 |
| P5 Hermes | Tool schema、Skill 文档、示例 Prompt、错误映射 | Hermes 可查询与写入。 |
| P6 Hardening | 鉴权、日志、备份、部署、E2E | 可长期运行版本。 |

## 14. 建议仓库结构

```text
subscription-manager/
├─ backend/
│  ├─ app/
│  │  ├─ api/v1/
│  │  ├─ core/
│  │  ├─ domain/
│  │  ├─ models/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ repositories/
│  │  ├─ notifications/
│  │  └─ main.py
│  ├─ migrations/
│  └─ tests/
├─ frontend/
│  ├─ src/components/
│  ├─ src/features/
│  ├─ src/pages/
│  └─ src/api/
├─ hermes/
│  ├─ SKILL.md
│  ├─ tools.json
│  └─ examples/
├─ deploy/
│  ├─ docker-compose.yml
│  ├─ traefik.labels.example.yml
│  └─ systemd/
├─ docs/
├─ .env.example
└─ README.md
```

## 15. MVP 验收清单

☐ 可通过 Web UI 创建一个 USD 月付订阅，并正确计算下次续费。

☐ 可配置 5 天和 1 天前两条提醒，扫描多次不会重复发送。

☐ 可记录实际付款，并在统计中区分预计与实际。

☐ 可展示未来 30 天账单、到期、试用结束和取消截止事件。

☐ 可从 Hermes 创建、查询、修改、归档订阅，且审计日志 actor=hermes。

☐ 移动端 PWA 可安装并完成核心操作。

☐ 数据库 migration 可在空库执行，也可回滚最近一次 migration。

☐ 提供 Docker Compose、.env.example、备份恢复说明和运行手册。

☐ 核心日期边界测试全部通过。

☐ 不存在明文 secret 和直接数据库写入的 Hermes 集成。

☐ 多币种统计按币种分组，未配置汇率时不输出跨币种总计。

☐ API Actor 由认证层产生，外部伪造 `X-Actor-*` 不会改变审计身份。

☐ 并发执行两次提醒扫描不会产生重复通知；失败重试和超出补发窗口均有可查询记录。

☐ 备份可恢复到空数据库，migration、ready check 和核心查询均成功。

☐ Billing Event 已持久化；修改计划不会覆盖历史/reconciled 事件。

☐ 当前周期付款只推进一次，历史补录不推进，歧义场景不会隐式修改计划。

☐ pending_cancel、Session/API Token、scheduler 并发和离线只读行为均通过自动化测试。

## 16. 交给 Codex 的执行指令

建议将以下文字与本文件一起提供给 Codex：

```text
请严格按照《Hermes 订阅与数字服务管理系统 - 产品需求与技术开发规格说明书》实施。

执行要求：
1. 先输出架构理解、风险清单、里程碑和拟采用的关键库，不要立即大规模写代码。
2. 发现规格冲突时，以“数据正确性、API 边界、可审计、可恢复”为优先原则，并记录决策。
3. 每完成一个阶段，运行测试并提交阶段性说明。
4. 不得让 Hermes 直接访问数据库；所有业务写入必须经过 API/service 层。
5. 不得使用 float 表示金额，不得用固定 30 天替代月度周期。
6. 不要在第一阶段扩展银行卡连接、OCR、原生 Android 或自动取消订阅。
7. 最终交付 README、OpenAPI、migration、测试、Docker Compose、Hermes Skill 和部署说明。
```

## 附录 A：默认产品决策

| 决策项 | 默认值 |
| --- | --- |
| 基准币种 | CNY；Dashboard 的下月续费总额可按 DEC-007 使用 ECB 参考汇率估算。 |
| 时区 | 由部署环境配置，默认 Asia/Shanghai；数据库时间使用 UTC。 |
| 提醒扫描 | Scheduler 默认每 5 分钟维护事件和 Outbox；可通过环境变量调整。 |
| 默认提醒 | 账单前 7 天和 1 天。 |
| 删除策略 | 仅归档，不提供普通硬删除。 |
| 鉴权 | Web 使用同源 HttpOnly Session；Hermes/scheduler 使用独立 scoped API Token；OIDC 可选。 |
| 通知与调度 | 独立 scheduler 维护可靠 Outbox；Hermes 单一周期任务负责最终通知和 ack/fail。 |
| 部署 | Docker Compose 优先，兼容外部 PostgreSQL；反向代理由用户选择。 |

## 附录 B：后续演进方向

- 邮件账单解析：先输出候选变更，人工确认后写入。

- Hermes 月度复盘：结合付款、使用评价、价格变化给出 keep/downgrade/cancel 建议。

- 价格监控：供应商价格页变化只作为提示，不自动覆盖当前价格。

- Android 原生壳：在 PWA 稳定后再评估 TWA/Capacitor 或 Kotlin。

- 数字资产扩展：域名、证书、VPS、License Seat、保修等可基于 service_type 扩展。

## 附录 C：决策记录

| ID | 决策 | 最终决定 | 理由/未采用方案 | 影响范围 | 状态 |
| --- | --- | --- | --- | --- | --- |
| DEC-001 | Billing Event 是否持久化 | 持久化 `billing_events`；计划变更后只替换未锁定的未来事件，历史事件不可覆盖 | 提醒幂等、付款关联和历史审计需要稳定 ID；未采用纯动态计算 | 数据库、提醒、付款、统计 | 已确认，2026-07-16 |
| DEC-002 | 记录付款是否推进账期 | API 显式提供 `advance_schedule`；当前周期正常付款默认 true，历史补录默认 false，歧义时拒绝自动推进 | 兼顾日常便利和历史补录安全；未采用所有付款一律推进或一律人工推进 | Payment、Billing Plan、Hermes | 已确认，2026-07-16 |
| DEC-003 | MVP 鉴权模式 | Web UI 使用同源 HttpOnly Session；Hermes 与 scheduler 使用独立、可撤销、带 scope 的 API Token；OIDC 为可选增强 | 避免浏览器保存长期管理 Token，并隔离机器主体权限；未采用全客户端共享静态 Token | 前后端、反向代理、安全 | 已确认，2026-07-16 |
| DEC-004 | 调度器与首个通知渠道 | 独立 backend scheduler 容器负责扫描和重试，n8n 仅作为可选外部触发；首个渠道实现 ntfy | 保证核心提醒链路不依赖外部自动化平台；未采用 n8n 作为唯一调度器 | 部署、运维、通知 | 已被 DEC-008 替代，2026-07-19 |
| DEC-005 | “计划取消”的领域表达 | 增加 `pending_cancel`；权益失效日前仍可用，但不生成失效日之后的续费事件 | 区分“已申请取消但仍可使用”和“权益已终止”；未采用只靠备注或 auto_renew 推断 | 状态机、UI、Hermes | 已确认，2026-07-16 |
| DEC-006 | PWA 离线范围 | 缓存应用壳和最近一次只读数据；离线禁止写入，不实现自动同步队列 | 降低冲突、安全和同步复杂度；未采用离线写入与后台合并 | PWA、安全、冲突处理 | 已确认，2026-07-16 |
| DEC-007 | Dashboard 跨币种人民币估算 | 使用 ECB 最新工作日欧元参考汇率交叉换算 CNY；显示来源与日期，任一币种缺失汇率或服务不可用时不输出总额 | 在保留原币种明细的同时提供可解释的人民币预算参考，避免静默使用过期或不完整数据 | Backend、Dashboard、运行环境 | 已确认，2026-07-18 |
| DEC-008 | 通知职责边界 | Subscription Manager 维护事件与可靠 Reminder Outbox；Hermes 领取、通知并确认。第一版支持 `external`/`disabled`，移除 ntfy | 保留去重、租约、重试和停机补发的数据正确性，同时避免业务组件绑定具体通知供应商 | Scheduler、API、Hermes | 已确认，2026-07-19 |
| DEC-009 | 生产反向代理边界 | 默认生产 Compose 不包含 Traefik、域名或证书配置，仅将 Frontend 绑定到宿主机回环端口 | 允许用户选择任意反代工具，Backend 与数据库保持内部网络隔离 | 部署、安全、运维 | 已确认，2026-07-19 |

以上决策已由产品方统一确认。后续变更必须记录：新选择、日期、理由、被替代方案，以及需要同步修改的章节/API/migration；不得仅通过代码实现隐式改变。

## 附录 D：实施前 Definition of Ready

进入 P1 Domain + DB 前必须满足：

- `DEC-001`、`DEC-002`、`DEC-005` 已关闭，ERD 和状态机与决策一致。
- 所有 MVP 表具备字段类型、空值、默认值、唯一约束、外键和索引定义。
- 周期、日期、金额、多币种和付款场景已形成示例输入/输出。

进入 P3 Reminder 前必须满足：

- `DEC-008` 已关闭，明确事件维护、Reminder Outbox、外部通知消费者、锁策略、重试参数和凭据来源。
- 通知适配器契约、超时、错误映射与 dry-run 响应已写入 OpenAPI。

进入 P4 PWA 前必须满足：

- `DEC-003`、`DEC-006` 已关闭。
- 页面字段、校验提示、危险操作确认、权限失败和离线状态已有验收示例。

进入发布候选版本前必须满足：

- 所有 MVP 验收项均有自动化测试或明确的人工验收步骤与证据。
- migration 已在空库和已有数据升级路径上验证，备份已实际恢复。
- OpenAPI、README、运行手册、Hermes Skill 与实际实现一致。

## 附录 E：MVP 数据字典基线

下表是 migration 和 Pydantic schema 的最低字段集合。实现可以增加内部字段，但不得删除这些字段或改变其业务语义；所有可变表均继承 4.5 的 `created_at`、`updated_at`、`version` 要求。

### E.1 subscriptions

| 字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| id | UUID | 主键。 |
| name | VARCHAR(200) | 必填，去除首尾空白后非空。 |
| vendor | VARCHAR(200) | 可空；MVP 不单独建立 vendor 表。 |
| category_id | UUID | 可空，外键指向 categories；分类归档后保留引用。 |
| status | ENUM | active/trial/pending_cancel/paused/cancelled/expired；转换见 4.6。 |
| website | TEXT | 可空，仅允许 http/https。 |
| logo_url | TEXT | 可空，仅允许 http/https。 |
| description | TEXT | 可空；渲染时必须防止 XSS。 |
| payment_method_description | VARCHAR(200) | 可空，只保存描述，不保存完整卡号或密码。 |
| start_date | DATE | 可空。 |
| archived_at | TIMESTAMPTZ | 可空；归档时写入，恢复时清空。 |

默认列表排除 `archived_at IS NOT NULL` 的记录；详情 API 可通过 ID 查询已归档记录。归档前的业务状态必须可恢复，可通过 `status_before_archive` 或等价审计信息实现。

### E.2 billing_plans

| 字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| id | UUID | 主键。 |
| subscription_id | UUID | 必填外键。 |
| amount | NUMERIC(18,6) | fixed/one_time 模式下大于或等于 0。 |
| currency | CHAR(3) | 大写 ISO 4217。 |
| interval_unit | ENUM | day/week/month/year。 |
| interval_count | INTEGER | 1..120。 |
| anchor_date | DATE | 固定周期必填，用于保存原始锚点。 |
| next_billing_date | DATE | usage_based/free 可空。 |
| auto_renew | BOOLEAN | 必填。 |
| billing_mode | ENUM | fixed/usage_based/one_time/free。 |
| valid_from | TIMESTAMPTZ | 必填。 |
| valid_to | TIMESTAMPTZ | 当前计划为空，历史计划必填。 |

更新金额、币种、周期或锚点时必须关闭旧计划并创建新计划，不得覆盖历史计划；仅修正明显录入错误时可通过专用管理操作修改，并记录完整 before/after 审计。

### E.3 billing_events

| 字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| id | UUID | 主键。 |
| subscription_id | UUID | 必填外键。 |
| billing_plan_id | UUID | billing 事件必填；其他生命周期事件可空。 |
| event_type | ENUM | billing/expiry/trial_end/cancellation_deadline/contract_end。 |
| event_date | DATE | 必填，按部署时区解释。 |
| amount | NUMERIC(18,6) | billing 事件通常必填，其他事件可空。 |
| currency | CHAR(3) | amount 非空时必填。 |
| status | ENUM | planned/reconciled/superseded/cancelled。 |
| generated_at | TIMESTAMPTZ | 必填。 |

同一 `billing_plan_id + event_type + event_date` 唯一；没有 plan 的生命周期事件以 `subscription_id + event_type + event_date` 唯一。事件不得物理删除，计划变化通过状态表示替代关系。

### E.4 service_dates

| 字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| subscription_id | UUID | 主键兼外键，每个订阅最多一条。 |
| trial_end_date | DATE | 可空。 |
| service_expiry_date | DATE | 可空。 |
| cancellation_deadline | DATE | 可空，包含截止日当天。 |
| contract_end_date | DATE | 可空。 |

日期之间默认不强制固定顺序，但出现 `cancellation_deadline > service_expiry_date`、试用已结束而状态仍为 trial 等情况时，API 必须返回 warning 或校验错误，不得静默接受明显矛盾。

### E.5 payments

| 字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| id | UUID | 主键。 |
| subscription_id | UUID | 必填外键。 |
| billing_event_id | UUID | 可空外键；正常周期付款必须关联，历史补录可空。 |
| amount | NUMERIC(18,6) | MVP 必须大于 0。 |
| currency | CHAR(3) | 大写 ISO 4217。 |
| paid_at | TIMESTAMPTZ | 必填。 |
| tax_amount | NUMERIC(18,6) | 默认 0，不得大于 amount。 |
| source | VARCHAR(50) | manual/hermes/import；MVP 不接银行流水。 |
| external_ref | VARCHAR(200) | 可空；同一 source 下非空值唯一。 |
| notes | TEXT | 可空。 |

Payment 创建后不可直接删除。录入错误使用“作废”能力或等价审计操作修正；退款模型属于第二阶段。

### E.6 reminder_rules 与 reminder_deliveries

| 表/字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| reminder_rules.id | UUID | 主键。 |
| reminder_rules.subscription_id | UUID | 必填外键。 |
| reminder_rules.event_type | ENUM | billing/expiry/trial_end/cancellation_deadline/contract_end。 |
| reminder_rules.offset_days | INTEGER | 0..3650。 |
| reminder_rules.channel | VARCHAR(50) | 必须对应已启用 Adapter。 |
| reminder_rules.enabled | BOOLEAN | 默认 true。 |
| reminder_deliveries.id | UUID | 主键。 |
| reminder_deliveries.rule_id | UUID | 必填外键。 |
| reminder_deliveries.event_key | VARCHAR(500) | 全局唯一；包含订阅、事件类型、事件日、提前量和渠道。 |
| reminder_deliveries.scheduled_for | TIMESTAMPTZ | 按部署时区计算后存 UTC。 |
| reminder_deliveries.status | ENUM | pending/processing/sent/failed/dead/expired。 |
| reminder_deliveries.attempt_count | INTEGER | 默认 0，非负。 |
| reminder_deliveries.sent_at | TIMESTAMPTZ | 可空。 |
| reminder_deliveries.error | TEXT | 可空，必须脱敏并限制长度。 |

同一订阅不得存在 event_type、offset_days、channel 完全相同的启用规则。投递领取必须在事务中把 pending/failed 原子更新为 processing，并带租约或超时恢复机制。

### E.7 categories、tags 与关联表

| 表 | 最低字段与约束 |
| --- | --- |
| categories | id、name、icon、sort_order、archived_at；规范化 name 唯一。 |
| tags | id、name、color、archived_at；规范化 name 唯一。 |
| subscription_tags | subscription_id + tag_id 复合主键；不得重复关联。 |

被使用的分类或标签只能归档，不能通过普通 API 物理删除。归档分类/标签不应从已有订阅详情中消失，但默认选择器不再提供。

### E.8 audit_logs

| 字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| id | UUID | 主键。 |
| occurred_at | TIMESTAMPTZ | 必填、不可修改。 |
| actor_type | ENUM | user/hermes/system/import。 |
| actor_id | VARCHAR(200) | 由认证层产生。 |
| action | VARCHAR(100) | create/update/archive/restore/record_payment 等稳定动作名。 |
| entity_type | VARCHAR(100) | 稳定资源类型。 |
| entity_id | UUID | 被操作资源 ID。 |
| before_json | JSONB | 可空，必须脱敏。 |
| after_json | JSONB | 可空，必须脱敏。 |
| request_id | VARCHAR(100) | 必填，用于关联日志。 |
| idempotency_key_hash | VARCHAR(128) | 可空，只保存哈希或不可逆摘要。 |

审计写入必须与业务写入处于同一数据库事务；审计失败时业务写入不得成功提交。

### E.9 users、sessions 与 api_tokens

| 表/字段 | 类型 | 约束/语义 |
| --- | --- | --- |
| users.id | UUID | 主键；MVP 只有一个本地管理员。 |
| users.username | VARCHAR(100) | 规范化后唯一。 |
| users.password_hash | TEXT | Argon2id 哈希，不保存明文。 |
| users.password_changed_at | TIMESTAMPTZ | 修改密码时更新，用于撤销旧 Session。 |
| sessions.id | UUID | 主键；Cookie 只保存不可预测的会话标识。 |
| sessions.user_id | UUID | 必填外键。 |
| sessions.expires_at / idle_expires_at | TIMESTAMPTZ | 同时执行绝对和空闲过期。 |
| sessions.revoked_at | TIMESTAMPTZ | 可空；注销或安全操作时写入。 |
| api_tokens.id | UUID | 主键。 |
| api_tokens.name / actor_type / actor_id | VARCHAR/ENUM | 标识用途和审计主体。 |
| api_tokens.token_hash | TEXT | 强哈希，全局唯一；明文只显示一次。 |
| api_tokens.scopes | TEXT[] | 按最小权限授予。 |
| api_tokens.last_used_at / expires_at / revoked_at | TIMESTAMPTZ | 支持使用审计、过期和撤销。 |

Session Cookie 必须设置 Secure、HttpOnly 和合适的 SameSite；所有使用 Session 的状态变更请求必须校验 CSRF Token。API Token 只允许通过 Authorization Bearer Header 传递。

## 附录 F：API 列表查询与资源契约

### F.1 Subscription 列表

至少支持以下查询参数：`page`、`page_size`、`q`、`status`、`category_id`、`tag_id`、`currency`、`billing_before`、`expiry_before`、`archived`、`sort`。默认按 `updated_at desc, id desc` 稳定排序。

`q` 至少搜索 name、vendor 和 description；所有过滤条件取交集。非法 sort 字段返回 422，不得直接拼接到 SQL。

### F.2 upcoming events

输入至少包含 `from_date`、`to_date`、`event_types`、`subscription_id`、`include_archived=false`。时间范围最大 366 天；默认从部署时区的当天开始查询未来 30 天。

响应中的每个事件至少包含：持久化 Billing Event ID、subscription_id、服务名、event_type、event_date、amount、currency、auto_renew、status 和 detail_url。

### F.3 analytics summary

响应必须分别返回 `forecast` 和 `actual`，每部分按 currency 分组，并明确统计区间及其时区。第二阶段启用汇率时还必须返回汇率来源、汇率日期和换算前金额。

### F.4 API 兼容性

- `/api/v1` 内不得进行破坏性字段删除或语义变更；新增字段优先设计为向后兼容。
- OpenAPI schema 中金额使用 string + decimal pattern，日期使用 `date`，时间使用 `date-time`。
- 所有响应必须包含或通过 Header 返回 `request_id`；错误响应不得泄露堆栈、SQL 或 secret。
- API 示例必须进入契约测试，避免文档与实现漂移。
