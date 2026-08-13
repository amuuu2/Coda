# Coda 项目简历写法

> 生成日期：2026-08-13  
> 定位：企业知识库 / Agent 工程 / 多智能体平台  
> 可信度说明：以下功能均已从当前仓库源码核验；未发现可直接引用的性能或准确率对比数据，因此不虚构提升比例。

## 推荐写法（正式版）

### Coda - 多租户知识库与多智能体协作平台

**技术栈：** Python、FastAPI、LangGraph、PostgreSQL、Redis / ARQ、Milvus、Neo4j、Vue 3、Docker Compose

**项目简介：** 面向企业内部知识检索和复杂任务协作，搭建集文档解析、混合检索、知识图谱与多智能体执行于一体的平台。管理员可统一配置知识库、模型和访问范围，用户可让智能体调用受控工具、拆分子任务，并获得可回查原文的回答与任务产物。

**核心工作 / 技术亮点：**

1. **保障智能体请求按序且可靠执行：** 针对用户连续提问可能引发的上下文竞争，为同一用户、智能体和会话建立 FIFO 请求队列；使用 `request_id` 幂等和数据库行锁处理重复提交、并发入队与取消，先提交消息和运行状态再投递 ARQ，并通过恢复扫描补发遗留任务，避免数据库显示“运行中”但任务实际未入队。

2. **解决长任务的上下文溢出问题：** 按 token 阈值对会话进行两级压缩，先把超长工具结果转存到会话文件，仅保留内容预览和回查路径；压缩后仍超限时再总结历史并保留最近消息，同时向前端发送压缩状态，兼顾长任务连续执行与关键结果可追溯。

3. **让工具能力按需开放而不是一次性全部暴露：** 智能体读取对应 `SKILL.md` 后才激活能力，再根据依赖关系动态放出本地工具和 MCP 工具；对依赖环、无权限 Skill 和不可用 MCP 显式拦截，减少工具过多造成的上下文占用和误调用风险。

4. **构建可追踪的多智能体协作链路：** 将研究、分析等复杂工作拆成独立的子智能体线程和运行实例，提供启动、进度查询、等待和取消完整生命周期；父智能体通过 `run_id` 追踪结果并校验任务归属，等待超时时保留后台任务供后续继续查询，支持多个长任务并行推进而不阻塞主会话。

5. **打通知识入库到混合检索的完整链路：** 针对 PDF、Office 文档和图片等异构资料，统一完成解析、按结构或语义切块和批量向量化；分块元数据与向量分别写入 PostgreSQL 和 Milvus，任一侧失败即清理两侧已写数据，避免检索结果与原文记录不一致。查询阶段融合语义向量与 BM25 关键词召回，并在精排服务异常时回退到原始召回分数。

6. **用知识图谱补足跨片段关系检索：** 以文档分块为单位抽取实体和关系，先统一实体名称并合并重复属性，再通过幂等写入维护“文档片段 - 实体 - 关系”结构；同时记录分块级抽取和向量化状态，使失败任务可以从未完成数据继续处理，并利用图结构排序召回跨段落关联内容。

7. **建立可回放的 Agent 质量验证流程：** 从真实运行中沉淀测试样本，在隔离会话中分别回放基线配置与候选配置，逐条保存输出、评分依据和差异结果；候选配置需经过实验后才能审批发布，并支持回滚，避免仅凭人工体验直接修改线上智能体。

## 一页简历精简版

### Coda - 多租户知识库与多智能体协作平台

**技术栈：** FastAPI、LangGraph、PostgreSQL、Redis / ARQ、Milvus、Neo4j、Vue 3、Docker Compose

面向企业知识检索与复杂任务协作，搭建集文档解析、RAG 检索、知识图谱和多智能体执行于一体的平台，使智能体能够在权限边界内查询企业资料、调用工具、拆分任务并交付可追溯结果。

- 设计会话级 FIFO 请求队列，结合 `request_id` 幂等、数据库行锁和提交后投递机制处理重复请求与并发冲突，并通过恢复扫描补发未成功入队的运行任务。
- 实现长会话两级压缩：超长工具结果先转存文件，仍超限时再总结历史并保留最近消息，保证复杂任务可持续执行且原始结果可回查。
- 以读取 `SKILL.md` 作为能力激活入口，按依赖动态开放本地工具和 MCP，拦截无权限能力、依赖环与不可用服务，降低工具误调用风险。
- 将复杂任务拆分为独立子智能体线程，提供启动、状态、等待和取消能力；父智能体按运行 ID 跟踪进度，支持多个长任务并行执行和超时后继续查询。
- 建立异构文档解析、结构化切块和混合检索链路；对 PostgreSQL 与 Milvus 双写失败执行清理补偿，并融合向量、BM25 与精排结果，提高语义问法和专业术语的覆盖能力。
- 基于文档片段抽取实体关系并构建知识图谱，统一实体名称、幂等合并重复关系，通过图结构排序召回跨段落关联证据。

## 按岗位替换

### 投递 Agent / LLM 应用岗位

优先保留：长上下文压缩、Skills 按需激活、多智能体协作、混合检索、知识图谱、质量回放。可以将“请求队列”替换为下面这条：

- 建立 Agent 配置回放评测流程，从真实运行沉淀样本，在隔离会话中对比基线与候选配置，保存逐条输出和评分依据，并以审批、发布、回滚控制配置变更风险。

### 投递 Python 后端岗位

优先保留：请求队列、入库一致性、多智能体生命周期、权限控制、任务恢复。可以将“知识图谱”替换为下面这条：

- 设计知识库、智能体和 Skill 的统一资源权限模型，将访问范围细分为全局、部门和指定用户，并限制普通用户的权限上限；后端查询按当前用户过滤可见资源，防止只依赖前端隐藏造成越权访问。

## 每条亮点在解决什么

| 亮点 | 业务问题 | 核心机制 | 可追问细节 |
| --- | --- | --- | --- |
| 请求队列 | 连续提问导致同一会话并发执行、消息顺序混乱 | FIFO、幂等键、行锁、提交后投递、恢复扫描 | 请求状态、消息状态、Run 状态如何衔接 |
| 上下文压缩 | 长对话和大工具输出超过模型上下文 | 工具结果转存、历史摘要、保留最近消息 | 两级阈值、回查路径、压缩事件 |
| Skills 门控 | 工具一次性暴露导致上下文膨胀和误调用 | 读取后激活、依赖解析、动态工具绑定 | 工具依赖、MCP 依赖、依赖环处理 |
| 多智能体 | 长任务阻塞主会话，多个任务难以并行 | 独立线程与 Run、生命周期接口、归属校验 | start / status / await / cancel 的状态流转 |
| 知识入库与检索 | 异构资料难解析，向量库与元数据可能不一致 | 结构化切块、双写补偿、混合召回、精排降级 | 分块字段、清理补偿、召回权重 |
| 知识图谱 | 单纯相似度检索难发现跨片段关系 | 实体归一、幂等合并、图排序召回 | 实体 ID、关系写入、分块级处理状态 |
| 质量回放 | Agent 配置修改依赖主观体验，回归风险高 | 真实样本回放、基线对照、发布与回滚 | 样本来源、评分口径、候选配置状态 |

## 代码验证摘要

- 仓库：`https://github.com/amuuu2/Coda.git`
- 本地目录：`D:\public\Coda-main`
- 核验提交：`ce78be9220d07c5580fa0a93351f7f21d7e4524d`
- 请求队列：`backend/package/yuxi/services/agent_request_queue_service.py`、`backend/package/yuxi/repositories/agent_run_request_repository.py`、`backend/package/yuxi/services/run_worker.py`
- 上下文压缩：`backend/package/yuxi/agents/middlewares/summary.py`、`backend/package/yuxi/agents/buildin/chatbot/graph.py`
- Skills / MCP：`backend/package/yuxi/agents/middlewares/skills.py`、`backend/package/yuxi/agents/mcp/service.py`
- 多智能体：`backend/package/yuxi/agents/middlewares/subagent_task.py`、`backend/package/yuxi/services/subagent_run_service.py`
- 知识入库与检索：`backend/package/yuxi/knowledge/implementations/milvus.py`、`backend/package/yuxi/knowledge/chunking/ragflow_like/`、`backend/package/yuxi/agents/toolkits/kbs/tools.py`
- 知识图谱：`backend/package/yuxi/knowledge/graphs/milvus_graph_service.py`、`backend/package/yuxi/knowledge/graphs/graph_utils.py`
- 质量回放：`backend/package/yuxi/services/quality_service.py`、`backend/server/routers/quality_router.py`
- 权限模型：`backend/package/yuxi/permissions/resource_permission.py`

## 建议补充的量化数据

只有完成真实测试后再写入简历，可优先补充：同一会话并发请求数与顺序正确率、pending 任务恢复成功率、压缩前后 token 数、检索 Recall@10 / F1@10、基线与候选配置评分差值、知识图谱构建吞吐和失败续跑成功率。不要使用未经测试的百分比。
