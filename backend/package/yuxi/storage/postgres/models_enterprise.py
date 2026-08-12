"""企业报告、文档抽取和数据分析领域模型。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text

from yuxi.storage.postgres.models_business import Base, JSON_VALUE
from yuxi.utils.datetime_utils import format_utc_datetime, utc_now_naive

SCHEDULE_ACTIVE_STATUSES = ("pending", "running", "retry_waiting")


def _serialize_datetime(value) -> str | None:
    """将数据库时间值转换为 API 使用的 UTC 字符串。"""
    return format_utc_datetime(value)


class ScheduledAgentTask(Base):
    """保存一个可按 Cron 派发的 Agent 报告任务。"""

    __tablename__ = "scheduled_agent_tasks"

    id = Column(String(64), primary_key=True)
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cron_expression = Column(String(128), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    agent_slug = Column(String(80), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    knowledge_base_ids = Column(JSON_VALUE, nullable=False, default=list)
    skill_slugs = Column(JSON_VALUE, nullable=False, default=list)
    mcp_server_slugs = Column(JSON_VALUE, nullable=False, default=list)
    model_spec = Column(String(255), nullable=True)
    output_config = Column(JSON_VALUE, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="enabled", index=True)
    max_retries = Column(Integer, nullable=False, default=2)
    retry_backoff_seconds = Column(Integer, nullable=False, default=60)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回不包含敏感信息的任务摘要。"""
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "name": self.name,
            "description": self.description,
            "cron_expression": self.cron_expression,
            "timezone": self.timezone,
            "agent_slug": self.agent_slug,
            "prompt": self.prompt,
            "knowledge_base_ids": self.knowledge_base_ids or [],
            "skill_slugs": self.skill_slugs or [],
            "mcp_server_slugs": self.mcp_server_slugs or [],
            "model_spec": self.model_spec,
            "output_config": self.output_config or {},
            "status": self.status,
            "enabled": self.status == "enabled",
            "max_retries": self.max_retries,
            "retry_backoff_seconds": self.retry_backoff_seconds,
            "next_run_at": _serialize_datetime(self.next_run_at),
            "last_run_at": _serialize_datetime(self.last_run_at),
            "created_at": _serialize_datetime(self.created_at),
            "updated_at": _serialize_datetime(self.updated_at),
        }


class ScheduledAgentRun(Base):
    """记录定时任务的一次计划执行及其 AgentRun 关联。"""

    __tablename__ = "scheduled_agent_runs"
    __table_args__ = (
        UniqueConstraint("schedule_id", "planned_at", name="uq_scheduled_agent_runs_schedule_planned"),
        Index("ix_scheduled_agent_runs_schedule_planned", "schedule_id", "planned_at"),
        Index(
            "uq_scheduled_agent_runs_active_schedule",
            "schedule_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running', 'retry_waiting')"),
        ),
    )

    id = Column(String(64), primary_key=True)
    schedule_id = Column(
        String(64), ForeignKey("scheduled_agent_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    planned_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    attempt = Column(Integer, nullable=False, default=0)
    agent_run_id = Column(String(64), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    artifacts = Column(JSON_VALUE, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回定时运行历史。"""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "owner_uid": self.owner_uid,
            "planned_at": _serialize_datetime(self.planned_at),
            "started_at": _serialize_datetime(self.started_at),
            "finished_at": _serialize_datetime(self.finished_at),
            "status": self.status,
            "attempt": self.attempt,
            "agent_run_id": self.agent_run_id,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "artifacts": self.artifacts or [],
            "created_at": _serialize_datetime(self.created_at),
        }


class ExtractionTemplate(Base):
    """版本化的结构化文档抽取模板。"""

    __tablename__ = "extraction_templates"
    __table_args__ = (UniqueConstraint("owner_uid", "name", "version", name="uq_extraction_templates_version"),)

    id = Column(String(64), primary_key=True)
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    schema_json = Column(JSON_VALUE, nullable=False)
    field_descriptions = Column(JSON_VALUE, nullable=False, default=dict)
    required_fields = Column(JSON_VALUE, nullable=False, default=list)
    prompt = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回模板定义及其版本。"""
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "name": self.name,
            "schema_json": self.schema_json or {},
            "field_descriptions": self.field_descriptions or {},
            "required_fields": self.required_fields or [],
            "prompt": self.prompt,
            "version": self.version,
            "is_active": bool(self.is_active),
            "created_at": _serialize_datetime(self.created_at),
            "updated_at": _serialize_datetime(self.updated_at),
        }


class ExtractionBatch(Base):
    """记录一批文档抽取任务及模板版本快照。"""

    __tablename__ = "extraction_batches"

    id = Column(String(64), primary_key=True)
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(String(64), ForeignKey("extraction_templates.id", ondelete="RESTRICT"), nullable=False)
    template_version = Column(Integer, nullable=False)
    template_schema_json = Column(JSON_VALUE, nullable=False, default=dict)
    template_field_descriptions = Column(JSON_VALUE, nullable=False, default=dict)
    template_required_fields = Column(JSON_VALUE, nullable=False, default=list)
    template_prompt = Column(Text, nullable=False, default="")
    model_spec = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    total_count = Column(Integer, nullable=False, default=0)
    queued_count = Column(Integer, nullable=False, default=0)
    processing_count = Column(Integer, nullable=False, default=0)
    succeeded_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    cancelled_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回批次进度摘要。"""
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "model_spec": self.model_spec,
            "status": self.status,
            "total_count": self.total_count,
            "queued_count": self.queued_count,
            "processing_count": self.processing_count,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "created_at": _serialize_datetime(self.created_at),
            "updated_at": _serialize_datetime(self.updated_at),
        }


class ExtractionTask(Base):
    """记录一个文档的解析、抽取、校验和证据。"""

    __tablename__ = "extraction_tasks"

    id = Column(String(64), primary_key=True)
    batch_id = Column(String(64), ForeignKey("extraction_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String(64), ForeignKey("knowledge_files.file_id", ondelete="RESTRICT"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="queued", index=True)
    attempt = Column(Integer, nullable=False, default=0)
    raw_result = Column(JSON_VALUE, nullable=True)
    extracted_result = Column(JSON_VALUE, nullable=True)
    validation_errors = Column(JSON_VALUE, nullable=False, default=list)
    evidence = Column(JSON_VALUE, nullable=False, default=list)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回抽取任务结果和证据。"""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "owner_uid": self.owner_uid,
            "file_id": self.file_id,
            "filename": self.filename,
            "status": self.status,
            "attempt": self.attempt,
            "raw_result": self.raw_result,
            "extracted_result": self.extracted_result,
            "validation_errors": self.validation_errors or [],
            "evidence": self.evidence or [],
            "error_message": self.error_message,
            "started_at": _serialize_datetime(self.started_at),
            "finished_at": _serialize_datetime(self.finished_at),
            "created_at": _serialize_datetime(self.created_at),
            "updated_at": _serialize_datetime(self.updated_at),
        }


class ExtractionResultRevision(Base):
    """记录抽取结果的模型版本和人工校对版本。"""

    __tablename__ = "extraction_result_revisions"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("extraction_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    revision_no = Column(Integer, nullable=False)
    revision_type = Column(String(32), nullable=False)
    result_json = Column(JSON_VALUE, nullable=False)
    evidence = Column(JSON_VALUE, nullable=False, default=list)
    revised_by_uid = Column(String(64), ForeignKey("users.uid", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回一个抽取结果修订版本。"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "owner_uid": self.owner_uid,
            "revision_no": self.revision_no,
            "revision_type": self.revision_type,
            "result_json": self.result_json or {},
            "evidence": self.evidence or [],
            "revised_by_uid": self.revised_by_uid,
            "created_at": _serialize_datetime(self.created_at),
        }


class AnalyticsDataSource(Base):
    """保存一个受白名单约束的 MySQL/PostgreSQL 数据源。"""

    __tablename__ = "analytics_data_sources"

    id = Column(String(64), primary_key=True)
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    db_type = Column(String(16), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    password_ciphertext = Column(Text, nullable=True)
    password_env = Column(String(255), nullable=True)
    options = Column(JSON_VALUE, nullable=False, default=dict)
    table_allowlist = Column(JSON_VALUE, nullable=False, default=list)
    is_enabled = Column(Boolean, nullable=False, default=True, index=True)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回数据源配置，但永不返回密码或密文。"""
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "name": self.name,
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database_name": self.database_name,
            "username": self.username,
            "has_password": bool(self.password_ciphertext or self.password_env),
            "options": self.options or {},
            "table_allowlist": self.table_allowlist or [],
            "is_enabled": bool(self.is_enabled),
            "last_tested_at": _serialize_datetime(self.last_tested_at),
            "last_synced_at": _serialize_datetime(self.last_synced_at),
            "created_at": _serialize_datetime(self.created_at),
            "updated_at": _serialize_datetime(self.updated_at),
        }


class AnalyticsSchemaTable(Base):
    """保存数据源同步得到的表和列元数据。"""

    __tablename__ = "analytics_schema_tables"
    __table_args__ = (
        UniqueConstraint("data_source_id", "schema_name", "table_name", name="uq_analytics_schema_table"),
    )

    id = Column(String(64), primary_key=True)
    data_source_id = Column(
        String(64), ForeignKey("analytics_data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    schema_name = Column(String(255), nullable=False)
    table_name = Column(String(255), nullable=False)
    columns = Column(JSON_VALUE, nullable=False, default=list)
    is_allowed = Column(Boolean, nullable=False, default=False, index=True)
    synced_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回表结构元数据。"""
        return {
            "id": self.id,
            "data_source_id": self.data_source_id,
            "owner_uid": self.owner_uid,
            "schema_name": self.schema_name,
            "table_name": self.table_name,
            "columns": self.columns or [],
            "is_allowed": bool(self.is_allowed),
            "synced_at": _serialize_datetime(self.synced_at),
        }


class AnalyticsQueryAudit(Base):
    """保存自然语言分析问题、SQL 和执行审计。"""

    __tablename__ = "analytics_query_audits"

    id = Column(String(64), primary_key=True)
    owner_uid = Column(String(64), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True)
    data_source_id = Column(
        String(64), ForeignKey("analytics_data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question = Column(Text, nullable=False)
    sql_text = Column(Text, nullable=True)
    model_spec = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    duration_ms = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    columns = Column(JSON_VALUE, nullable=False, default=list)
    rows = Column(JSON_VALUE, nullable=False, default=list)
    chart = Column(JSON_VALUE, nullable=True)
    conclusion = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        """返回查询结果，不包含任何数据源密码。"""
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "data_source_id": self.data_source_id,
            "question": self.question,
            "sql_text": self.sql_text,
            "model_spec": self.model_spec,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "row_count": self.row_count,
            "columns": self.columns or [],
            "rows": self.rows or [],
            "chart": self.chart,
            "conclusion": self.conclusion,
            "error_message": self.error_message,
            "created_at": _serialize_datetime(self.created_at),
        }
