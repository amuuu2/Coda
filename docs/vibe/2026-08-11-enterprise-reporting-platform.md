# 企业智能报告与数据分析平台实施方案

## 目标

在 Coda 现有 Vue + FastAPI + PostgreSQL + Redis/ARQ + MinIO + LangGraph 边界内，增加三项可独立使用的能力，并让它们可以由定时 Agent 任务组合成站内经营报告：

- 自动化中心：Cron、时区、启停、立即运行、运行历史和结果详情。
- 抽取中心：版本化 JSON Schema 模板、批次、文档任务、证据、校对和导出。
- 数据分析工作台：MySQL/PostgreSQL 数据源、Schema 元数据、只读 SQL、表格、图表、结论和查询审计。

本次不创建第二套 Agent 执行引擎。定时任务最终仍通过 `submit_run_command` 创建 Coda 原有 `AgentRun`，由现有 ARQ worker 执行；报告生成物沿用 AgentRun 的线程输出目录和结果读取链路。

## 验收标准

- [x] 每个新实体都带 `owner_uid`，列表、详情、修改、删除和导出都执行后端用户范围校验。
- [x] 调度任务支持 Cron、IANA 时区、启停、立即运行、下次执行时间和运行历史；`schedule_id + planned_at` 唯一，活跃 Run 默认每个任务最多一个；取消后的任务不能通过更新或启用接口恢复。
- [x] 任务暂停或取消后，调度器不再派发；失败只允许有限次重试，错过多个周期时合并为最近一次计划。
- [x] 抽取模板包含 JSON Schema、字段说明、必填规则、提示词和版本；批次支持已上传知识文件和批量任务。
- [x] 抽取结果必须经过 JSON Schema 校验；保存原始结果、校验错误、文件/页码/段落证据和人工修订记录；支持 JSON/CSV 导出；ARQ 重试前持久化真实尝试次数和排队状态。
- [x] 数据源只支持 MySQL/PostgreSQL；连接测试和 Schema 同步不在启动时执行；密码使用部署环境的密钥加密后保存，API 和日志不返回明文。
- [x] SQL 只允许成熟 parser 识别出的单条 `SELECT`/CTE；拒绝 DDL、DML、多语句、危险函数和白名单之外的表。
- [x] 查询使用只读事务、超时和最大行数限制，保存问题、SQL、状态、耗时、行数、错误、操作者和来源数据源。
- [ ] 定时 Agent 可以引用抽取结果和受控查询工具，稳定生成 Markdown/HTML/PDF 产物并写入运行历史；代码已接入 AgentRun 和 artifact 摘要，格式转换仍需目标环境验证。
- [x] 前端包含 loading、empty、error、disabled 状态，所有业务 API 定义在 `web/src/apis`。

## 数据模型

模型位于 `yuxi.storage.postgres.models_enterprise`，继承现有 `BusinessBase` 的 metadata，但由显式 Migration 创建。应用启动的旧 `create_all` 会跳过这些表，避免新表被隐式创建。

### 自动化

- `scheduled_agent_tasks`：任务名称、Cron、时区、`agent_slug`、提示词、知识库/Skill/MCP/模型/输出配置、重试上限、暂停状态、`next_run_at` 和 `owner_uid`。
- `scheduled_agent_runs`：计划时间、实际时间、状态、错误、耗时、Token、AgentRun ID、生成物摘要和 `owner_uid`；唯一约束为 `(schedule_id, planned_at)`，并以部分唯一索引约束活跃状态。

### 文档抽取

- `extraction_templates`：模板名称、JSON Schema、字段说明、必填字段、提示词、版本和启用状态。
- `extraction_batches`：模板版本、JSON Schema/字段说明/必填字段/提示词快照、模型、批次状态、总数/成功/失败/取消计数和 `owner_uid`；执行与人工校对不读取后续修改的模板定义。
- `extraction_tasks`：批次中的知识文件、解析/抽取/校验状态、尝试次数、原始结果、校验错误、证据、最终结果和 `owner_uid`。
- `extraction_result_revisions`：任务结果的模型版本、人工修订版本、修订人、修订前后 JSON、证据和时间。

### 数据分析

- `analytics_data_sources`：数据库类型、连接地址、用户名、加密密码、表白名单、启用状态和 `owner_uid`。
- `analytics_schema_tables`：数据源的 schema、表名、列定义、同步时间、是否允许查询和 `owner_uid`。
- `analytics_query_audits`：问题、SQL、查询状态、耗时、行数、图表配置、结论、错误、操作者和 `owner_uid`。

## API

所有路由挂载在 `/api` 下，并通过 `get_required_user` 获取用户。当前 MVP 的管理边界是资源创建者/所有者；管理员可以读取和管理本部门可见资源的策略由后续权限配置补充，本次不使用前端隐藏替代后端鉴权。

### `/api/automation`

- `GET /schedules`
- `POST /schedules`
- `GET /schedules/{schedule_id}`
- `PUT /schedules/{schedule_id}`
- `DELETE /schedules/{schedule_id}`
- `POST /schedules/{schedule_id}/enable`
- `POST /schedules/{schedule_id}/disable`
- `POST /schedules/{schedule_id}/run`
- `GET /schedules/{schedule_id}/runs`
- `GET /runs/{run_id}`

### `/api/extraction`

- `GET/POST /templates`
- `GET/PUT/DELETE /templates/{template_id}`（DELETE 以停用保留历史版本和批次证据）
- `POST /batches`
- `GET /batches`
- `GET /batches/{batch_id}`
- `POST /batches/{batch_id}/rerun`
- `POST /batches/{batch_id}/cancel`
- `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/revise`
- `GET /batches/{batch_id}/export?format=json|csv`

### `/api/analytics`

- `GET/POST /data-sources`
- `GET/PUT/DELETE /data-sources/{source_id}`
- `POST /data-sources/{source_id}/test`
- `POST /data-sources/{source_id}/sync-schema`
- `GET /data-sources/{source_id}/schema`
- `POST /queries`
- `GET /queries`
- `GET /queries/{query_id}`

## 执行链

1. Scheduler worker 读取启用任务，按 `next_run_at <= now` 锁定任务并插入 `(schedule_id, planned_at)` 运行记录。
2. 任务状态为暂停/取消或已存在活跃运行时，不派发；多个错过的计划只保留最近一次。
3. 服务通过现有 `submit_run_command` 创建 `source=scheduled_report` 的 AgentRun，输入提示词包含可访问的抽取结果引用和数据分析工具范围。
4. ARQ worker 执行原有 AgentRun。成功后回写计划运行状态、耗时、Token 和生成物摘要；失败记录 `attempt`，由下一次 scheduler sweep 按 `retry_backoff_seconds * 2^(attempt-1)` 重新派发，超过任务上限后终态化。
5. 文档抽取任务复用 `KnowledgeFile` 的文件标识和现有解析/对象存储边界；抽取结果在服务层校验，无法定位证据时保存 `locatable=false`，不伪造页码。
6. 数据分析服务用 AST parser 解析 SQL，检查单语句、操作类型、危险函数和 Schema 白名单，然后在只读事务中执行并限制超时、行数和列输出。

## 实施状态

- [x] 需求、模型、API、页面和目标环境验收标准已记录。
- [x] 参考项目目录已创建；GitHub 访问在当前环境失败，未获得三个只读参考仓库。
- [x] ORM 与显式升级/回滚 Migration。
- [x] Repository、Service、AgentRun worker 接入和路由注册。
- [x] 前端 API、自动化中心、抽取中心、数据分析工作台。
- [x] Unit、integration、e2e 测试已编写，当前电脑不运行；补充了最终 Agent state 结果落库、定时上下文 metadata、连接 options、短表名和锁/危险函数回归测试。
- [x] Worker 入口已明确复用现有 ARQ 执行链；定时 AgentRun 与文档抽取任务共用 `WorkerSettings`，没有新增第二套执行引擎。
- [ ] 目标部署电脑执行 Migration、依赖安装、测试、构建、启动和完整链路验收。

## 当前环境限制

- 当前目录不包含 `.git` 元数据，因此无法执行 `git status`、`git diff` 或写入 `.git/info/exclude`；没有创建伪 Git 仓库。
- 当前环境禁止安装依赖、访问数据库、执行 Migration、启动服务、运行测试/Lint/Build。
- `Octop`、`docetl`、`WrenAI` 浅克隆均因无法连接 GitHub 失败，方案未引用其未读取的具体代码。
- 新增的 `sqlglot` 依赖尚未写入 `backend/uv.lock`；目标电脑需要先重新锁定依赖并重建 API/Worker 镜像。
- 企业新增 Python 模块、路由和 Migration 文件在当前工作区被 Esafenet 包装为二进制文件；本次按用户要求继续保留并修改代码，不将该保护层视为业务实现的一部分。目标电脑需先确认源码文件可被 Python/构建工具正常读取，再执行后续验证。
- 查询失败审计仅保存异常类型和通用错误，连接测试、Schema 同步和查询 API 对客户端返回通用错误，避免泄露连接细节。
- 定时运行完成时，最终 LangGraph state 的 `artifacts`、`files` 和 `token_usage` 会写入 AI 输出消息 metadata，再由自动化运行同步到运行历史；目标环境仍需验证 Agent 是否实际生成 Markdown/HTML/PDF 文件。
