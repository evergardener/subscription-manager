# P1–P3 验证记录

日期：2026-07-18

状态：**P1、P2、P3 已实现并在新开发主机通过本地 PostgreSQL、Docker Compose 和自动化测试；等待 GitHub Actions 对最终提交给出权威结果**

## 交付范围

- P1：完整 MVP schema、Alembic migration、Decimal 金额、日历周期、持久化 Billing Event、状态机、审计、乐观锁、幂等记录、管理员 bootstrap、Session/CSRF 与 scoped API Token。
- P2：订阅、计划、状态转换、归档恢复、付款、分类、标签、提醒规则、Upcoming Events、按币种统计和审计 API；统一错误结构和 OpenAPI 契约。
- P3：独立 scheduler、事件滚动生成、提醒 delivery 幂等生成、`FOR UPDATE SKIP LOCKED` 原子领取、processing 租约、指数退避、dead/expired、人工重试、dry-run 和 ntfy Adapter。
- P4 及之后内容未实现；前端仍保持 P0 健康状态页。

## 自动化验证

| 检查 | 结果 |
| --- | --- |
| Ruff lint/format | 通过，42 个 Python 文件 |
| mypy strict | 通过，39 个源文件 |
| pytest | 通过，23 tests |
| Domain/services 覆盖率 | 80.63%，高于 80% 门槛 |
| Alembic metadata drift | `No new upgrade operations detected` |
| Migration 往返 | 空库 upgrade、downgrade base、再次 upgrade 全部通过 |
| Frontend lint/typecheck/test/build | 通过，2 tests |

测试覆盖月末、闰年、季度/半年、状态转换、Decimal、Session CSRF、Token scope 与撤销、Actor Header 防伪、API 幂等、计划替换、提醒 event_key、重复扫描、双 worker 原子领取、发送成功、失败重试和 dead 状态。

## Docker Compose 垂直切片

- 原 P0 空数据库就地升级到 revision `ae17e2c0f9f8`，共 16 张 public 表。
- Backend、PostgreSQL、Scheduler、Frontend 均健康，migration one-shot 退出码 0。
- 创建 USD 月付订阅后持久化生成 14 个 billing/lifecycle events。
- 同一 Idempotency-Key 重复创建订阅和重复记录付款均返回原资源，未重复写入或推进。
- 实际付款 USD 95 与预计 USD 100 分离，账期按原 anchor 推进。
- 外部伪造 `X-Actor-*` 未改变审计 actor，记录仍为认证 Session 用户。
- 提醒窗口按 `scheduled_for` 判断；首次 dry-run 生成 2 条 delivery，重复扫描生成 0 条。
- Backend/Scheduler 日志未发现 `Traceback`、`ERROR` 或 `CRITICAL`。
- 验证结束后已清空临时管理员、订阅、付款、投递和审计数据，保留空白 P3 schema 与运行中的本地实例。

## 尚待补齐

最终提交推送后，确认 GitHub Actions `backend`、`frontend`、`compose` 三个 job 全绿，并将运行链接与 commit SHA 补充到本文件。完成后停止开发，下一阶段从 P4 开始。
