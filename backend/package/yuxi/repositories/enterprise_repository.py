"""企业报告平台的 PostgreSQL Repository。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_enterprise import (
    AnalyticsDataSource,
    AnalyticsQueryAudit,
    AnalyticsSchemaTable,
    ExtractionBatch,
    ExtractionResultRevision,
    ExtractionTask,
    ExtractionTemplate,
    ScheduledAgentRun,
    ScheduledAgentTask,
)


class EnterpriseRepository:
    """封装自动化、抽取和数据分析实体的可见性与持久化查询。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_schedules(self, owner_uid: str) -> list[ScheduledAgentTask]:
        result = await self.db.execute(
            select(ScheduledAgentTask)
            .where(ScheduledAgentTask.owner_uid == str(owner_uid))
            .order_by(ScheduledAgentTask.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_schedule(self, schedule_id: str, owner_uid: str, *, lock: bool = False) -> ScheduledAgentTask | None:
        query = select(ScheduledAgentTask).where(
            ScheduledAgentTask.id == schedule_id,
            ScheduledAgentTask.owner_uid == str(owner_uid),
        )
        if lock:
            query = query.with_for_update()
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_schedule(self, schedule: ScheduledAgentTask) -> ScheduledAgentTask:
        """新增定时任务并 flush，事务由调用方控制。"""
        self.db.add(schedule)
        await self.db.flush()
        return schedule

    async def delete_schedule(self, schedule: ScheduledAgentTask) -> None:
        await self.db.delete(schedule)
        await self.db.flush()

    async def list_schedule_runs(self, schedule_id: str, owner_uid: str, limit: int) -> list[ScheduledAgentRun]:
        result = await self.db.execute(
            select(ScheduledAgentRun)
            .where(
                ScheduledAgentRun.schedule_id == schedule_id,
                ScheduledAgentRun.owner_uid == str(owner_uid),
            )
            .order_by(ScheduledAgentRun.planned_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_schedule_run(self, run_id: str, owner_uid: str) -> ScheduledAgentRun | None:
        result = await self.db.execute(
            select(ScheduledAgentRun).where(
                ScheduledAgentRun.id == run_id,
                ScheduledAgentRun.owner_uid == str(owner_uid),
            )
        )
        return result.scalar_one_or_none()

    async def get_schedule_run_by_key(self, schedule_id: str, planned_at) -> ScheduledAgentRun | None:
        result = await self.db.execute(
            select(ScheduledAgentRun).where(
                ScheduledAgentRun.schedule_id == schedule_id,
                ScheduledAgentRun.planned_at == planned_at,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_schedule_run(self, schedule_id: str) -> ScheduledAgentRun | None:
        result = await self.db.execute(
            select(ScheduledAgentRun)
            .where(ScheduledAgentRun.schedule_id == schedule_id)
            .order_by(ScheduledAgentRun.planned_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_schedule_run(self, schedule_id: str) -> ScheduledAgentRun | None:
        result = await self.db.execute(
            select(ScheduledAgentRun)
            .where(
                ScheduledAgentRun.schedule_id == schedule_id,
                ScheduledAgentRun.status.in_(("pending", "running", "retry_waiting")),
            )
            .order_by(ScheduledAgentRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def claim_due_schedules(self, now, limit: int = 20) -> list[ScheduledAgentTask]:
        """锁定到期任务，供单个 scheduler tick 消费。"""
        result = await self.db.execute(
            select(ScheduledAgentTask)
            .where(
                ScheduledAgentTask.status == "enabled",
                ScheduledAgentTask.next_run_at.is_not(None),
                ScheduledAgentTask.next_run_at <= now,
            )
            .order_by(ScheduledAgentTask.next_run_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def add_schedule_run(self, run: ScheduledAgentRun) -> ScheduledAgentRun:
        self.db.add(run)
        await self.db.flush()
        return run

    async def list_templates(self, owner_uid: str) -> list[ExtractionTemplate]:
        result = await self.db.execute(
            select(ExtractionTemplate)
            .where(ExtractionTemplate.owner_uid == str(owner_uid))
            .order_by(ExtractionTemplate.name.asc(), ExtractionTemplate.version.desc())
        )
        return list(result.scalars().all())

    async def get_template(self, template_id: str, owner_uid: str) -> ExtractionTemplate | None:
        result = await self.db.execute(
            select(ExtractionTemplate).where(
                ExtractionTemplate.id == template_id,
                ExtractionTemplate.owner_uid == str(owner_uid),
            )
        )
        return result.scalar_one_or_none()

    async def get_batch(self, batch_id: str, owner_uid: str) -> ExtractionBatch | None:
        result = await self.db.execute(
            select(ExtractionBatch).where(
                ExtractionBatch.id == batch_id,
                ExtractionBatch.owner_uid == str(owner_uid),
            )
        )
        return result.scalar_one_or_none()

    async def list_batches(self, owner_uid: str) -> list[ExtractionBatch]:
        result = await self.db.execute(
            select(ExtractionBatch)
            .where(ExtractionBatch.owner_uid == str(owner_uid))
            .order_by(ExtractionBatch.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_extraction_task(self, task_id: str, owner_uid: str) -> ExtractionTask | None:
        result = await self.db.execute(
            select(ExtractionTask).where(
                ExtractionTask.id == task_id,
                ExtractionTask.owner_uid == str(owner_uid),
            )
        )
        return result.scalar_one_or_none()

    async def list_extraction_tasks(self, batch_id: str, owner_uid: str) -> list[ExtractionTask]:
        result = await self.db.execute(
            select(ExtractionTask)
            .where(
                ExtractionTask.batch_id == batch_id,
                ExtractionTask.owner_uid == str(owner_uid),
            )
            .order_by(ExtractionTask.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_revisions(self, task_id: str, owner_uid: str) -> list[ExtractionResultRevision]:
        result = await self.db.execute(
            select(ExtractionResultRevision)
            .where(
                ExtractionResultRevision.task_id == task_id,
                ExtractionResultRevision.owner_uid == str(owner_uid),
            )
            .order_by(ExtractionResultRevision.revision_no.desc())
        )
        return list(result.scalars().all())

    async def get_data_source(self, source_id: str, owner_uid: str) -> AnalyticsDataSource | None:
        result = await self.db.execute(
            select(AnalyticsDataSource).where(
                AnalyticsDataSource.id == source_id,
                AnalyticsDataSource.owner_uid == str(owner_uid),
            )
        )
        return result.scalar_one_or_none()

    async def list_data_sources(self, owner_uid: str) -> list[AnalyticsDataSource]:
        result = await self.db.execute(
            select(AnalyticsDataSource)
            .where(AnalyticsDataSource.owner_uid == str(owner_uid))
            .order_by(AnalyticsDataSource.name.asc())
        )
        return list(result.scalars().all())

    async def list_schema_tables(self, source_id: str, owner_uid: str) -> list[AnalyticsSchemaTable]:
        result = await self.db.execute(
            select(AnalyticsSchemaTable)
            .where(
                AnalyticsSchemaTable.data_source_id == source_id,
                AnalyticsSchemaTable.owner_uid == str(owner_uid),
            )
            .order_by(AnalyticsSchemaTable.schema_name.asc(), AnalyticsSchemaTable.table_name.asc())
        )
        return list(result.scalars().all())

    async def list_query_audits(self, owner_uid: str, limit: int) -> list[AnalyticsQueryAudit]:
        result = await self.db.execute(
            select(AnalyticsQueryAudit)
            .where(AnalyticsQueryAudit.owner_uid == str(owner_uid))
            .order_by(AnalyticsQueryAudit.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_query_audit(self, query_id: str, owner_uid: str) -> AnalyticsQueryAudit | None:
        result = await self.db.execute(
            select(AnalyticsQueryAudit).where(
                AnalyticsQueryAudit.id == query_id,
                AnalyticsQueryAudit.owner_uid == str(owner_uid),
            )
        )
        return result.scalar_one_or_none()
