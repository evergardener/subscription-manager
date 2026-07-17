# Mac 开发交接

> 归档说明：2026-07-17 决定继续使用当前本机 Docker 环境开发。本文件保留为未来可选迁移参考，不再代表当前执行计划。

日期：2026-07-16

项目：Hermes Subscription Manager

Windows 源目录：`C:\Projects\Github\subscription-manager`

## 当前结论

- P0 代码、依赖锁、静态检查、单元测试、镜像构建和完整 Compose 运行验证已通过。
- P1 尚未开始，没有业务 migration、领域模型、认证或第二阶段 API。
- 唯一未取得的 P0 权威证据是 GitHub Actions 的实际绿色运行记录。
- 当前工作树尚未提交；迁移时必须保留全部文件和 Git 元数据，或先创建一个明确的 P0 交接提交。

详细证据见 [P0_VERIFICATION.md](./P0_VERIFICATION.md)。

## Mac 环境建议

- macOS 14 或更高版本。
- Git。
- Python 3.12。
- `uv 0.8.3`（与 CI 固定版本一致）。
- Node.js 22 和 npm。
- Docker Desktop 或兼容的 Docker Engine，支持 `docker compose`。

不要复制以下生成目录：

- `.cache/`
- `backend/.venv/`
- `backend/.pytest_cache/`
- `backend/.mypy_cache/`
- `backend/.ruff_cache/`
- `frontend/node_modules/`
- `frontend/dist/`

这些内容应在 Mac 上根据 lockfile 重新生成。

## 迁移后恢复

在项目根目录执行：

```bash
cp .env.example .env
```

编辑 `.env`，至少替换 `POSTGRES_PASSWORD=change-me`，并让 `DATABASE_URL` 使用相同密码。不要提交 `.env`。

安装和验证 Backend：

```bash
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
uv run pytest
uv run alembic upgrade head --sql
uv run python ../scripts/validate_p0.py
cd ..
```

安装和验证 Frontend：

```bash
cd frontend
npm ci
npm audit --audit-level=high
npm run lint
npm run typecheck
npm test
npm run build
cd ..
```

验证完整栈：

```bash
docker compose config --quiet
docker compose build --pull
docker compose up -d --wait --wait-timeout 180
docker compose ps -a
curl -fsS http://127.0.0.1:8000/api/v1/health/live
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
curl -fsS http://127.0.0.1:8080/api/v1/health/ready
```

验证 migration 往返：

```bash
docker compose run --rm migrate alembic downgrade base
docker compose run --rm migrate alembic upgrade head
docker compose exec -T db psql -U hermes -d hermes -Atc \
  "select schemaname||'.'||tablename from pg_tables where schemaname='public' order by tablename;"
```

预期仅输出：

```text
public.alembic_version
```

清理本地测试栈：

```bash
docker compose down -v
```

`-v` 会删除本项目 Compose 测试数据库卷，只应在确认其中没有需要保留的数据时使用。

## Git 与 CI 接手检查

```bash
git status --short --branch
git diff --check
git diff -- compose.yml .github/workflows/ci.yml
```

确认 Compose 和 CI 都使用：

```text
postgres:16.14-alpine3.22
```

创建或推送 P0 提交后，等待 GitHub Actions 的 `backend`、`frontend`、`compose` 三个 job 全绿，再更新 [P0_VERIFICATION.md](./P0_VERIFICATION.md) 并进入 P1。

## 远程验证环境

- 主机：`192.168.7.101`
- 测试目录：`/root/hermes-subscription-manager-p0-20260716-2219`
- 已安装：Docker Engine 26.1.4、Docker Compose 2.27.1
- 交接时完整栈保持运行，端口为 Backend `8000`、Frontend `8080`。

远程凭据和随机数据库密码不进入本文档或仓库。后续如果不再需要该环境，应先保存必要日志，再在该远程测试目录执行 `docker compose down -v`。

## P1 启动条件

P1 的第一批工作是 MVP migration、周期计算、Billing Event、状态机、审计事务、乐观锁、幂等键和认证基础。开始前必须确认：

1. Mac 全新环境完成上述全部复验。
2. GitHub Actions 三个 job 全绿。
3. P0 交接提交可追溯，工作树无意外文件。
4. [实施计划](./Hermes_Subscription_Manager_Implementation_Plan.md) 中 P0 状态更新为完整关闭。
