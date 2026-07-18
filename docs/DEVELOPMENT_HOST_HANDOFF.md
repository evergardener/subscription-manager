# 开发主机迁移交接

日期：2026-07-18

项目：Hermes Subscription Manager

源目录：`C:\Projects\Github\subscription-manager`

目标：迁移到另一台 Windows、macOS 或 Linux 主机继续开发，同时保留 Git 历史并在目标主机重建验证环境。

## 1. 当前状态

- P0 代码、依赖锁、静态检查、单元测试、镜像构建和完整 Compose 运行验证已通过。
- P0 基线提交：`74743c3 chore: establish validated P0 baseline`。
- P1 尚未开始，没有业务 migration、领域模型、认证或第二阶段 API。
- 新开发主机复验已经完成；提交 `cad4b9a` 的 GitHub Actions 三个 job 全部通过，P0 已正式关闭。
- 每个后续已验证变更都应自动创建独立 Git 提交，不自动推送。

完整证据见 [P0_VERIFICATION.md](./P0_VERIFICATION.md)。

## 2. 推荐迁移方式

优先使用带访问控制的 Git 远程仓库：

1. 在源主机确认工作树干净。
2. 将当前分支推送到私有或受控远程仓库。
3. 在目标主机使用 `git clone` 获取项目。
4. 比对源主机和目标主机的 `git rev-parse HEAD`。

如果暂时没有远程仓库，可以使用 Git bundle 保留全部历史：

```powershell
git status --short --branch
git bundle create subscription-manager.bundle --all
git bundle verify subscription-manager.bundle
```

将 bundle 复制到目标主机后执行：

```bash
git clone subscription-manager.bundle subscription-manager
cd subscription-manager
git status --short --branch
git log --oneline -5
```

不要只复制源码压缩包作为唯一迁移方式，因为这会丢失 Git 历史。如果直接复制整个项目目录，必须包含 `.git`，并在复制前确认工作树干净。

## 3. 不迁移的内容

以下内容必须在目标主机重新生成：

- `.cache/`
- `.env`
- `backend/.venv/`
- `backend/.pytest_cache/`
- `backend/.mypy_cache/`
- `backend/.ruff_cache/`
- `frontend/node_modules/`
- `frontend/dist/`
- Docker images、containers、networks 和 volumes

项目当前只有 P0 空基线，不包含需要迁移的业务数据库数据。不要复制源主机的临时 PostgreSQL volume。

## 4. 目标主机环境

- Git。
- Python 3.12。
- `uv 0.8.3`，与 CI 固定版本一致。
- Node.js 22 和 npm。
- Docker Desktop 或 Docker Engine，支持 Linux containers 和 `docker compose`。
- 至少 4 CPU、8 GiB 可用内存和 10 GiB 可用磁盘空间。

Docker 就绪检查：

```bash
docker version
docker compose version
docker info
```

## 5. 配置恢复

在项目根目录执行：

```bash
cp .env.example .env
```

编辑 `.env`，至少替换 `POSTGRES_PASSWORD=change-me`，并让 `DATABASE_URL` 使用相同密码。不要提交 `.env`。

Windows PowerShell 可使用：

```powershell
Copy-Item .env.example .env
```

## 6. Backend 重建与验证

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

预期 Backend 测试为 5 tests passed，静态 Alembic SQL 仅创建 `alembic_version`。

## 7. Frontend 重建与验证

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

预期 Frontend 测试为 2 tests passed，依赖审计为 0 vulnerabilities。

## 8. Docker 完整栈验证

```bash
docker compose config --quiet
docker compose build --pull
docker compose up -d --wait --wait-timeout 180
docker compose ps -a
curl -fsS http://127.0.0.1:8000/api/v1/health/live
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
curl -fsS http://127.0.0.1:8080/api/v1/health/ready
```

Windows PowerShell 的端点检查可使用：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health/live
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health/ready
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/api/v1/health/ready
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

## 9. Git 与 CI 接手检查

```bash
git status --short --branch
git diff --check
git log --oneline -5
git rev-parse HEAD
```

确认 Compose 和 CI 都使用：

```text
postgres:16.14-alpine3.22
```

推送到 GitHub 后，确认 `backend`、`frontend`、`compose` 三个 job 全绿，并把 CI 链接或 commit SHA 补充到 [P0_VERIFICATION.md](./P0_VERIFICATION.md)。

## 10. 清理与启动 P1

完成验证后，如需清空目标主机的临时验证数据：

```bash
docker compose down -v
```

`-v` 会删除本项目的 PostgreSQL volume，只应在确认没有需要保留的数据时使用。

P1 启动前必须满足：

1. 目标主机全部 Backend、Frontend 和 Docker 验证通过。
2. GitHub Actions 三个 job 全绿。
3. 迁移后的 Git HEAD 与预期提交一致，工作树干净。
4. [实施计划](./Hermes_Subscription_Manager_Implementation_Plan.md) 中 P0 状态更新为完整关闭。
