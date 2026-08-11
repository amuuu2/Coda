<div align="center">
<h1>Coda</h1>

<p><strong>A multi-tenant agent platform and enterprise knowledge base</strong><br/>Make enterprise knowledge retrievable, reasoned over, and deliverable by agents</p>

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=ffffff)](https://github.com/amuuu2/Coda/blob/main/docker-compose.yml)
[![Issues](https://img.shields.io/github/issues/amuuu2/Coda?color=F48D73)](https://github.com/amuuu2/Coda/issues)
[![License](https://img.shields.io/github/license/amuuu2/Coda?logo=github)](https://github.com/amuuu2/Coda/blob/main/LICENSE)

[[中文说明]](README.md)
</div>

## Introduction

Coda is an LLM-powered platform for building knowledge-base and knowledge-graph agents. It combines **RAG retrieval**, **Milvus-backed knowledge graphs**, and **LangGraph multi-agent orchestration** in a multi-tenant workspace. Administrators manage knowledge bases, models, and permissions, while users work with agents that can mount Skills, MCPs, sub-agents, and sandbox tools.

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Frontend | Vue 3 · Vite · Pinia |
| Backend | FastAPI · LangGraph · ARQ |
| Storage | PostgreSQL · Redis · MinIO · Milvus · Neo4j |
| Document parsing | MinerU · PaddleX · RapidOCR |
| Deployment | Docker Compose |

## Quick Start

Prerequisites: Docker Engine 24.0+, Docker Compose 2.20+, and at least one working LLM API key.

```bash
git clone https://github.com/amuuu2/Coda.git
cd Coda

# Linux/macOS
./scripts/init.sh

# Windows PowerShell
.\scripts\init.ps1

docker compose up --build -d
```

For Alibaba Bailian, select `1` in the initialization script and enter `DASHSCOPE_API_KEY`.

Once the services are ready, open:

- Web: <http://localhost:5173>
- API docs: <http://localhost:5050/docs>

See [docs](docs/) for configuration and development guides.

## Acknowledgements

This project uses or references the following open-source projects:

- [LightRAG](https://github.com/HKUDS/LightRAG)
- [DeepAgents](https://github.com/langchain-ai/deepagents)
- [DeerFlow](https://github.com/bytedance/deer-flow)
- [RAGflow](https://github.com/infiniflow/ragflow)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [QwenPaw](https://github.com/agentscope-ai/QwenPaw)

## License

This project is licensed under the MIT License. Redistributions must retain the copyright and permission notices in [LICENSE](LICENSE).
