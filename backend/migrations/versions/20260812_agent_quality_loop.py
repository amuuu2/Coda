"""创建 Agent 质量评测、回放和候选版本表。

Migration 只由目标环境显式执行，应用启动不会调用这里的 SQL。
"""

from sqlalchemy import text

MIGRATION_ID = "20260812_agent_quality_loop"

UPGRADE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS quality_replay_samples (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        agent_slug VARCHAR(80) NOT NULL REFERENCES agents(slug) ON DELETE CASCADE,
        source_run_id VARCHAR(64) REFERENCES agent_runs(id) ON DELETE SET NULL,
        input_text TEXT NOT NULL,
        expected_output TEXT,
        baseline_output TEXT,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        status VARCHAR(24) NOT NULL DEFAULT 'active',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_quality_replay_owner_agent ON quality_replay_samples(owner_uid, agent_slug)",
    "CREATE INDEX IF NOT EXISTS ix_quality_replay_source_run ON quality_replay_samples(source_run_id)",
    """
    CREATE TABLE IF NOT EXISTS quality_candidates (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        agent_slug VARCHAR(80) NOT NULL REFERENCES agents(slug) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        previous_config_json JSONB,
        status VARCHAR(24) NOT NULL DEFAULT 'draft',
        change_summary TEXT,
        approved_by VARCHAR(64) REFERENCES users(uid) ON DELETE SET NULL,
        approved_at TIMESTAMPTZ,
        published_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_quality_candidates_agent_version UNIQUE(agent_slug, version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_quality_candidates_owner_agent ON quality_candidates(owner_uid, agent_slug)",
    "CREATE INDEX IF NOT EXISTS ix_quality_candidates_status ON quality_candidates(status)",
    """
    CREATE TABLE IF NOT EXISTS quality_experiments (
        id VARCHAR(64) PRIMARY KEY,
        owner_uid VARCHAR(64) NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
        agent_slug VARCHAR(80) NOT NULL REFERENCES agents(slug) ON DELETE CASCADE,
        candidate_id VARCHAR(64) REFERENCES quality_candidates(id) ON DELETE CASCADE,
        sample_count INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(24) NOT NULL DEFAULT 'queued',
        baseline_score INTEGER,
        candidate_score INTEGER,
        summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        error_message TEXT,
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_quality_experiments_owner_agent ON quality_experiments(owner_uid, agent_slug)",
    "CREATE INDEX IF NOT EXISTS ix_quality_experiments_status ON quality_experiments(status)",
    """
    CREATE TABLE IF NOT EXISTS quality_evaluation_results (
        id VARCHAR(64) PRIMARY KEY,
        experiment_id VARCHAR(64) NOT NULL REFERENCES quality_experiments(id) ON DELETE CASCADE,
        sample_id VARCHAR(64) NOT NULL REFERENCES quality_replay_samples(id) ON DELETE CASCADE,
        variant VARCHAR(16) NOT NULL,
        output_text TEXT,
        score INTEGER NOT NULL DEFAULT 0,
        judge_type VARCHAR(32) NOT NULL DEFAULT 'deterministic',
        judge_reason TEXT,
        run_id VARCHAR(64) REFERENCES agent_runs(id) ON DELETE SET NULL,
        duration_ms INTEGER,
        token_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_quality_result_variant UNIQUE(experiment_id, sample_id, variant)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_quality_results_experiment ON quality_evaluation_results(experiment_id)",
)

DOWNGRADE_STATEMENTS = (
    "DROP TABLE IF EXISTS quality_evaluation_results",
    "DROP TABLE IF EXISTS quality_experiments",
    "DROP TABLE IF EXISTS quality_candidates",
    "DROP TABLE IF EXISTS quality_replay_samples",
)


async def upgrade(connection) -> None:
    """按外键依赖顺序创建质量闭环表。"""
    for statement in UPGRADE_STATEMENTS:
        await connection.execute(text(statement))


async def downgrade(connection) -> None:
    """按外键依赖逆序删除质量闭环表。"""
    for statement in DOWNGRADE_STATEMENTS:
        await connection.execute(text(statement))
