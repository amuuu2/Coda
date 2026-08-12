"""企业报告 Agent 使用的受控数据和抽取结果工具。"""

from __future__ import annotations

from typing import Any

from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import tool
from yuxi.repositories.enterprise_repository import EnterpriseRepository
from yuxi.services.enterprise_analytics_service import execute_question
from yuxi.storage.postgres.manager import pg_manager


def _runtime_uid(runtime: ToolRuntime | None) -> str | None:
    """读取 Agent runtime 中的用户归属。"""
    uid = getattr(getattr(runtime, "context", None), "uid", None)
    value = str(uid or "").strip()
    return value or None


class ExtractionResultsInput(BaseModel):
    """读取结构化抽取批次的输入。"""

    batch_id: str = Field(min_length=1, description="抽取批次 ID")


@tool(
    category="buildin",
    tags=["企业报告"],
    display_name="读取结构化抽取结果",
    args_schema=ExtractionResultsInput,
)
async def get_extraction_batch_results(batch_id: str, runtime: ToolRuntime) -> dict[str, Any] | str:
    """读取当前用户有权访问的抽取批次、字段结果和原文证据。"""
    owner_uid = _runtime_uid(runtime)
    if not owner_uid:
        return "无法确定当前用户，不能读取抽取结果"

    async with pg_manager.get_async_session_context() as db:
        repo = EnterpriseRepository(db)
        batch = await repo.get_batch(batch_id.strip(), owner_uid)
        if not batch:
            return "抽取批次不存在或当前用户无权访问"
        tasks = await repo.list_extraction_tasks(batch.id, owner_uid)
        return {
            "batch": batch.to_dict(),
            "tasks": [task.to_dict() for task in tasks],
        }


class ControlledDataQueryInput(BaseModel):
    """受控数据查询工具的输入。"""

    data_source_id: str = Field(min_length=1, description="Coda 数据源 ID")
    question: str = Field(min_length=1, description="自然语言问题")
    sql: str | None = Field(default=None, description="可选的单条 SELECT/CTE SQL")
    timeout_seconds: int = Field(default=30, ge=1, le=60)
    max_rows: int = Field(default=1000, ge=1, le=1000)


@tool(
    category="buildin",
    tags=["企业报告", "数据分析"],
    display_name="运行受控数据查询",
    args_schema=ControlledDataQueryInput,
)
async def run_controlled_data_query(
    data_source_id: str,
    question: str,
    sql: str | None = None,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any] | str:
    """在当前用户所属数据源上执行 AST 校验、白名单和只读事务约束。"""
    owner_uid = _runtime_uid(runtime)
    if not owner_uid:
        return "无法确定当前用户，不能执行数据查询"

    async with pg_manager.get_async_session_context() as db:
        repo = EnterpriseRepository(db)
        source = await repo.get_data_source(data_source_id.strip(), owner_uid)
        if not source or not source.is_enabled:
            return "数据源不存在或已停用"
        schema_tables = await repo.list_schema_tables(source.id, owner_uid)
        try:
            audit = await execute_question(
                db,
                source,
                schema_tables,
                question,
                sql,
                None,
                timeout_seconds,
                max_rows,
            )
        except ValueError as exc:
            return {"status": "rejected", "error": str(exc)}
        except Exception:
            return {"status": "failed", "error": "受控数据查询失败"}
        return audit.to_dict()


class AnalyticsQueryResultInput(BaseModel):
    """读取既有数据分析查询结果的输入。"""

    query_id: str = Field(min_length=1, description="数据分析查询审计 ID")


@tool(
    category="buildin",
    tags=["企业报告", "数据分析"],
    display_name="读取数据分析结果",
    args_schema=AnalyticsQueryResultInput,
)
async def get_analytics_query_result(query_id: str, runtime: ToolRuntime) -> dict[str, Any] | str:
    """读取当前用户有权访问的既有查询结果，避免报告重复访问数据库。"""
    owner_uid = _runtime_uid(runtime)
    if not owner_uid:
        return "无法确定当前用户，不能读取数据分析结果"

    async with pg_manager.get_async_session_context() as db:
        audit = await EnterpriseRepository(db).get_query_audit(query_id.strip(), owner_uid)
        if not audit:
            return "数据分析查询不存在或当前用户无权访问"
        return audit.to_dict()

