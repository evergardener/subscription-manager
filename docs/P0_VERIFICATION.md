# P0 验证记录

日期：2026-07-18
状态：**P0 已完成：新开发主机复验和 GitHub Actions 权威验证均已通过；P1 尚未开始**

## 1. 交付范围

- Monorepo、Backend、Frontend、独立 Scheduler、Docker Compose 和 GitHub Actions CI 骨架。
- 环境配置校验、JSON 日志、`request_id`、OpenAPI。
- `/api/v1/health/live` 和 `/api/v1/health/ready`。
- Alembic 空基线；应用代码不存在 `create_all()`。
- Python `uv.lock`、带 hash 的生产 `requirements.lock` 和前端 `package-lock.json`。
- README 中的启动、开发和验证命令。
- PostgreSQL 镜像固定为 `postgres:16.14-alpine3.22`，避免浮动标签造成不可复现构建。

P0 未创建任何业务表，P1 功能未提前实现。

## 2. 本地质量检查

### Backend

| 检查 | 结果 |
| --- | --- |
| `uv sync --frozen` | 通过 |
| `uv run ruff check .` | 通过 |
| `uv run ruff format --check .` | 通过，19 个文件已格式化 |
| `uv run mypy app tests` | 通过，17 个源文件无问题 |
| `uv run pytest` | 通过，5 tests |
| `uv run alembic upgrade head --sql` | 通过；仅生成 `alembic_version` 表 |
| `uv run python ../scripts/validate_p0.py` | 通过 |

### Frontend

| 检查 | 结果 |
| --- | --- |
| `npm ci` | 通过 |
| `npm audit --audit-level=high` | 通过，0 vulnerabilities |
| `npm run lint` | 通过 |
| `npm run typecheck` | 通过 |
| `npm test` | 通过，2 tests |
| `npm run build` | 通过，Vite 生产构建成功 |

说明：一次受限沙箱运行中 Vitest 因 `esbuild spawn EPERM` 未能启动；在不修改系统配置的沙箱外复跑后通过。这是执行环境限制，不是测试失败。

## 3. 本地 Docker/PostgreSQL 完整栈验证

验证主机：Windows 11 + WSL2

运行时：Docker Desktop Engine 29.6.1、Docker Compose 5.3.0

隔离项目名：`hermes-subscription-manager-local`

| 验证项 | 结果 |
| --- | --- |
| `./scripts/verify-p0.ps1 -SkipInstall` | 完整通过，包括 Compose 官方解析 |
| Backend/Frontend/Scheduler 镜像构建 | 通过 |
| Docker 构建上下文 | Backend 约 2.34 kB、Frontend 约 766 B；已排除虚拟环境、`node_modules` 和构建产物 |
| PostgreSQL 16 初始化和健康检查 | 通过 |
| `migrate` one-shot 服务 | 退出码 0 |
| 完整栈 `docker compose up -d --wait` | 退出码 0 |
| Backend `/health/live` | HTTP 200 |
| Backend `/health/ready` | HTTP 200，真实连接 PostgreSQL |
| Frontend 同源代理 `/api/v1/health/ready` | HTTP 200 |
| `X-Request-ID` 透传 | 通过，返回 `local-p0-request` |
| `upgrade head -> downgrade base -> upgrade head` | 全部退出码 0 |
| P0 数据库表检查 | 仅 `public.alembic_version` |
| Backend/Scheduler 错误日志扫描 | 未发现 `Traceback`、`ERROR` 或 `CRITICAL` |

验证时 Backend 使用端口 `8000`，Frontend 使用端口 `8080`。数据库密码通过当前 PowerShell 进程的临时环境变量提供，没有生成或提交 `.env`。这些结果作为源主机验证证据保留；迁移时不复制容器或数据库卷，目标主机必须从 lockfile 和 Compose 配置重新构建并复验。

## 4. 局域网 Docker/PostgreSQL 交叉验证

验证主机：`192.168.7.101`

操作系统：CentOS 7，Linux 3.10

运行时：Docker Engine 26.1.4、Docker Compose 2.27.1
远程测试目录：`/root/hermes-subscription-manager-p0-20260716-2219`

| 验证项 | 结果 |
| --- | --- |
| `docker compose config --quiet` | 通过 |
| Backend/Frontend/Scheduler 镜像构建 | 通过 |
| PostgreSQL 16 初始化和健康检查 | 通过 |
| `migrate` one-shot 服务 | 退出码 0 |
| 完整栈 `docker compose up -d --wait` | 退出码 0 |
| Backend `/health/live` | HTTP 200 |
| Backend `/health/ready` | HTTP 200，真实连接 PostgreSQL |
| Frontend 首页 | HTTP 200，包含应用标题和 root 节点 |
| Frontend 同源代理 `/api/v1/health/ready` | HTTP 200 |
| `/openapi.json` | 可访问，包含 live/ready 路径 |
| `X-Request-ID` 透传 | 通过，响应和 JSON 日志均保留输入值 |
| `upgrade head -> downgrade base -> upgrade head` | 全部退出码 0 |
| P0 数据库表检查 | 仅 `public.alembic_version` |
| Scheduler 独立进程 | 启动成功并记录 `scheduler_heartbeat` |
| Backend/Scheduler 错误日志扫描 | 未发现 `Traceback`、`ERROR` 或 `CRITICAL` |

远程完整栈在交接时保持运行，便于迁移后复查。测试数据库密码为远程临时随机值，只保存在权限 600 的远程 `.env` 中，未写入仓库。

## 5. 验证中发现并修复的问题

最初使用浮动标签 `postgres:16-alpine`。2026-07-16 拉取到的镜像基于 Alpine 3.23，在 CentOS 7 自带的旧版 `libseccomp 2.3.1` 上初始化 PostgreSQL 时出现 `Operation not permitted`。

对比验证结果：

- 同一镜像使用 `seccomp=unconfined` 可运行，证明问题来自宿主机 seccomp 兼容性；该弱化安全性的方式未进入项目配置。
- `postgres:16.14-alpine3.22` 在默认 seccomp 下正常运行。
- 项目 Compose 与 CI 均已固定到 `postgres:16.14-alpine3.22`，兼顾当前补丁版本、默认隔离和构建可复现性。

## 6. 新开发主机与 GitHub Actions 验证

2026-07-18 在新开发主机从 `uv.lock` 和 `package-lock.json` 全新重建依赖，并使用 Docker Desktop Linux Engine 29.6.1、Docker Compose 5.3.0 复验。Backend 5 tests、Frontend 2 tests、全部 lint/typecheck/build、Compose 镜像构建、完整栈、真实 PostgreSQL ready check、迁移往返、表检查、request ID 和 scheduler heartbeat 均通过；结构化日志未发现 `Traceback`、`ERROR` 或 `CRITICAL`。

项目随后首次推送到 `evergardener/subscription-manager`。提交 `cad4b9a05461448185cd8d57d61d22511bbc5830` 的 [GitHub Actions CI 运行](https://github.com/evergardener/subscription-manager/actions/runs/29641921957) 于 2026-07-18 完成，结论为 `success`：

| Job | 结果 |
| --- | --- |
| `backend` | 通过，包括 PostgreSQL service、依赖同步、Ruff、mypy、5 tests 和 migration 往返 |
| `frontend` | 通过，包括依赖审计、lint、typecheck、2 tests 和生产构建 |
| `compose` | 通过，Compose 官方配置解析成功 |

至此 P0 的本地、新主机、跨主机 Docker 和 GitHub runner 证据均已闭环，P0 正式关闭。

## 7. 开发主机迁移状态

- P0 基线已提交，基线提交为 `74743c3`。
- 新开发主机迁移和从 lockfile 重建已完成，Git 历史已保留。
- 本地 `main` 已关联并推送到 `https://github.com/evergardener/subscription-manager.git`。
- 源主机的 `.venv`、`node_modules`、`.cache`、构建产物、容器和 Docker volume 不属于迁移内容。
- 新开发主机与 GitHub Actions 复验已完成，可以开始 P1。
