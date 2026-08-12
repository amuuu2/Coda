<div align="center">
<h1>Coda</h1>

<p><strong>多租户智能体平台与企业知识库</strong><br/>让企业知识可被智能体检索、推理与交付</p>

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=ffffff)](https://github.com/amuuu2/Coda/blob/main/docker-compose.yml)
[![Issues](https://img.shields.io/github/issues/amuuu2/Coda?color=F48D73)](https://github.com/amuuu2/Coda/issues)
[![License](https://img.shields.io/github/license/amuuu2/Coda?logo=github)](https://github.com/amuuu2/Coda/blob/main/LICENSE)

[[English README]](README.en.md)
</div>

## 简介

Coda 是一个基于大模型的智能知识库与知识图谱智能体开发平台。它将 **RAG 检索**、**Milvus 知识库内知识图谱** 与 **LangGraph 多智能体编排** 整合进统一的多租户工作台：管理员配置知识库、模型与权限，用户可以与挂载 Skills、MCP、子智能体和沙盒工具的智能体对话，并获得带引用来源、知识图谱推理与可交付产物的回答。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 · Vite · Pinia |
| 后端 | FastAPI · LangGraph · ARQ |
| 存储 | PostgreSQL · Redis · MinIO · Milvus · Neo4j |
| 文档解析 | MinerU · PaddleX · RapidOCR |
| 部署 | Docker Compose |

## 快速开始

前置要求：Docker Engine 24.0+、Docker Compose 2.20+，以及至少一个可用的大模型 API Key。

```bash
git clone https://github.com/amuuu2/Coda.git
cd Coda

# Linux/macOS
./scripts/init.sh

# Windows PowerShell
.\scripts\init.ps1

docker compose up --build -d
```

使用阿里百炼时，在初始化脚本中选择 `1`，并填写 `DASHSCOPE_API_KEY`。

启动完成后访问：

- Web：<http://localhost:5173>
- API 文档：<http://localhost:5050/docs>

详细配置和开发说明见 [docs](docs/)。

## 致谢

本项目使用或参考了以下开源项目：

- [LightRAG](https://github.com/HKUDS/LightRAG)
- [DeepAgents](https://github.com/langchain-ai/deepagents)
- [DeerFlow](https://github.com/bytedance/deer-flow)
- [RAGflow](https://github.com/infiniflow/ragflow)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [QwenPaw](https://github.com/agentscope-ai/QwenPaw)

## 许可证

本项目采用 MIT 许可证。再发布或分发时必须保留 [LICENSE](LICENSE) 中的版权与许可声明。
