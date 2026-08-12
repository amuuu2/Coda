"""Agent 质量闭环的数据访问。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_quality import (
    QualityCandidate,
    QualityEvaluationResult,
    QualityExperiment,
    QualityReplaySample,
)


class QualityRepository:
    """集中执行质量资源的用户范围查询。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_samples(self, uid: str, agent_slug: str, limit: int = 100) -> list[QualityReplaySample]:
        result = await self.db.execute(
            select(QualityReplaySample)
            .where(QualityReplaySample.owner_uid == str(uid), QualityReplaySample.agent_slug == agent_slug)
            .order_by(QualityReplaySample.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_sample(self, sample_id: str, uid: str) -> QualityReplaySample | None:
        result = await self.db.execute(
            select(QualityReplaySample).where(
                QualityReplaySample.id == sample_id, QualityReplaySample.owner_uid == str(uid)
            )
        )
        return result.scalar_one_or_none()

    async def list_samples_by_ids(
        self, uid: str, agent_slug: str, sample_ids: list[str]
    ) -> list[QualityReplaySample]:
        """按实验冻结的 ID 顺序读取当前用户样本。"""
        if not sample_ids:
            return []
        result = await self.db.execute(
            select(QualityReplaySample).where(
                QualityReplaySample.id.in_(sample_ids),
                QualityReplaySample.owner_uid == str(uid),
                QualityReplaySample.agent_slug == agent_slug,
            )
        )
        samples_by_id = {item.id: item for item in result.scalars().all()}
        return [samples_by_id[sample_id] for sample_id in sample_ids if sample_id in samples_by_id]

    async def list_candidates(self, uid: str, agent_slug: str) -> list[QualityCandidate]:
        result = await self.db.execute(
            select(QualityCandidate)
            .where(QualityCandidate.owner_uid == str(uid), QualityCandidate.agent_slug == agent_slug)
            .order_by(QualityCandidate.version.desc())
        )
        return list(result.scalars().all())

    async def get_candidate(self, candidate_id: str, uid: str) -> QualityCandidate | None:
        result = await self.db.execute(
            select(QualityCandidate).where(
                QualityCandidate.id == candidate_id, QualityCandidate.owner_uid == str(uid)
            )
        )
        return result.scalar_one_or_none()

    async def next_candidate_version(self, agent_slug: str) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(QualityCandidate.version), 0)).where(
                QualityCandidate.agent_slug == agent_slug
            )
        )
        return int(result.scalar_one()) + 1

    async def get_experiment(self, experiment_id: str, uid: str) -> QualityExperiment | None:
        result = await self.db.execute(
            select(QualityExperiment).where(
                QualityExperiment.id == experiment_id, QualityExperiment.owner_uid == str(uid)
            )
        )
        return result.scalar_one_or_none()

    async def list_experiments(self, uid: str, agent_slug: str, limit: int = 50) -> list[QualityExperiment]:
        """按时间倒序列出用户自己的实验历史。"""
        result = await self.db.execute(
            select(QualityExperiment)
            .where(QualityExperiment.owner_uid == str(uid), QualityExperiment.agent_slug == agent_slug)
            .order_by(QualityExperiment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def has_completed_experiment(self, uid: str, candidate_id: str) -> bool:
        """判断候选是否已有当前用户完成的回放证据。"""
        result = await self.db.execute(
            select(QualityExperiment.id).where(
                QualityExperiment.owner_uid == str(uid),
                QualityExperiment.candidate_id == candidate_id,
                QualityExperiment.status == "completed",
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_results(self, experiment_id: str, uid: str) -> list[QualityEvaluationResult]:
        result = await self.db.execute(
            select(QualityEvaluationResult)
            .join(QualityExperiment, QualityExperiment.id == QualityEvaluationResult.experiment_id)
            .where(
                QualityEvaluationResult.experiment_id == experiment_id,
                QualityExperiment.owner_uid == str(uid),
            )
            .order_by(QualityEvaluationResult.sample_id, QualityEvaluationResult.variant)
        )
        return list(result.scalars().all())

    async def add(self, entity: Any) -> Any:
        self.db.add(entity)
        await self.db.flush()
        return entity
