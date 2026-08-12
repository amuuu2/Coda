"""受控数据分析：数据源连接、Schema 同步、Text-to-SQL 和只读执行。"""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import URL, create_engine, delete, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.repositories.enterprise_repository import EnterpriseRepository
from yuxi.services.enterprise_secrets import encrypt_secret, resolve_data_source_password
from yuxi.services.sql_guard import validate_read_only_sql
from yuxi.storage.postgres.models_enterprise import AnalyticsDataSource, AnalyticsQueryAudit, AnalyticsSchemaTable
from yuxi.utils.datetime_utils import utc_now_naive

SUPPORTED_DATABASE_TYPES = {"postgresql", "mysql"}
MAX_QUERY_ROWS = 1000
MAX_QUERY_TIMEOUT_SECONDS = 60


def _engine_url(source: AnalyticsDataSource) -> URL:
    """构造只用于目标数据源的 SQLAlchemy URL，不把密码写入日志。"""
    password = resolve_data_source_password(source)
    driver = "postgresql+psycopg" if source.db_type == "postgresql" else "mysql+pymysql"
    return URL.create(
        drivername=driver,
        username=source.username,
        password=password,
        host=source.host,
        port=source.port,
        database=source.database_name,
    )


def _new_engine(source: AnalyticsDataSource):
    """创建短生命周期连接引擎，避免跨请求缓存数据源凭证。"""
    connect_args = dict(source.options or {})
    connect_args.setdefault("connect_timeout", 5)
    return create_engine(
        _engine_url(source),
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )


def _dialect(source: AnalyticsDataSource) -> str:
    return "postgres" if source.db_type == "postgresql" else "mysql"


def _json_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把数据库驱动返回值转换成 JSONB 可以持久化的值。"""
    def normalize(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value) if value % 1 else int(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    return [normalize(row) for row in rows]


def _allowed_tables(schema_tables: list[AnalyticsSchemaTable]) -> set[str]:
    discovered: set[str] = set()
    short_names: dict[str, set[str]] = {}
    for table in schema_tables:
        if not table.is_allowed:
            continue
        full_name = f"{table.schema_name}.{table.table_name}".lower()
        short_name = table.table_name.strip().lower()
        discovered.add(full_name)
        short_names.setdefault(short_name, set()).add(full_name)
    discovered.update(short_name for short_name, full_names in short_names.items() if len(full_names) == 1)
    return discovered


def _configured_table_names(discovered: list[dict[str, Any]], configured: set[str]) -> set[str]:
    """根据白名单生成允许查询的完整表名，拒绝歧义短表名。"""
    short_name_counts: dict[str, int] = {}
    for item in discovered:
        short_name = str(item["table_name"]).strip().lower()
        short_name_counts[short_name] = short_name_counts.get(short_name, 0) + 1

    allowed = set()
    for item in discovered:
        full_name = f"{item['schema_name']}.{item['table_name']}".lower()
        short_name = str(item["table_name"]).strip().lower()
        if full_name in configured or (short_name in configured and short_name_counts[short_name] == 1):
            allowed.add(full_name)
    return allowed


async def create_data_source(db: AsyncSession, owner_uid: str, data: dict) -> AnalyticsDataSource:
    """创建数据源；密码只接受写入，不在实体响应中返回。"""
    db_type = str(data.get("db_type") or "").lower()
    if db_type not in SUPPORTED_DATABASE_TYPES:
        raise ValueError("数据源类型只支持 postgresql 或 mysql")
    password_env = str(data.get("password_env") or "").strip() or None
    password = data.get("password")
    if not password and not password_env:
        raise ValueError("必须提供 password 或 password_env")
    source = AnalyticsDataSource(
        id=str(__import__("uuid").uuid4()),
        owner_uid=str(owner_uid),
        name=str(data.get("name") or "").strip(),
        db_type=db_type,
        host=str(data.get("host") or "").strip(),
        port=int(data.get("port") or (5432 if db_type == "postgresql" else 3306)),
        database_name=str(data.get("database_name") or "").strip(),
        username=str(data.get("username") or "").strip(),
        password_ciphertext=encrypt_secret(str(password)) if password else None,
        password_env=password_env,
        options=dict(data.get("options") or {}),
        table_allowlist=list(data.get("table_allowlist") or []),
        is_enabled=bool(data.get("is_enabled", True)),
    )
    if not source.name or not source.host or not source.database_name or not source.username:
        raise ValueError("数据源名称、主机、数据库和用户名不能为空")
    db.add(source)
    await db.flush()
    return source


def update_data_source(source: AnalyticsDataSource, data: dict) -> AnalyticsDataSource:
    """更新数据源非敏感配置和写入式密码。"""
    if "db_type" in data:
        db_type = str(data["db_type"] or "").lower()
        if db_type not in SUPPORTED_DATABASE_TYPES:
            raise ValueError("数据源类型只支持 postgresql 或 mysql")
        source.db_type = db_type

    for field in ("name", "host", "port", "database_name", "username", "options", "table_allowlist", "is_enabled"):
        if field in data:
            setattr(source, field, data[field])
    if data.get("password_env"):
        source.password_env = str(data["password_env"]).strip()
    if data.get("password"):
        source.password_ciphertext = encrypt_secret(str(data["password"]))
        source.password_env = None
    source.updated_at = utc_now_naive()
    return source


async def test_data_source(db: AsyncSession, source: AnalyticsDataSource) -> dict[str, Any]:
    """连接数据源并执行轻量探针，不返回连接凭证。"""
    def probe() -> None:
        engine = _new_engine(source)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()

    await asyncio.to_thread(probe)
    source.last_tested_at = utc_now_naive()
    return {"status": "ok", "tested_at": source.last_tested_at.isoformat()}


async def sync_schema(db: AsyncSession, source: AnalyticsDataSource) -> list[AnalyticsSchemaTable]:
    """读取目标数据库元数据并应用表白名单。"""
    def inspect_schema() -> list[dict[str, Any]]:
        engine = _new_engine(source)
        try:
            database_inspector = inspect(engine)
            if source.db_type == "postgresql":
                excluded_schemas = {"information_schema", "pg_catalog", "pg_toast"}
                schemas = [schema for schema in database_inspector.get_schema_names() if schema not in excluded_schemas]
            else:
                schemas = [None]
            tables: list[dict[str, Any]] = []
            for schema in schemas:
                for table_name in database_inspector.get_table_names(schema=schema):
                    columns = [
                        {
                            "name": column["name"],
                            "type": str(column["type"]),
                            "nullable": bool(column.get("nullable", True)),
                        }
                        for column in database_inspector.get_columns(table_name, schema=schema)
                    ]
                    tables.append({"schema_name": schema or source.database_name, "table_name": table_name, "columns": columns})
            return tables
        finally:
            engine.dispose()

    discovered = await asyncio.to_thread(inspect_schema)
    configured = {str(item).strip().lower() for item in source.table_allowlist or [] if str(item).strip()}
    allowed_names = _configured_table_names(discovered, configured)
    await db.execute(delete(AnalyticsSchemaTable).where(AnalyticsSchemaTable.data_source_id == source.id))
    result = []
    for item in discovered:
        full_name = f"{item['schema_name']}.{item['table_name']}".lower()
        table = AnalyticsSchemaTable(
            id=str(__import__("uuid").uuid4()),
            data_source_id=source.id,
            owner_uid=source.owner_uid,
            schema_name=item["schema_name"],
            table_name=item["table_name"],
            columns=item["columns"],
            is_allowed=full_name in allowed_names,
            synced_at=utc_now_naive(),
        )
        db.add(table)
        result.append(table)
    source.last_synced_at = utc_now_naive()
    await db.flush()
    return result


async def generate_sql(question: str, schema_tables: list[AnalyticsSchemaTable], model_spec: str | None) -> str:
    """使用 Coda 已配置聊天模型生成候选 SQL，随后仍必须经过 AST 安全门禁。"""
    from yuxi.agents.models import load_chat_model

    schema = "\n".join(
        f"{table.schema_name}.{table.table_name}: "
        + ", ".join(f"{column.get('name')} ({column.get('type')})" for column in table.columns or [])
        for table in schema_tables
        if table.is_allowed
    )
    prompt = (
        "你是企业数据分析 SQL 生成器。只输出一条 SQL，不要解释，不要 Markdown。"
        "只能使用给定 Schema 中的表，只能 SELECT/CTE，最多返回 1000 行。\n"
        f"Schema:\n{schema}\n问题:\n{question}"
    )
    response = await load_chat_model(model_spec).ainvoke(prompt)
    content = getattr(response, "content", response)
    sql = content if isinstance(content, str) else str(content)
    if "```" in sql:
        sql = sql.split("```", 2)[1].removeprefix("sql").strip()
    return sql.strip().rstrip(";")


def _execute_sync(source: AnalyticsDataSource, sql: str, allowed_tables: set[str], timeout_seconds: int, max_rows: int):
    validation = validate_read_only_sql(sql, dialect=_dialect(source), allowed_tables=allowed_tables)
    engine = _new_engine(source)
    started = time.monotonic()
    try:
        with engine.connect() as connection:
            if source.db_type == "mysql":
                # MySQL 的事务只读属性必须在 START TRANSACTION 前设置。
                connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
                connection.commit()
            with connection.begin():
                if source.db_type == "postgresql":
                    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                    connection.exec_driver_sql(f"SET LOCAL statement_timeout = {timeout_seconds * 1000}")
                else:
                    connection.exec_driver_sql(f"SET SESSION MAX_EXECUTION_TIME = {timeout_seconds * 1000}")
                limited_sql = f"SELECT * FROM ({validation.sql}) AS coda_query LIMIT {max_rows}"
                result = connection.execute(text(limited_sql))
                rows = _json_safe_rows([dict(row._mapping) for row in result.fetchmany(max_rows)])
                columns = list(result.keys())
        return validation, limited_sql, columns, rows, int((time.monotonic() - started) * 1000)
    finally:
        engine.dispose()


def build_chart(columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """为包含数值列的查询结果生成最小图表配置。"""
    if not rows:
        return None
    numeric_columns = [
        column
        for column in columns
        if any(isinstance(row.get(column), (int, float)) for row in rows)
    ]
    if not numeric_columns:
        return None
    dimension = next((column for column in columns if column not in numeric_columns), columns[0])
    return {"type": "line", "dimension": dimension, "metrics": numeric_columns[:4]}


async def execute_question(
    db: AsyncSession,
    source: AnalyticsDataSource,
    schema_tables: list[AnalyticsSchemaTable],
    question: str,
    sql: str | None,
    model_spec: str | None,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
) -> AnalyticsQueryAudit:
    """生成并执行受控 SQL，保存完整查询审计。"""
    if not 1 <= timeout_seconds <= MAX_QUERY_TIMEOUT_SECONDS:
        raise ValueError(f"查询超时必须在 1 到 {MAX_QUERY_TIMEOUT_SECONDS} 秒之间")
    max_rows = min(max(1, max_rows), MAX_QUERY_ROWS)
    audit = AnalyticsQueryAudit(
        id=str(__import__("uuid").uuid4()),
        owner_uid=source.owner_uid,
        data_source_id=source.id,
        question=question.strip(),
        model_spec=model_spec,
        status="running",
    )
    db.add(audit)
    await db.flush()
    try:
        candidate_sql = sql or await generate_sql(question, schema_tables, model_spec)
        allowed_tables = _allowed_tables(schema_tables)
        validation, executed_sql, columns, rows, duration_ms = await asyncio.wait_for(
            asyncio.to_thread(_execute_sync, source, candidate_sql, allowed_tables, timeout_seconds, max_rows),
            timeout=timeout_seconds + 2,
        )
        audit.sql_text = executed_sql
        audit.columns = columns
        audit.rows = rows
        audit.row_count = len(rows)
        audit.duration_ms = duration_ms
        audit.chart = build_chart(columns, rows)
        audit.conclusion = f"查询返回 {len(rows)} 行，字段数为 {len(columns)}。"
        audit.status = "success"
    except Exception as exc:
        audit.status = "failed"
        audit.error_message = f"{type(exc).__name__}: 查询执行失败"
        await db.commit()
        raise
    await db.flush()
    return audit
