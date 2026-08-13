"""Agent 质量评测、Replay 与候选版本 API。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from yuxi.repositories.agent_repository import AgentRepository, user_can_manage_agent
from yuxi.repositories.quality_repository import QualityRepository
from yuxi.services.quality_service import (
    add_replay_sample,
    add_run_to_replay,
    approve_candidate as approve_candidate_service,
    create_candidate,
    create_experiment,
    delete_experiment,
    publish_candidate,
    rollback_candidate,
    run_experiment,
)
from yuxi.storage.postgres.models_business import User

quality_router = APIRouter(prefix="/agent-quality", tags=["agent-quality"])


class ReplaySamplePayload(BaseModel):
    """Replay 样本创建参数。"""

    agent_slug: str = Field(..., min_length=1, max_length=80)
    input_text: str = Field(..., min_length=1)
    expected_output: str | None = None
    source_run_id: str | None = Field(None, max_length=64)


class CandidatePayload(BaseModel):
    """候选版本创建参数。"""

    agent_slug: str = Field(..., min_length=1, max_length=80)
    config: dict[str, Any] = Field(default_factory=dict)
    change_summary: str | None = None


class ExperimentPayload(BaseModel):
    """离线实验创建参数。"""

    agent_slug: str = Field(..., min_length=1, max_length=80)
    candidate_id: str | None = None


class RunSamplePayload(BaseModel):
    """从 AgentRun 收集样本时的可选期望答案。"""

    expected_output: str | None = None


@quality_router.get("/agents")
async def list_managed_agents(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户可在质量闭环中管理的主智能体。"""
    repo = AgentRepository(db)
    await repo.ensure_default_agent()
    agents = await repo.list_visible(user=current_user)
    return {
        "agents": [
            {
                "id": agent.slug,
                "slug": agent.slug,
                "name": agent.name,
            }
            for agent in agents
            if user_can_manage_agent(current_user, agent)
        ]
    }


@quality_router.get("/samples")
async def list_samples(
    agent_slug: str = Query(..., min_length=1),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户在指定 Agent 下的 Replay 样本。"""
    items = await QualityRepository(db).list_samples(str(current_user.uid), agent_slug)
    return {"samples": [item.to_dict() for item in items]}


@quality_router.post("/samples")
async def create_sample(
    payload: ReplaySamplePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """添加手工样本或从已有 AgentRun 收集失败样本。"""
    item = await add_replay_sample(
        db, current_user, payload.agent_slug, payload.input_text, payload.expected_output, payload.source_run_id
    )
    return {"sample": item.to_dict()}


@quality_router.post("/runs/{run_id}/sample")
async def create_sample_from_run(
    run_id: str,
    payload: RunSamplePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """把当前用户的一次真实运行直接收集为 Replay 样本。"""
    item = await add_run_to_replay(db, current_user, run_id, payload.expected_output)
    return {"sample": item.to_dict()}


@quality_router.get("/candidates")
async def list_candidates(
    agent_slug: str = Query(..., min_length=1),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户创建的候选版本。"""
    items = await QualityRepository(db).list_candidates(str(current_user.uid), agent_slug)
    return {"candidates": [item.to_dict() for item in items]}


@quality_router.post("/candidates")
async def create_candidate_route(
    payload: CandidatePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新的 Prompt、模型和 Skill 快照候选。"""
    item = await create_candidate(db, current_user, payload.agent_slug, payload.config, payload.change_summary)
    return {"candidate": item.to_dict()}


@quality_router.post("/experiments")
async def create_experiment_route(
    payload: ExperimentPayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """创建待执行的回放实验。"""
    item = await create_experiment(db, current_user, payload.agent_slug, payload.candidate_id)
    return {"experiment": item.to_dict()}


@quality_router.get("/experiments")
async def list_experiments_route(
    agent_slug: str = Query(..., min_length=1),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户在指定 Agent 下的实验历史。"""
    items = await QualityRepository(db).list_experiments(str(current_user.uid), agent_slug)
    return {"experiments": [item.to_dict() for item in items]}


@quality_router.post("/experiments/{experiment_id}/run")
async def run_experiment_route(
    experiment_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """使用现有 AgentRun 队列执行回放实验。"""
    item = await run_experiment(db, current_user, experiment_id)
    return {"experiment": item.to_dict()}


@quality_router.get("/experiments/{experiment_id}")
async def get_experiment_route(
    experiment_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """读取实验摘要和逐样本 Judge 结果。"""
    repo = QualityRepository(db)
    item = await repo.get_experiment(experiment_id, str(current_user.uid))
    if not item:
        raise HTTPException(status_code=404, detail="评测实验不存在")
    results = await repo.list_results(experiment_id, str(current_user.uid))
    return {"experiment": item.to_dict(), "results": [result.to_dict() for result in results]}


@quality_router.delete("/experiments/{experiment_id}")
async def delete_experiment_route(
    experiment_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """删除当前用户拥有的实验历史和逐样本结果。"""
    await delete_experiment(db, current_user, experiment_id)
    return {"message": "实验记录已删除"}


@quality_router.post("/candidates/{candidate_id}/approve")
async def approve_candidate(
    candidate_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """人工批准候选版本，但不直接修改生产 Agent。"""
    item = await approve_candidate_service(db, current_user, candidate_id)
    return {"candidate": item.to_dict()}


@quality_router.post("/candidates/{candidate_id}/publish")
async def publish_candidate_route(
    candidate_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """发布已审批候选到 Agent 当前配置。"""
    item = await publish_candidate(db, current_user, candidate_id)
    return {"candidate": item.to_dict()}


@quality_router.post("/candidates/{candidate_id}/rollback")
async def rollback_candidate_route(
    candidate_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """回滚一次已发布的候选版本。"""
    item = await rollback_candidate(db, current_user, candidate_id)
    return {"candidate": item.to_dict()}
