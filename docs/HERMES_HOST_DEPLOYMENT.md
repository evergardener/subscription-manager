# Hermes 主机生产部署手册

## 1. 适用范围

本手册用于将部署文件和 Hermes 集成包复制或克隆到 Hermes 所在的 Linux 主机，然后由 Hermes/运维执行者拉取预构建镜像并部署。生产 Compose 只包含 Subscription Manager 自身组件：迁移、Backend、Scheduler、Frontend，以及可选的内置 PostgreSQL；Hermes 主机不构建应用源码。

推荐主机基线：

- Linux x86_64 或 arm64，时间同步正常；
- Docker Engine 24+、Docker Compose v2；
- `curl`、`jq`、`openssl`；
- 至少 2 GB 可用内存、10 GB 可用磁盘；
- 已有 HTTPS 域名或受保护的内网 HTTPS 入口；
- Backend 可出站访问 `https://www.ecb.europa.eu`，用于可选的人民币汇率估算。

## 2. 拷贝与部署前检查

不要从旧主机复制 `.env`、`backend/.venv`、`frontend/node_modules`、Docker volume 或未加密备份。优先使用 Git：

```bash
sudo install -d -o "$USER" -g "$USER" /opt/subscription-manager
git clone https://github.com/evergardener/subscription-manager.git /opt/subscription-manager
cd /opt/subscription-manager
git status --short
git rev-parse HEAD
docker version
docker compose version
```

如果使用文件拷贝，确认仓库根目录至少包含 `deploy/`、`backend/`、`frontend/`、`hermes/`、`scripts/` 和本交接文档。不要自动覆盖目标主机已有的 `.env` 或数据目录。

检查端口和已有 Compose 项目：

```bash
ss -lntp | grep -E ':(8080|80|443)\b' || true
docker compose ls
```

发现已有 `subscription-manager` 项目时，按第 10 节升级，不得当作全新安装。

## 3. 选择数据库模式

### 内置 PostgreSQL（推荐用于首次单机部署）

```bash
cd /opt/subscription-manager
cp deploy/.env.production.example .env
chmod 0600 .env
```

用受保护编辑器设置 `.env`。至少替换：

```dotenv
POSTGRES_DB=subscription_manager
POSTGRES_USER=subscription_manager
POSTGRES_PASSWORD=<openssl rand -hex 32 的结果>
SERVICE_BIND_ADDRESS=127.0.0.1
SERVICE_PORT=8080
NOTIFICATION_MODE=external
```

不要把尖括号占位文本原样保留。新安装可生成 URL-safe 密码：

```bash
openssl rand -hex 32
```

### 外部 PostgreSQL 16+

```bash
cp deploy/.env.external-db.example .env
chmod 0600 .env
```

设置完整 `DATABASE_URL`，对用户名/密码中的保留字符进行 URL 编码，并按供应商要求启用 TLS。外部数据库应预先创建最小权限角色和空数据库。相关供应商备份、HA 和 TLS 责任不由本 Compose 接管。

### 镜像版本

生产镜像由 GitHub Actions 在完整 CI 通过后发布：

- `ghcr.io/evergardener/subscription-manager-backend`
- `ghcr.io/evergardener/subscription-manager-frontend`

默认 `IMAGE_TAG=latest`，它只跟随最新成功的 `main` 构建。需要可复现部署或回滚时，使用同一提交对应的 `sha-<40 位 Git commit>` 标签。`main` 也指向最新成功的主分支构建；推送 `v*` Git 标签会额外发布 SemVer 标签。

首次工作流发布后，仓库所有者必须在 GitHub 上分别进入两个 Package 的 **Package settings → Change visibility → Public** 完成一次性公开设置。公开后不可改回私有。公开镜像可匿名拉取，Hermes 主机不需要 GHCR Token；若尚未公开，下面的 `pull` 会返回权限错误。

## 4. 配置和启动

内置数据库模式：

```bash
cd /opt/subscription-manager
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager config --quiet
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager pull
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager up -d --wait
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager ps --all
```

外部数据库模式将文件名替换为 `deploy/compose.external-db.yml`。验收条件：

- `migrate` 状态为 `Exited (0)`；
- `backend`、`frontend` 健康；
- `scheduler` 运行；
- `db`（内置模式）健康；
- 只有 Frontend 出现 `127.0.0.1:<SERVICE_PORT>->80/tcp`，Backend/Scheduler/数据库没有宿主机端口。

验证同源 API：

```bash
curl --fail-with-body http://127.0.0.1:8080/api/v1/health/live
curl --fail-with-body http://127.0.0.1:8080/api/v1/health/ready
```

## 5. 配置 HTTPS 反向代理

反向代理目标统一为 `http://127.0.0.1:8080`。浏览器和 Hermes 均使用同一个公开 HTTPS origin；不要让 Hermes 直连 Backend 容器。

Caddy 最小示例：

```caddyfile
subscriptions.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Nginx 核心示例：

```nginx
server {
    listen 443 ssl http2;
    server_name subscriptions.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

证书、DNS 和代理访问控制由用户已有设施管理。若在代理前增加 SSO，必须允许带 `Authorization: Bearer` 的 `/api/v1/*` 机器请求直接到达 Subscription Manager，不能重定向到交互登录页。

```bash
curl --fail-with-body https://subscriptions.example.com/api/v1/health/ready
```

## 6. 初始化管理员

仅空库第一次执行 bootstrap。密码至少 12 个字符，不要写入 shell 历史：

```bash
read -rsp 'Initial admin password: ' ADMIN_PASSWORD; echo
jq -n --arg username admin --arg password "$ADMIN_PASSWORD" \
  '{username:$username,password:$password}' \
  | curl --fail-with-body -H 'Content-Type: application/json' \
      --data-binary @- http://127.0.0.1:8080/api/v1/auth/bootstrap
unset ADMIN_PASSWORD
```

已有管理员时返回 HTTP 409 是预期行为。忘记密码只能在主机本地重置：

```bash
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager \
  exec backend python -m app.cli reset-admin-password --username admin
```

## 7. 创建 Hermes Token

推荐通过 HTTPS Web UI 登录，在“设置 → API Token”创建：

- 名称：`Hermes Production`；
- Actor ID：使用该 Hermes 实例的稳定名称，例如 `hermes-main`；
- Scopes：`subscriptions:read`、`subscriptions:write`、`payments:write`、`analytics:read`、`audit:read`、`reminders:consume`。

Token 明文只显示一次。立即写入 Hermes 的 secret store/service credential，不要写入仓库 `.env`、普通配置文件、聊天记录或日志。不要授予 `tokens:manage`、`reminders:scan`、`reminders:read`、`reminders:retry`。

然后按 [hermes/INSTALL.md](../hermes/INSTALL.md) 安装 Skill 和周期提醒任务。

## 8. 部署验收

完成以下检查：

```bash
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager ps --all
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager logs --since 10m backend scheduler
curl --fail-with-body https://subscriptions.example.com/api/v1/health/ready
```

使用 Hermes 依次完成：

1. 查询未来 30 天事件；
2. 创建一条明确标记为验收用途的订阅（需确认）；
3. 修改金额或关键日期（需确认）；
4. 设置一条 external reminder rule（需确认）；
5. 查询审计，确认 actor 为 Hermes Token 的 Actor ID；
6. 归档并恢复验收订阅（均需确认）；
7. 验证 Reminder Consumer 能 claim，并且只有实际通知成功后 ack。

## 9. systemd 与每日备份

内置 PostgreSQL部署可安装仓库提供的 unit：

```bash
sudo cp deploy/systemd/subscription-manager*.service /etc/systemd/system/
sudo cp deploy/systemd/subscription-manager-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now subscription-manager.service
sudo systemctl enable --now subscription-manager-backup.timer
systemctl list-timers subscription-manager-backup.timer
```

`subscription-manager.service` 当前使用内置数据库 Compose；外部数据库部署应先复制 unit 并将 Compose 文件改为 `deploy/compose.external-db.yml`，再安装。备份必须加密复制到异机，且需要定期按 [BACKUP_RESTORE.md](BACKUP_RESTORE.md)验证恢复。

内置数据库部署应立即执行首次备份和空库恢复验证：

```bash
sudo systemctl start subscription-manager-backup.service
sudo journalctl -u subscription-manager-backup.service --no-pager -n 50
LATEST_BACKUP="$(find /opt/subscription-manager/backups -maxdepth 1 -type f \
  -name 'subscription-manager-*.dump' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
test -n "$LATEST_BACKUP"
./scripts/verify-restore.sh "$LATEST_BACKUP"
```

恢复验证会拒绝复用已有 validation 容器/volume，并在成功或失败后只清理本次创建的 `subscription-manager-restore-validation` 资源。随后把 dump、`.sha256` sidecar 加密复制到异机；本机验证不能替代异机副本。

## 10. 升级与回滚

升级已有实例：

1. 记录当前 `IMAGE_TAG`、镜像 digest、部署文件 revision、Compose 文件、项目名、数据库名和角色名；
2. 创建备份及 SHA-256，并在隔离空库验证恢复；
3. 拉取/复制经审核的部署文件 revision；
4. 检查 `.env`，保留该数据卷初始化时的 `POSTGRES_DB`、`POSTGRES_USER` 和密码；
5. 将 `IMAGE_TAG` 设为目标 `latest`、SemVer 或不可变 `sha-*` 标签；
6. 运行 `config --quiet`、`pull`，再执行 `up -d --wait`；
7. 记录实际镜像 digest，并验证 migration、订阅数量、ready、UI、Hermes 查询和提醒任务。

应用回滚时，将 `IMAGE_TAG` 改为此前记录的 `sha-*` 标签后重新 `pull` 和 `up -d --wait`。不要通过修改 `POSTGRES_DB`/`POSTGRES_USER` 给已有 volume 重命名，也不要执行 `down --volumes`。迁移后需要回滚时，不应直接跨 migration 降级旧代码；应将已验证备份恢复到新的空数据库/volume，验证后切换。

## 11. 交付记录

部署结束后记录但不要包含 secret：

- Git revision、部署时间、Compose 模式；
- 公开 HTTPS URL；
- migration revision、订阅数量；
- Hermes Token 名称/Actor ID/scopes（不含 Token）；
- Reminder Consumer 周期及最后成功时间；
- 备份位置、SHA-256、异机副本和恢复验证日期。
