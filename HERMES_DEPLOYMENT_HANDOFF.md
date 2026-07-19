# Hermes 主机部署交接入口

本文件是把仓库复制到 Hermes 所在主机后的首要入口。部署执行者应先完整阅读本文件，再按链接读取细节。目标是在不泄露密钥、不破坏已有数据的前提下，完成 Subscription Manager、Hermes Skill 和唯一提醒消费任务的安装。

用户可在复制仓库后直接向 Hermes 发出以下指令：

```text
请进入 Subscription Manager 仓库，完整阅读 HERMES_DEPLOYMENT_HANDOFF.md 及其标记的必读文档。
先只读检查本机 Docker、端口、反向代理、现有 Compose/数据和 Hermes Skill/密钥/周期任务机制，
向我报告部署模式及需要我提供的域名或外部数据库选择；不要输出 secret。
条件明确后按文档构建部署、初始化、安装整个 hermes/ 集成包并创建唯一 Reminder Consumer，
完成全部验收和首个可恢复备份。禁止 down --volumes，已有实例必须先备份并保留原数据库身份。
每个经验证的仓库变更都提交并推送；主机级配置只做任务所需的最小变更。
```

## 执行边界

1. 默认按 Linux 生产主机和 Docker Compose v2 部署，安装目录建议为 `/opt/subscription-manager`。
2. 全新安装优先使用仓库内置 PostgreSQL；已有受管 PostgreSQL 时才选择外部数据库模式。
3. 不安装 Traefik、ntfy 或任何通知供应商。反向代理由主机已有的 Nginx、Caddy、Tunnel 等设施提供。
4. 不输出、提交或写入普通日志：数据库密码、管理员密码、API Token、私钥或完整 `.env`。
5. 不运行 `docker compose down --volumes`。升级已有实例前必须创建并验证备份，并保留该数据卷初始化时的数据库名和角色名。
6. 只运行一个 Scheduler 和一个 Hermes Reminder Consumer。不得用多个同一 Token 的任务并发领取提醒。

## 必读顺序

1. [主机部署手册](docs/HERMES_HOST_DEPLOYMENT.md)：前置检查、配置、启动、反向代理、初始化、验收、升级和回滚。
2. [Hermes 安装说明](hermes/INSTALL.md)：Skill/Tools、密钥、连通性和周期任务。
3. [用户使用说明](docs/USER_GUIDE.md)：自然语言操作、确认规则、提醒、付款和故障处理。
4. [配置变量参考](docs/CONFIGURATION.md)：每个环境变量的含义和范围。
5. [备份恢复手册](docs/BACKUP_RESTORE.md)与[运维手册](docs/OPERATIONS.md)。

## 推荐执行流程

```text
只读检查主机与仓库
        ↓
选择 bundled/external PostgreSQL
        ↓
创建受保护的 .env 并验证 Compose
        ↓
构建、迁移、启动，验证 loopback ready
        ↓
配置用户自有 HTTPS 反向代理
        ↓
bootstrap 管理员并创建 Hermes 最小权限 Token
        ↓
安装 hermes/ Skill 与 Tools，注入 URL/Token 密钥
        ↓
创建唯一的 Reminder Consumer 周期任务
        ↓
完成读、写确认、提醒 claim/ack/fail 与备份验收
```

## 完成标准

部署执行者最终必须向用户报告以下信息，但不得报告任何 secret：

- 使用的 Git revision、部署目录和 Compose 模式；
- Frontend HTTPS 地址以及 ready 状态；
- migration revision，Bundled 模式下的数据库/角色名称；
- Backend、Scheduler、数据库没有宿主机端口；
- Hermes Skill 读取、查询和确认写入测试结果；
- Reminder Consumer 的任务名称、周期和唯一实例证据；
- 首个备份的路径、SHA-256、异机复制状态和恢复验证结果；
- 任何仍需用户处理的 DNS、证书、通知渠道或防火墙事项。

若主机缺少域名/HTTPS、已有数据库身份不明确、端口冲突、备份不可恢复或 Hermes 密钥存储方式无法确定，应停止对应有风险的步骤并向用户说明，而不是猜测或降低安全配置。
