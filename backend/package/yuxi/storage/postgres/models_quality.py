"""Agent 质量评测闭环的数据模型。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

from yuxi.utils.datetime_utils import format_utc_datetime, utc_now_naive

QualityBase = declarative_base()


class QualityReplaySample(QualityBase):
    """保存可重复执行的 Agent 输入、期望和基线结果。"""

    __tablename__ = "quality_replay_samples"

    id = Column(String(64), primary_key=True)
    # 跨领域外键由显式 Migration 创建，避免独立 ORM MetaData 解析业务表失败。
    owner_uid = Column(String(64), nullable=False, index=True)
    agent_slug = Column(String(80), nullable=False, index=True)
    source_run_id = Column(String(64), nullable=True, index=True)
    input_text = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=True)
    baseline_output = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    status = Column(String(24), nullable=False, default="active", index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now_naive)
    updated_at = Column(DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "agent_slug": self.agent_slug,
            "source_run_id": self.source_run_id,
            "input_text": self.input_text,
            "expected_output": self.expected_output,
            "baseline_output": self.baseline_output,
            "metadata": self.metadata_json or {},
            "status": self.status,
            "created_at": format_utc_datetime(self.created_at),
            "updated_at": format_utc_datetime(self.updated_at),
        }


class QualityCandidate(QualityBase):
    """保存待评测、待审批或已发布的 Agent 配置快照。"""

    __tablename__ = "quality_candidates"

    id = Column(String(64), primary_key=True)
    owner_uid = Column(String(64), nullable=False, index=True)
    agent_slug = Column(String(80), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    config_json = Column(JSONB, nullable=False, default=dict)
    previous_config_json = Column(JSONB, nullable=True)
    status = Column(String(24), nullable=False, default="draft", index=True)
    change_summary = Column(Text, nullable=True)
    approved_by = Column(String(64), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now_naive)
    updated_at = Column(DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

    __table_args__ = (
        Index("uq_quality_candidates_agent_version", "agent_slug", "version", unique=True),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "agent_slug": self.agent_slug,
            "version": self.version,
            "config": self.config_json or {},
            "previous_config": self.previous_config_json,
            "status": self.status,
            "change_summary": self.change_summary,
            "approved_by": self.approved_by,
            "approved_at": format_utc_datetime(self.approved_at),
            "published_at": format_utc_datetime(self.published_at),
            "created_at": format_utc_datetime(self.created_at),
            "updated_at": format_utc_datetime(self.updated_at),
        }


class QualityExperiment(QualityBase):
    """记录一次基线与候选版本的回放实验。"""

    __tablename__ = "quality_experiments"

    id = Column(String(64), primary_key=True)
    owner_uid = Column(String(64), nullable=False, index=True)
    agent_slug = Column(String(80), nullable=False, index=True)
    candidate_id = Column(String(64), ForeignKey("quality_candidates.id", ondelete="CASCADE"), nullable=True)
    sample_count = Column(Integer, nullable=False, default=0)
    status = Column(String(24), nullable=False, default="queued", index=True)
    baseline_score = Column(Integer, nullable=True)
    candidate_score = Column(Integer, nullable=True)
    summary_json = Column(JSONB, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now_naive)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "agent_slug": self.agent_slug,
            "candidate_id": self.candidate_id,
            "sample_count": self.sample_count,
            "status": self.status,
            "baseline_score": self.baseline_score,
            "candidate_score": self.candidate_score,
            "summary": self.summary_json or {},
            "error_message": self.error_message,
            "started_at": format_utc_datetime(self.started_at),
            "finished_at": format_utc_datetime(self.finished_at),
            "created_at": format_utc_datetime(self.created_at),
        }


class QualityEvaluationResult(QualityBase):
    """保存实验中单条样本的输出、评分和解释。"""

    __tablename__ = "quality_evaluation_results"

    id = Column(String(64), primary_key=True)
    experiment_id = Column(String(64), ForeignKey("quality_experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    sample_id = Column(String(64), ForeignKey("quality_replay_samples.id", ondelete="CASCADE"), nullable=False, index=True)
    variant = Column(String(16), nullable=False)
    output_text = Column(Text, nullable=True)
    score = Column(Integer, nullable=False, default=0)
    judge_type = Column(String(32), nullable=False, default="deterministic")
    judge_reason = Column(Text, nullable=True)
    run_id = Column(String(64), nullable=True, index=True)
    duration_ms = Column(Integer, nullable=True)
    token_usage = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utc_now_naive)

    __table_args__ = (Index("uq_quality_result_variant", "experiment_id", "sample_id", "variant", unique=True),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "sample_id": self.sample_id,
            "variant": self.variant,
            "output": self.output_text,
            "score": self.score,
            "judge_type": self.judge_type,
            "judge_reason": self.judge_reason,
            "run_id": self.run_id,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage or {},
            "created_at": format_utc_datetime(self.created_at),
        }
