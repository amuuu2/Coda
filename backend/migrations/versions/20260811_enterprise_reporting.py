"""创建企业报告平台所需的 PostgreSQL 表。

该文件由目标部署电脑的显式 Migration 命令调用，应用启动不会调用这里的升级逻辑。
"""

from sqlalchemy import text

MIGRATION_ID = "20260811_enterprise_reporting"

UPGRADE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS scheduled_agent_tasks (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        cron_expression VARCHAR(128) NOT NULL,
        timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
        agent_slug VARCHAR(80) NOT NULL,
        prompt TEXT NOT NULL,
        knowledge_base_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        skill_slugs JSONB NOT NULL DEFAULT '[]'::jsonb,
        mcp_server_slugs JSONB NOT NULL DEFAULT '[]'::jsonb,
        model_spec VARCHAR(255),
        output_config JSONB NOT NULL DEFAULT '{}'::jsonb,
        status VARCHAR(32) NOT NULL DEFAULT 'enabled',
        max_retries INTEGER NOT NULL DEFAULT 2,
        retry_backoff_seconds INTEGER NOT NULL DEFAULT 60,
        next_run_at TIMESTAMPTZ,
        last_run_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_tasks_owner_uid ON scheduled_agent_tasks(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_tasks_agent_slug ON scheduled_agent_tasks(agent_slug)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_tasks_status ON scheduled_agent_tasks(status)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_tasks_next_run_at ON scheduled_agent_tasks(next_run_at)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_tasks_due ON scheduled_agent_tasks(status, next_run_at)",
    """
    CREATE TABLE IF NOT EXISTS scheduled_agent_runs (
        id VARCHAR(64) PRIMARY KEY,
        schedule_id VARCHAR(64) NOT NULL REFERENCES scheduled_agent_tasks(id) ON DELETE CASCADE,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        planned_at TIMESTAMPTZ NOT NULL,
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        status VARCHAR(32) NOT NULL DEFAULT 'pending',
        attempt INTEGER NOT NULL DEFAULT 0,
        agent_run_id VARCHAR(64) REFERENCES agent_runs(id) ON DELETE SET NULL,
        error_message TEXT,
        duration_ms INTEGER,
        input_tokens INTEGER,
        output_tokens INTEGER,
        artifacts JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_scheduled_agent_runs_schedule_planned UNIQUE(schedule_id, planned_at)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_runs_owner_uid ON scheduled_agent_runs(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_runs_schedule_id ON scheduled_agent_runs(schedule_id)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_runs_agent_run_id ON scheduled_agent_runs(agent_run_id)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_runs_status ON scheduled_agent_runs(status)",
    "CREATE INDEX IF NOT EXISTS ix_scheduled_agent_runs_schedule_planned ON scheduled_agent_runs(schedule_id, planned_at)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_scheduled_agent_runs_active_schedule
    ON scheduled_agent_runs(schedule_id)
    WHERE status IN ('pending', 'running', 'retry_waiting')
    """,
    """
    CREATE TABLE IF NOT EXISTS extraction_templates (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        schema_json JSONB NOT NULL,
        field_descriptions JSONB NOT NULL DEFAULT '{}'::jsonb,
        required_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
        prompt TEXT NOT NULL DEFAULT '',
        version INTEGER NOT NULL DEFAULT 1,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_extraction_templates_version UNIQUE(owner_uid, name, version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_extraction_templates_owner_uid ON extraction_templates(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_templates_is_active ON extraction_templates(is_active)",
    """
    CREATE TABLE IF NOT EXISTS extraction_batches (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        template_id VARCHAR(64) NOT NULL REFERENCES extraction_templates(id) ON DELETE RESTRICT,
        template_version INTEGER NOT NULL,
        template_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        template_field_descriptions JSONB NOT NULL DEFAULT '{}'::jsonb,
        template_required_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
        template_prompt TEXT NOT NULL DEFAULT '',
        model_spec VARCHAR(255),
        status VARCHAR(32) NOT NULL DEFAULT 'queued',
        total_count INTEGER NOT NULL DEFAULT 0,
        queued_count INTEGER NOT NULL DEFAULT 0,
        processing_count INTEGER NOT NULL DEFAULT 0,
        succeeded_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        cancelled_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_extraction_batches_owner_uid ON extraction_batches(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_batches_status ON extraction_batches(status)",
    """
    CREATE TABLE IF NOT EXISTS extraction_tasks (
        id VARCHAR(64) PRIMARY KEY,
        batch_id VARCHAR(64) NOT NULL REFERENCES extraction_batches(id) ON DELETE CASCADE,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        file_id VARCHAR(64) NOT NULL REFERENCES knowledge_files(file_id) ON DELETE RESTRICT,
        filename VARCHAR(512) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'queued',
        attempt INTEGER NOT NULL DEFAULT 0,
        raw_result JSONB,
        extracted_result JSONB,
        validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        error_message TEXT,
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_extraction_tasks_batch_status ON extraction_tasks(batch_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_tasks_owner_uid ON extraction_tasks(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_tasks_file_id ON extraction_tasks(file_id)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_tasks_status ON extraction_tasks(status)",
    """
    CREATE TABLE IF NOT EXISTS extraction_result_revisions (
        id VARCHAR(64) PRIMARY KEY,
        task_id VARCHAR(64) NOT NULL REFERENCES extraction_tasks(id) ON DELETE CASCADE,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        revision_no INTEGER NOT NULL,
        revision_type VARCHAR(32) NOT NULL,
        result_json JSONB NOT NULL,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        revised_by_uid VARCHAR(64) REFERENCES users(uid) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_extraction_result_revision_no UNIQUE(task_id, revision_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_extraction_result_revisions_owner_uid ON extraction_result_revisions(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_extraction_result_revisions_task_id ON extraction_result_revisions(task_id)",
    """
    CREATE TABLE IF NOT EXISTS analytics_data_sources (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        db_type VARCHAR(16) NOT NULL,
        host VARCHAR(255) NOT NULL,
        port INTEGER NOT NULL,
        database_name VARCHAR(255) NOT NULL,
        username VARCHAR(255) NOT NULL,
        password_ciphertext TEXT,
        password_env VARCHAR(255),
        options JSONB NOT NULL DEFAULT '{}'::jsonb,
        table_allowlist JSONB NOT NULL DEFAULT '[]'::jsonb,
        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        last_tested_at TIMESTAMPTZ,
        last_synced_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_analytics_data_sources_owner_uid ON analytics_data_sources(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_analytics_data_sources_is_enabled ON analytics_data_sources(is_enabled)",
    """
    CREATE TABLE IF NOT EXISTS analytics_schema_tables (
        id VARCHAR(64) PRIMARY KEY,
        data_source_id VARCHAR(64) NOT NULL REFERENCES analytics_data_sources(id) ON DELETE CASCADE,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        schema_name VARCHAR(255) NOT NULL,
        table_name VARCHAR(255) NOT NULL,
        columns JSONB NOT NULL DEFAULT '[]'::jsonb,
        is_allowed BOOLEAN NOT NULL DEFAULT FALSE,
        synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_analytics_schema_table UNIQUE(data_source_id, schema_name, table_name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_analytics_schema_tables_source_allowed ON analytics_schema_tables(data_source_id, is_allowed)",
    "CREATE INDEX IF NOT EXISTS ix_analytics_schema_tables_owner_uid ON analytics_schema_tables(owner_uid)",
    "CREATE INDEX IF NOT EXISTS ix_analytics_schema_tables_is_allowed ON analytics_schema_tables(is_allowed)",
    """
    CREATE TABLE IF NOT EXISTS analytics_query_audits (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        data_source_id VARCHAR(64) REFERENCES analytics_data_sources(id) ON DELETE SET NULL,
        question TEXT NOT NULL,
        sql_text TEXT,
        model_spec VARCHAR(255),
        status VARCHAR(32) NOT NULL DEFAULT 'queued',
        duration_ms INTEGER,
        row_count INTEGER,
        columns JSONB NOT NULL DEFAULT '[]'::jsonb,
        rows JSONB NOT NULL DEFAULT '[]'::jsonb,
        chart JSONB,
        conclusion TEXT,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_analytics_query_audits_owner_created ON analytics_query_audits(owner_uid, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_analytics_query_audits_data_source_id ON analytics_query_audits(data_source_id)",
    "CREATE INDEX IF NOT EXISTS ix_analytics_query_audits_status ON analytics_query_audits(status)",
)

DOWNGRADE_STATEMENTS = (
    "DROP TABLE IF EXISTS analytics_query_audits",
    "DROP TABLE IF EXISTS analytics_schema_tables",
    "DROP TABLE IF EXISTS analytics_data_sources",
    "DROP TABLE IF EXISTS extraction_result_revisions",
    "DROP TABLE IF EXISTS extraction_tasks",
    "DROP TABLE IF EXISTS extraction_batches",
    "DROP TABLE IF EXISTS extraction_templates",
    "DROP TABLE IF EXISTS scheduled_agent_runs",
    "DROP TABLE IF EXISTS scheduled_agent_tasks",
)


async def upgrade(connection) -> None:
    """按顺序创建企业报告平台表和索引。"""
    for statement in UPGRADE_STATEMENTS:
        await connection.execute(text(statement))


async def downgrade(connection) -> None:
    """按依赖逆序删除企业报告平台表。"""
    for statement in DOWNGRADE_STATEMENTS:
        await connection.execute(text(statement))
