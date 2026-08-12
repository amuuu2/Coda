"""数据分析工作台 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from yuxi.repositories.enterprise_repository import EnterpriseRepository
from yuxi.services.enterprise_analytics_service import (
    create_data_source,
    execute_question,
    sync_schema,
    test_data_source,
    update_data_source,
)
from yuxi.storage.postgres.models_business import User

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


class DataSourcePayload(BaseModel):
    """数据源写入参数，password 只用于写入。"""

    name: str = Field(min_length=1, max_length=255)
    db_type: str
    host: str
    port: int | None = Field(default=None, ge=1, le=65535)
    database_name: str
    username: str
    password: str | None = None
    password_env: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    table_allowlist: list[str] = Field(default_factory=list)
    is_enabled: bool = True


class QueryPayload(BaseModel):
    """自然语言数据分析请求。"""

    data_source_id: str
    question: str = Field(min_length=1)
    sql: str | None = None
    model_spec: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=60)
    max_rows: int = Field(default=1000, ge=1, le=1000)


def _raise_validation(exc: ValueError) -> None:
    detail = exc.args[0] if exc.args else str(exc)
    raise HTTPException(status_code=422, detail=detail) from exc


@analytics_router.get("/data-sources")
async def list_data_sources(current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)):
    sources = await EnterpriseRepository(db).list_data_sources(str(current_user.uid))
    return {"data_sources": [source.to_dict() for source in sources]}


@analytics_router.post("/data-sources")
async def create_data_source_route(
    payload: DataSourcePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await create_data_source(db, str(current_user.uid), payload.model_dump())
    except ValueError as exc:
        _raise_validation(exc)
    return {"data_source": source.to_dict()}


@analytics_router.get("/data-sources/{source_id}")
async def get_data_source(
    source_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    source = await EnterpriseRepository(db).get_data_source(source_id, str(current_user.uid))
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"data_source": source.to_dict()}


@analytics_router.put("/data-sources/{source_id}")
async def update_data_source_route(
    source_id: str,
    payload: DataSourcePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    source = await EnterpriseRepository(db).get_data_source(source_id, str(current_user.uid))
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    try:
        source = update_data_source(source, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        _raise_validation(exc)
    return {"data_source": source.to_dict()}


@analytics_router.delete("/data-sources/{source_id}")
async def delete_data_source(
    source_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    source = await EnterpriseRepository(db).get_data_source(source_id, str(current_user.uid))
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    await db.delete(source)
    return {"success": True}


@analytics_router.post("/data-sources/{source_id}/test")
async def test_data_source_route(
    source_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    source = await EnterpriseRepository(db).get_data_source(source_id, str(current_user.uid))
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    try:
        result = await test_data_source(db, source)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="数据源连接失败，请检查配置和目标数据库状态") from exc
    return result


@analytics_router.post("/data-sources/{source_id}/sync-schema")
async def sync_schema_route(
    source_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    source = await EnterpriseRepository(db).get_data_source(source_id, str(current_user.uid))
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    try:
        tables = await sync_schema(db, source)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Schema 同步失败，请检查配置和目标数据库状态") from exc
    return {"data_source": source.to_dict(), "tables": [table.to_dict() for table in tables]}


@analytics_router.get("/data-sources/{source_id}/schema")
async def list_schema(
    source_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    source = await EnterpriseRepository(db).get_data_source(source_id, str(current_user.uid))
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    tables = await EnterpriseRepository(db).list_schema_tables(source_id, str(current_user.uid))
    return {"tables": [table.to_dict() for table in tables]}


@analytics_router.post("/queries")
async def execute_query(
    payload: QueryPayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    repo = EnterpriseRepository(db)
    source = await repo.get_data_source(payload.data_source_id, str(current_user.uid))
    if not source or not source.is_enabled:
        raise HTTPException(status_code=404, detail="数据源不存在或已停用")
    schema_tables = await repo.list_schema_tables(source.id, str(current_user.uid))
    try:
        audit = await execute_question(
            db,
            source,
            schema_tables,
            payload.question,
            payload.sql,
            payload.model_spec,
            payload.timeout_seconds,
            payload.max_rows,
        )
    except ValueError as exc:
        _raise_validation(exc)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="查询执行失败，请查看查询历史中的错误状态") from exc
    return {"query": audit.to_dict()}


@analytics_router.get("/queries")
async def list_queries(
    limit: int = 50,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    audits = await EnterpriseRepository(db).list_query_audits(str(current_user.uid), min(max(limit, 1), 100))
    return {"queries": [audit.to_dict() for audit in audits]}


@analytics_router.get("/queries/{query_id}")
async def get_query(
    query_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    audit = await EnterpriseRepository(db).get_query_audit(query_id, str(current_user.uid))
    if not audit:
        raise HTTPException(status_code=404, detail="查询记录不存在")
    return {"query": audit.to_dict()}
