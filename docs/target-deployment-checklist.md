# Agent 质量闭环目标环境部署清单

以下命令只由目标部署电脑执行。本次开发电脑不安装依赖、不连接数据库、不执行 Migration、不运行测试或服务。

## 1. 备份

在项目根目录执行：

```powershell
New-Item -ItemType Directory -Force ..\coda-backup
Copy-Item .env ..\coda-backup\.env.before-agent-quality-loop
docker compose exec -T postgres pg_dump -U postgres -d yuxi -Fc -f /tmp/coda-quality-backup.dump
docker compose cp postgres:/tmp/coda-quality-backup.dump ..\coda-backup\coda-quality-backup.dump
```

确认 `.env` 是文件而不是目录，并确认其中已配置现有 Coda 所需密钥、数据库、Redis 和模型供应商信息。不要把密钥粘贴到日志或代码仓库。

## 2. 构建和基础设施

```powershell
docker compose build
docker compose up -d postgres redis minio sandbox-provisioner
docker compose ps
docker logs postgres --tail 100
```

质量闭环复用现有 PostgreSQL、Redis/ARQ、MinIO 和 AgentRun/Worker。它没有新增第三方依赖；此前已删除的企业报告、抽取和分析模块依赖不应重新安装。

## 3. 执行质量 Migration

```powershell
docker compose run --rm --no-deps api python /app/scripts/run_quality_migration.py upgrade
```

检查表、索引和约束：

```powershell
docker compose exec -T postgres psql -U postgres -d yuxi -c "\\dt quality_*"
docker compose exec -T postgres psql -U postgres -d yuxi -c "\\d+ quality_replay_samples"
docker compose exec -T postgres psql -U postgres -d yuxi -c "\\d+ quality_candidates"
docker compose exec -T postgres psql -U postgres -d yuxi -c "\\d+ quality_experiments"
docker compose exec -T postgres psql -U postgres -d yuxi -c "\\d+ quality_evaluation_results"
```

确认四张质量表的所有者字段、质量候选版本唯一约束、实验结果唯一约束以及指向 `users`、`agents`、`agent_runs` 的外键均存在。

## 4. 测试、检查和启动

```powershell
docker compose up -d api worker web
docker compose exec api uv run --group test pytest test/unit/services/test_quality_service.py
docker compose exec api uv run --group test pytest test/integration/api/test_quality_router.py
docker compose exec api uv run --group test pytest test/e2e/test_agent_quality_loop.py -m e2e
docker compose exec api uv run --group dev ruff check server package test
docker compose exec api uv run --group dev ruff format --check server package test
docker compose exec api uv run python -m compileall server package
docker compose exec web pnpm build
```

按目标环境项目规范执行完整测试、Lint、类型检查和 Build；上面是质量闭环最小检查集。前端若项目存在独立 typecheck 命令，也应按 `web/package.json` 的 scripts 执行。

## 5. 功能验收顺序

1. 登录并确认 Agent 管理页出现“质量闭环”。
2. 选择可管理 Agent，手工添加一条 Replay 样本；确认普通用户看不到该样本。
3. 从真实 AgentRun 收集样本，确认输入和输出已保存。
4. 创建只修改 Prompt、模型或 Skill 的候选，确认空配置、未知字段、不可用模型和无权 Skill 被拒绝。
5. 创建并运行实验，确认每条样本有 baseline/candidate 结果、分数、判定理由、Run ID 和耗时。
6. 在未实验时尝试批准，确认被拒绝；完成实验后批准、发布并检查 Agent 配置变化。
7. 回滚候选，确认恢复发布前配置；再次发布新候选时确认旧发布版本变为 `superseded`。
8. 检查 API、Worker 和 PostgreSQL 日志，不应出现密钥、候选完整敏感配置或跨用户数据。

## 6. 失败回滚

Migration 失败且事务未提交时先检查日志和数据库状态。需要回滚质量表时执行：

```powershell
docker compose run --rm --no-deps api python /app/scripts/run_quality_migration.py downgrade
```

若数据库或部署状态无法确认，停止 API/Worker，使用备份恢复：

```powershell
docker compose stop api worker web
docker compose cp ..\coda-backup\coda-quality-backup.dump postgres:/tmp/coda-quality-backup.dump
docker compose exec -T postgres pg_restore --clean --if-exists -U postgres -d yuxi /tmp/coda-quality-backup.dump
```

恢复后重新检查业务表、质量表和服务日志，再决定是否重新升级。
