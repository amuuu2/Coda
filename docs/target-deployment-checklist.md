# 企业报告平台目标部署清单

本清单必须在目标部署电脑执行。当前源码工作区没有运行数据库、Docker、依赖或服务；本次仅完成静态代码、Migration、测试和清单。参考仓库目录已加入 `.gitignore`；若目标副本包含 `.git`，还应把 `.reference-repos/` 写入 `.git/info/exclude`。

## 1. 备份

在仓库根目录执行，备份文件放到仓库外的受控目录，并通过目标环境的密码管理方式提供 `.env`，不要把敏感值写入命令历史、日志或文档：

```powershell
New-Item -ItemType Directory -Force ..\coda-backup | Out-Null
Copy-Item .env ..\coda-backup\.env.before-enterprise-reporting
docker compose exec -T postgres pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB --format=custom --file=/tmp/coda-before-enterprise-reporting.dump
docker compose cp postgres:/tmp/coda-before-enterprise-reporting.dump ..\coda-backup\coda-before-enterprise-reporting.dump
```

如果目标环境没有导出 `POSTGRES_USER`/`POSTGRES_DB`，使用部署配置中的数据库用户名和库名执行同一条 `pg_dump`，不要在回复或日志中打印密码。

## 2. 安装新增依赖

当前代码新增 Python 依赖 `croniter`、`jsonschema` 和 `sqlglot`。其中 `croniter`、`jsonschema` 已存在于锁文件，`sqlglot` 需要目标电脑重新锁定；本次没有执行：

```powershell
docker compose run --rm --no-deps -w /workspace -v "${PWD}/backend:/workspace" api uv lock
docker compose build api worker
docker compose run --rm --no-deps -v "${PWD}/backend:/app" api uv sync --group test --no-dev
```

前端没有新增 npm 依赖，继续使用仓库现有 `web/pnpm-lock.yaml`。

## 3. 启动基础设施

```powershell
docker compose up -d postgres redis minio
docker compose ps
```

确认 `postgres`、`redis`、`minio` 为 healthy。若经营报告需要 OCR/文档解析服务，再按目标环境资源启用 `all` profile：

```powershell
docker compose --profile all up -d
```

## 4. 执行 Migration

先确认 API/worker 镜像已经包含当前源码和新依赖，再只执行一次显式升级脚本：

```powershell
docker compose run --rm api uv run python scripts/run_enterprise_migrations.py upgrade
```

Migration 文件位于 `backend/migrations/versions/20260811_enterprise_reporting.py`，提供 `upgrade` 和 `downgrade`。不要用应用启动、`create_all` 或手工 `CREATE TABLE` 代替 Migration。

## 5. 检查数据库结构

```powershell
docker compose exec postgres psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "\dt scheduled_agent_* extraction_* analytics_*"
docker compose exec postgres psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "\di *scheduled*; \di *extraction*; \di *analytics*"
docker compose exec postgres psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "SELECT conname, conrelid::regclass, contype FROM pg_constraint WHERE conrelid::regclass::text LIKE ANY (ARRAY['scheduled_agent_%','extraction_%','analytics_%']);"
```

检查每张新表的 `owner_uid` 外键、`schedule_id + planned_at` 唯一约束、活跃运行部分唯一索引、数据源白名单索引和级联策略。

## 6. 执行测试

```powershell
docker compose run --rm api uv run pytest -m unit
docker compose run --rm api uv run pytest -m integration
docker compose run --rm api uv run pytest -m e2e
docker compose run --rm web pnpm test:unit
```

本次新增测试在当前电脑只编写不运行。真实 integration/e2e 需要数据库、Redis、MinIO、解析服务、模型供应商和认证数据。

## 7. Lint、类型检查和 Build

```powershell
docker compose run --rm api uv run ruff check package migrations scripts
docker compose run --rm api uv run ruff format --check package migrations scripts
docker compose run --rm web pnpm run lint
docker compose run --rm web pnpm run build
```

项目当前没有统一的 Python 类型检查脚本；目标环境可按团队标准补充 `pyright` 或 `mypy`，至少检查新增后端模块和 Migration。

## 8. 启动服务

```powershell
docker compose up -d api worker web
docker compose ps
docker logs api-dev --tail 100
docker logs worker-dev --tail 100
```

确认应用启动日志没有新表缺失、Migration 版本不匹配、Redis 投递或解析服务错误。

## 9. 功能验收顺序

1. 使用普通用户创建自动化任务，配置 Agent、提示词、知识库、Skills/MCP、模型、Markdown 输出、Cron 和时区；验证后端越权访问被拒绝。
2. 启停任务并立即运行；检查 `scheduled_agent_runs` 的计划时间、实际时间、状态、`agent_run_id`、耗时、Token 和生成物，重复请求不能产生重复的 `(schedule_id, planned_at)`；取消任务后验证更新和重新启用都会被拒绝。
3. 创建两个抽取模板版本，选择已有知识文件建立批次；验证排队、解析、抽取、校验、成功/失败/取消、证据、人工修订和 JSON/CSV 导出。
4. 创建 PostgreSQL 或 MySQL 数据源，测试连接、同步 Schema 并设置表白名单；验证明文密码不会出现在 API 响应、日志和审计记录。
5. 输入自然语言问题，验证返回问题、受白名单约束的单条 SELECT/CTE、表格、图表和结论；验证 DDL、DML、多语句、危险函数、非白名单表和超时查询被拒绝并写入审计。
6. 创建“经营周报”任务：每周一读取指定业务文档和只读数据库，提取关键字段，分析最近一周指标，生成包含数据表、图表和来源证据的 Markdown/HTML/PDF，并在自动化运行历史和详情中可见。

## 10. 失败回滚

仅当升级失败且确认没有依赖新增表的业务写入时，在目标环境执行：

```powershell
docker compose run --rm api uv run python scripts/run_enterprise_migrations.py downgrade
```

然后恢复数据库备份并重启服务：

```powershell
docker compose down
docker compose up -d postgres redis minio
docker compose exec -T postgres pg_restore --clean --if-exists -U $env:POSTGRES_USER -d $env:POSTGRES_DB < ..\coda-backup\coda-before-enterprise-reporting.dump
docker compose up -d api worker web
```

回滚后重新检查原有对话、知识库、AgentRun 和附件功能。Migration、依赖或完整链路验证失败时不要继续生产验收，保留 API/worker 日志和数据库检查结果供定位。
