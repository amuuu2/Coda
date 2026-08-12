"""自动化中心 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.agents.buildin import agent_manager
from yuxi.agents.context import normalize_agent_context_config
from server.utils.auth_middleware import get_db, get_required_user
from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.enterprise_repository import EnterpriseRepository
from yuxi.services.enterprise_automation_service import (
    create_schedule,
    dispatch_schedule_run,
    update_schedule,
)
from yuxi.storage.postgres.models_business import User

automation_router = APIRouter(prefix="/automation", tags=["automation"])


class SchedulePayload(BaseModel):
    """自动化任务写入参数。"""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    cron_expression: str = Field(min_length=1, max_length=128)
    timezone: str = "UTC"
    agent_slug: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    skill_slugs: list[str] = Field(default_factory=list)
    mcp_server_slugs: list[str] = Field(default_factory=list)
    model_spec: str | None = None
    output_config: dict[str, Any] = Field(default_factory=lambda: {"format": "markdown"})
    enabled: bool = True
    max_retries: int = Field(default=2, ge=0, le=3)
    retry_backoff_seconds: int = Field(default=60, ge=10, le=3600)


async def _ensure_agent_access(db: AsyncSession, user: User, agent_slug: str):
    agent = await AgentRepository(db).get_visible_by_slug(slug=agent_slug, user=user, kind="main")
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在或不可访问")
    return agent


async def _ensure_resource_access(db: AsyncSession, user: User, payload: SchedulePayload) -> None:
    """在保存任务前校验其知识库、Skills 和 MCP 资源归属。"""
    agent = await _ensure_agent_access(db, user, payload.agent_slug)
    backend = agent_manager.get_agent(agent.backend_id)
    if not backend:
        raise HTTPException(status_code=404, detail="智能体后端不存在")

    requested = {
        "knowledges": {str(item).strip() for item in payload.knowledge_base_ids if str(item).strip()},
        "skills": {str(item).strip() for item in payload.skill_slugs if str(item).strip()},
        "mcps": {str(item).strip() for item in payload.mcp_server_slugs if str(item).strip()},
    }
    normalized = await normalize_agent_context_config(
        {field: list(values) for field, values in requested.items()},
        db=db,
        user=user,
        context_schema=backend.context_schema,
    )
    for field, values in requested.items():
        if values and not values.issubset(set(normalized.get(field) or [])):
            raise HTTPException(status_code=422, detail=f"任务包含当前用户无权访问的 {field} 资源")


def _raise_validation(exc: ValueError) -> None:
    detail = exc.args[0] if exc.args else str(exc)
    raise HTTPException(status_code=422, detail=detail) from exc


@automation_router.get("/schedules")
async def list_schedules(current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)):
    """列出当前用户拥有的自动化任务。"""
    schedules = await EnterpriseRepository(db).list_schedules(str(current_user.uid))
    return {"schedules": [schedule.to_dict() for schedule in schedules]}


@automation_router.post("/schedules")
async def create_schedule_route(
    payload: SchedulePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_resource_access(db, current_user, payload)
    try:
        schedule = await create_schedule(db, str(current_user.uid), payload.model_dump())
    except ValueError as exc:
        _raise_validation(exc)
    return {"schedule": schedule.to_dict()}


@automation_router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await EnterpriseRepository(db).get_schedule(schedule_id, str(current_user.uid))
    if not schedule:
        raise HTTPException(status_code=404, detail="自动化任务不存在")
    runs = await EnterpriseRepository(db).list_schedule_runs(schedule.id, str(current_user.uid), 20)
    return {"schedule": schedule.to_dict(), "runs": [run.to_dict() for run in runs]}


@automation_router.put("/schedules/{schedule_id}")
async def update_schedule_route(
    schedule_id: str,
    payload: SchedulePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    repo = EnterpriseRepository(db)
    schedule = await repo.get_schedule(schedule_id, str(current_user.uid))
    if not schedule:
        raise HTTPException(status_code=404, detail="自动化任务不存在")
    await _ensure_resource_access(db, current_user, payload)
    try:
        schedule = update_schedule(schedule, payload.model_dump())
    except ValueError as exc:
        _raise_validation(exc)
    return {"schedule": schedule.to_dict()}


@automation_router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    repo = EnterpriseRepository(db)
    schedule = await repo.get_schedule(schedule_id, str(current_user.uid))
    if not schedule:
        raise HTTPException(status_code=404, detail="自动化任务不存在")
    schedule.status = "cancelled"
    schedule.next_run_at = None
    await db.commit()
    return {"success": True}


@automation_router.post("/schedules/{schedule_id}/enable")
async def enable_schedule(
    schedule_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await _set_schedule_status(schedule_id, "enabled", current_user, db)


@automation_router.post("/schedules/{schedule_id}/disable")
async def disable_schedule(
    schedule_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await _set_schedule_status(schedule_id, "disabled", current_user, db)


async def _set_schedule_status(schedule_id: str, status: str, user: User, db: AsyncSession) -> dict:
    """设置任务启停状态并清理暂停任务的下一次派发时间。"""
    schedule = await EnterpriseRepository(db).get_schedule(schedule_id, str(user.uid))
    if not schedule:
        raise HTTPException(status_code=404, detail="自动化任务不存在")
    if status == "enabled" and schedule.status == "cancelled":
        raise HTTPException(status_code=409, detail="已取消的任务不能重新启用")
    schedule.status = status
    if status != "enabled":
        schedule.next_run_at = None
    else:
        from yuxi.services.enterprise_automation_service import calculate_next_run

        schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone)
    await db.commit()
    return {"schedule": schedule.to_dict()}


@automation_router.post("/schedules/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await EnterpriseRepository(db).get_schedule(schedule_id, str(current_user.uid))
    if not schedule:
        raise HTTPException(status_code=404, detail="自动化任务不存在")
    try:
        run = await dispatch_schedule_run(db, schedule, current_user)
    except ValueError as exc:
        _raise_validation(exc)
    return {"run": run.to_dict()}


@automation_router.get("/schedules/{schedule_id}/runs")
async def list_schedule_runs(
    schedule_id: str,
    limit: int = 50,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    schedule = await EnterpriseRepository(db).get_schedule(schedule_id, str(current_user.uid))
    if not schedule:
        raise HTTPException(status_code=404, detail="自动化任务不存在")
    runs = await EnterpriseRepository(db).list_schedule_runs(schedule_id, str(current_user.uid), limit)
    return {"runs": [run.to_dict() for run in runs]}


@automation_router.get("/runs/{run_id}")
async def get_schedule_run(
    run_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    run = await EnterpriseRepository(db).get_schedule_run(run_id, str(current_user.uid))
    if not run:
        raise HTTPException(status_code=404, detail="自动化运行记录不存在")
    return {"run": run.to_dict()}
