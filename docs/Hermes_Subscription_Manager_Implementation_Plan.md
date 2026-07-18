# Hermes Subscription Manager 实施计划

版本：v1.0
日期：2026-07-16
依据：[Hermes_Subscription_Manager_Development_Spec.md](./Hermes_Subscription_Manager_Development_Spec.md) v1.1

## 1. 当前状态

- 产品与技术规格 v1.1 已完成，DEC-001 至 DEC-006 均已确认。
- 项目已创建于 `C:\Projects\Github\subscription-manager`。
- P0 代码、依赖锁定、本地质量检查、本地 Docker 完整栈和局域网 Docker 交叉验证已通过；完整证据见 [P0_VERIFICATION.md](./P0_VERIFICATION.md)。
- PostgreSQL 已固定为 `postgres:16.14-alpine3.22`，解决浮动标签在旧版 seccomp 宿主机上的兼容性和可复现性问题。
- 新开发主机已从 lockfile 重建并完成本地质量门、Docker Linux Engine 完整栈和迁移往返复验。
- 提交 `cad4b9a` 的 GitHub Actions `backend`、`frontend`、`compose` 三个 job 已全部通过；P0 正式关闭，下一步进入 P1。
- 每个已验证变更后自动创建 Git 提交；仓库约定见根目录 [AGENTS.md](../AGENTS.md)。

## 2. 架构理解

系统由五个运行单元组成：

1. React PWA：人工查询和维护订阅，使用同源 HttpOnly Session。
2. FastAPI Backend：唯一业务边界，负责鉴权、校验、领域规则、审计和 OpenAPI。
3. PostgreSQL：保存订阅、计费计划、持久化 Billing Event、付款、提醒、投递、身份和审计数据。
4. Scheduler：使用与 Backend 相同的 Python 代码镜像，以独立命令运行；负责事件滚动生成、提醒扫描、投递领取和重试。
5. Hermes Skill/Tools：使用独立 scoped API Token 调用 Backend，不直接访问数据库。

n8n 不是核心运行依赖，只能作为带 `reminders:scan` scope 的外部触发器。MVP 通知渠道为 ntfy。

## 3. 代码与模块边界

### Backend

```text
backend/app/
├─ api/                 # HTTP 适配层，不放业务规则
├─ auth/                # Session、API Token、scope、CSRF
├─ domain/              # 实体、值对象、状态机、周期计算
├─ services/            # 用例和事务边界
├─ repositories/        # SQLAlchemy 数据访问
├─ models/              # ORM 映射
├─ schemas/             # Pydantic 请求/响应
├─ notifications/       # Adapter 接口与 ntfy 实现
├─ scheduler/           # 事件生成、扫描、领取、重试
├─ audit/               # before/after、actor、request_id
└─ core/                # 配置、日志、数据库、异常
```

依赖方向必须保持为：`api/scheduler/hermes adapter -> services -> domain + repository interfaces`。ORM model 和 FastAPI request object 不得进入纯 domain 计算函数。

### Frontend

```text
frontend/src/
├─ app/                 # Router、Providers、主题、Session
├─ api/                 # 生成或类型化的 API client
├─ features/            # subscriptions/payments/events/settings/auth
├─ components/          # 通用 UI
├─ pages/               # 页面组合
├─ offline/             # 只读缓存与离线状态
└─ test/                # 测试工具
```

## 4. 关键库基线

最终版本在 P0 中锁定，并通过兼容性 smoke test 后写入 lockfile。

| 领域 | 库/工具 | 用途 |
| --- | --- | --- |
| Backend API | FastAPI、Pydantic v2、pydantic-settings | HTTP、schema、配置。 |
| 数据库 | SQLAlchemy 2.x、Alembic、psycopg | ORM、migration、PostgreSQL driver。 |
| 调度 | APScheduler | 独立 scheduler 进程的周期触发。 |
| HTTP | httpx | ntfy 调用和测试客户端。 |
| 密码 | argon2-cffi | 管理员密码和敏感 Token 哈希。 |
| 日期 | Python datetime + dateutil | 日历周期计算；核心算法保持纯函数。 |
| Backend 质量 | pytest、pytest-asyncio、Ruff、mypy | 测试、lint、类型检查。 |
| Frontend | React、TypeScript、Vite | PWA 基础。 |
| UI | Tailwind CSS、shadcn/ui | 响应式组件。 |
| 状态/表单 | TanStack Query、React Hook Form、Zod | 服务端状态、表单和前端校验。 |
| PWA | vite-plugin-pwa、IndexedDB 封装 | 应用壳和最近只读数据缓存。 |
| Frontend 测试 | Vitest、Testing Library、Playwright | 单元、组件和 E2E。 |

## 5. 里程碑

### P0：初始化与架构验证

交付：

- Monorepo、Backend、Frontend、Docker Compose 和 CI 骨架。
- `.env.example`、配置校验、JSON 日志和 request_id。
- Backend/Frontend/scheduler 三个启动命令。
- PostgreSQL 连接及 `/health/live`、`/health/ready`。
- Ruff、mypy、pytest、Frontend lint/typecheck/test 的最小通过样例。
- 架构决策与开发命令写入 README。

退出门槛：全新环境可按 README 启动；CI 全绿；没有业务表由 ORM 自动建表。

### P1：Domain、DB 与 Auth

交付：

- 规格附录 E 的 MVP migration。
- 周期计算、Billing Event 生成、状态机和金额值对象。
- 审计事务、乐观锁和 Idempotency-Key 存储。
- 本地管理员 bootstrap、Session、CSRF、scoped API Token。

退出门槛：空库升级/回滚通过；月末/闰年/状态转换/权限测试通过。

### P2：Core API

交付：订阅、计划、状态转换、付款、分类、标签、事件、统计和审计接口，以及 OpenAPI 契约测试。

退出门槛：当前付款只推进一次，历史补录不推进；多币种统计不隐式相加。

### P3：Reminder

交付：独立 scheduler、数据库领取锁、processing 租约、失败重试、补发、dry-run 和 ntfy Adapter。

退出门槛：并发 worker 不重复发送；停机恢复、dead/expired 状态和人工重试可审计。

### P4：PWA

交付：登录、Dashboard、Subscriptions、Detail、Upcoming Events、基础 Analytics、Settings 和 Token 管理。

退出门槛：360 px 无横向滚动；离线只读且明确提示；注销清除 IndexedDB 数据。

### P5：Hermes

交付：`SKILL.md`、Tool schema、认证配置、错误映射、确认流程和端到端示例。

退出门槛：查询和关键写操作通过真实 API；actor=hermes；无法伪造 Actor Header。

### P6：Hardening

交付：备份恢复、Traefik/systemd 文档、安全头、速率限制、性能检查、完整 E2E 和运行手册。

退出门槛：规格第 15 章所有验收项完成并有证据。

## 6. 首个垂直切片

P0/P1 不应一次实现全部领域。第一个可验证切片为：

1. bootstrap 管理员并登录。
2. 创建一个 USD 月付订阅和当前 Billing Plan。
3. 持久化生成下一次 billing event。
4. 查询订阅详情和未来事件。
5. 记录关联付款并以 `advance_schedule=true` 推进一次账期。
6. 检查 Billing Event、Billing Plan、Payment 和 Audit Log 的事务结果。

这个切片会尽早验证最危险的模型关系，完成后再扩展分类、标签、提醒和 UI。

## 7. 风险与控制

| 风险 | 控制措施 | 首次验证阶段 |
| --- | --- | --- |
| 月末/闰年日期漂移 | 纯函数 + 参数化/性质测试，始终保留原 anchor | P1 |
| 付款重复推进 | Idempotency-Key、event 关联、version、单事务 | P1/P2 |
| 计划变更覆盖历史 | append-only plan、event superseded 状态 | P1 |
| 多 scheduler 重复通知 | 数据库原子领取、租约、唯一 event_key | P3 |
| Actor Header 伪造 | 服务端从 Session/Token 生成 actor | P1 |
| 浏览器泄露长期 Token | UI 使用 Session，Token 明文只显示一次 | P1/P4 |
| 离线数据泄露或冲突 | 只读 IndexedDB、注销清除、不缓存凭据 | P4 |
| 规格与 OpenAPI 漂移 | API 示例和 schema 进入契约测试 | P2 起持续 |

## 8. 实施纪律

- 每个阶段使用小批次 migration 和测试，不跨阶段预埋第二阶段功能。
- 任何偏离 v1.1 规格的实现必须先更新 Markdown 决策记录。
- 每个阶段结束时更新本计划的状态、测试证据和剩余风险。
- 不提交 secret、真实 Token、生产域名或个人订阅数据。
