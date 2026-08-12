"""企业自动化中心：Cron 计算、幂等派发和 AgentRun 结果同步。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.repositories.enterprise_repository import EnterpriseRepository
from yuxi.services.agent_run_service import enqueue_agent_run
from yuxi.services.input_message_service import build_chat_input_message
from yuxi.services.run_submission_service import RunOrigin, RunSubmissionCommand, submit_run_command
from yuxi.storage.postgres.models_business import AgentRun, Message, User
from yuxi.storage.postgres.models_enterprise import ScheduledAgentRun, ScheduledAgentTask
from yuxi.utils.datetime_utils import utc_now_naive

SUPPORTED_OUTPUT_FORMATS = {"markdown", "html", "pdf"}
SCHEDULE_STATUSES = {"enabled", "disabled", "cancelled"}


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def calculate_next_run(cron_expression: str, timezone: str, base: datetime | None = None) -> datetime:
    """根据 Cron 和 IANA 时区计算下一次 UTC 执行时间。"""
    try:
        zone = ZoneInfo(timezone)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"不支持的时区: {timezone}") from exc

    base_local = (_as_utc(base) if base else _now_utc()).astimezone(zone)
    try:
        next_local = croniter(cron_expression, base_local).get_next(datetime)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"无效的 Cron 表达式: {cron_expression}") from exc
    return _as_utc(next_local)


def validate_schedule_payload(data: dict) -> None:
    """校验定时任务的最小业务约束。"""
    if not str(data.get("name") or "").strip():
        raise ValueError("任务名称不能为空")
    if not str(data.get("agent_slug") or "").strip():
        raise ValueError("必须选择 Agent")
    if not str(data.get("prompt") or "").strip():
        raise ValueError("提示词不能为空")
    if data.get("max_retries", 2) not in range(0, 4):
        raise ValueError("最大重试次数必须在 0 到 3 之间")
    if data.get("retry_backoff_seconds", 60) not in range(10, 3601):
        raise ValueError("重试退避必须在 10 到 3600 秒之间")
    output_format = (data.get("output_config") or {}).get("format", "markdown")
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"输出格式必须是: {', '.join(sorted(SUPPORTED_OUTPUT_FORMATS))}")
    calculate_next_run(data["cron_expression"], data.get("timezone") or "UTC")


def _request_id(schedule_id: str, planned_at: datetime) -> str:
    key = f"{schedule_id}:{_as_utc(planned_at).isoformat()}"
    return f"sched-{uuid.uuid5(uuid.NAMESPACE_URL, key)}"


def _thread_id(schedule_run_id: str) -> str:
    return f"scheduled-{schedule_run_id}"


async def create_schedule(db: AsyncSession, owner_uid: str, data: dict) -> ScheduledAgentTask:
    """创建任务并预计算下次执行时间。"""
    validate_schedule_payload(data)
    schedule = ScheduledAgentTask(
        id=str(uuid.uuid4()),
        owner_uid=str(owner_uid),
        name=str(data["name"]).strip(),
        description=data.get("description"),
        cron_expression=str(data["cron_expression"]).strip(),
        timezone=data.get("timezone") or "UTC",
        agent_slug=str(data["agent_slug"]).strip(),
        prompt=str(data["prompt"]).strip(),
        knowledge_base_ids=list(data.get("knowledge_base_ids") or []),
        skill_slugs=list(data.get("skill_slugs") or []),
        mcp_server_slugs=list(data.get("mcp_server_slugs") or []),
        model_spec=data.get("model_spec"),
        output_config=dict(data.get("output_config") or {"format": "markdown"}),
        status="enabled" if data.get("enabled", True) else "disabled",
        max_retries=int(data.get("max_retries", 2)),
        retry_backoff_seconds=int(data.get("retry_backoff_seconds", 60)),
    )
    schedule.next_run_at = (
        calculate_next_run(schedule.cron_expression, schedule.timezone) if schedule.status == "enabled" else None
    )
    await EnterpriseRepository(db).create_schedule(schedule)
    return schedule


def update_schedule(schedule: ScheduledAgentTask, data: dict) -> ScheduledAgentTask:
    """更新任务配置并重新计算下次执行时间。"""
    if schedule.status == "cancelled":
        raise ValueError("已取消的任务不能更新或重新启用")

    merged = {
        "name": data.get("name", schedule.name),
        "agent_slug": data.get("agent_slug", schedule.agent_slug),
        "prompt": data.get("prompt", schedule.prompt),
        "cron_expression": data.get("cron_expression", schedule.cron_expression),
        "timezone": data.get("timezone", schedule.timezone),
        "output_config": data.get("output_config", schedule.output_config or {}),
        "max_retries": data.get("max_retries", schedule.max_retries),
        "retry_backoff_seconds": data.get("retry_backoff_seconds", schedule.retry_backoff_seconds),
    }
    validate_schedule_payload(merged)
    for field in (
        "name",
        "description",
        "cron_expression",
        "timezone",
        "agent_slug",
        "prompt",
        "model_spec",
        "max_retries",
        "retry_backoff_seconds",
    ):
        if field in data:
            setattr(schedule, field, data[field])
    for field in ("knowledge_base_ids", "skill_slugs", "mcp_server_slugs"):
        if field in data:
            setattr(schedule, field, list(data[field] or []))
    if "output_config" in data:
        schedule.output_config = dict(data["output_config"] or {})
    if "enabled" in data:
        schedule.status = "enabled" if data["enabled"] else "disabled"
    schedule.next_run_at = (
        calculate_next_run(schedule.cron_expression, schedule.timezone) if schedule.status == "enabled" else None
    )
    schedule.updated_at = utc_now_naive()
    return schedule


async def dispatch_schedule_run(
    db: AsyncSession,
    schedule: ScheduledAgentTask,
    owner: User,
    *,
    planned_at: datetime | None = None,
    commit: bool = True,
    enqueue: bool = True,
) -> ScheduledAgentRun:
    """创建幂等的计划运行，并提交到现有 AgentRun 队列。"""
    if enqueue and not commit:
        raise ValueError("未提交计划运行前不能投递 AgentRun")
    if schedule.status != "enabled":
        raise ValueError("任务已暂停或取消，不能派发")

    is_scheduled_dispatch = planned_at is not None
    planned = _as_utc(planned_at or _now_utc())
    repo = EnterpriseRepository(db)
    existing = await repo.get_schedule_run_by_key(schedule.id, planned)
    if existing:
        return existing
    if await repo.get_active_schedule_run(schedule.id):
        raise ValueError("同一任务已有活跃运行")

    attempt = 0
    if is_scheduled_dispatch:
        previous = await repo.get_latest_schedule_run(schedule.id)
        if previous and previous.status == "failed" and previous.attempt > 0:
            next_regular_run = calculate_next_run(schedule.cron_expression, schedule.timezone, previous.planned_at)
            if planned < next_regular_run:
                attempt = previous.attempt

    schedule_run = ScheduledAgentRun(
        id=str(uuid.uuid4()),
        schedule_id=schedule.id,
        owner_uid=schedule.owner_uid,
        planned_at=planned,
        status="pending",
        attempt=attempt,
    )
    try:
        async with db.begin_nested():
            await repo.add_schedule_run(schedule_run)
            schedule.last_run_at = planned
            schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone, planned)
            now = _now_utc()
            while _as_utc(schedule.next_run_at) <= now:
                schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone, schedule.next_run_at)

            prompt = (
                f"{schedule.prompt}\n\n"
                "这是一次定时经营报告任务。请优先使用已授权的知识库、结构化抽取结果和只读数据分析工具，"
                f"按 {schedule.output_config.get('format', 'markdown')} 格式生成可交付报告；将最终文件写入 outputs 目录，"
                "并调用 present_artifacts 登记交付物，确保结果写入运行历史。"
            )
            input_message = build_chat_input_message(prompt).with_metadata(
                {
                    "source": "scheduled_report",
                    "schedule_id": schedule.id,
                    "scheduled_run_id": schedule_run.id,
                    "knowledge_base_ids": schedule.knowledge_base_ids or [],
                    "skill_slugs": schedule.skill_slugs or [],
                    "mcp_server_slugs": schedule.mcp_server_slugs or [],
                    "output_config": schedule.output_config or {},
                }
            )
            result = await submit_run_command(
                command=RunSubmissionCommand(
                    agent_slug=schedule.agent_slug,
                    thread_id=_thread_id(schedule_run.id),
                    request_id=_request_id(schedule.id, planned),
                    input_message=input_message,
                    origin=RunOrigin(
                        source="scheduled_report",
                        channel="scheduler",
                        external_id=schedule_run.id,
                        metadata={"schedule_id": schedule.id, "scheduled_run_id": schedule_run.id},
                    ),
                    request_metadata=input_message.extra_metadata,
                    model_spec=schedule.model_spec,
                    queue_policy="enqueue",
                    create_conversation=True,
                    conversation_title=schedule.name,
                ),
                current_user=owner,
                db=db,
                commit=False,
                enqueue=False,
            )
            schedule_run.agent_run_id = result.get("run_id")
            schedule_run.status = "pending" if result.get("status") in {"queued", "dispatched"} else result.get("status", "pending")
            await db.flush()
    except IntegrityError:
        existing = await repo.get_schedule_run_by_key(schedule.id, planned)
        if existing:
            return existing
        raise
    if commit:
        await db.commit()
    if enqueue and schedule_run.agent_run_id:
        await enqueue_agent_run(schedule_run.agent_run_id)
    return schedule_run


async def sync_scheduled_run(db: AsyncSession, agent_run: AgentRun) -> None:
    """把 AgentRun 终态同步到自动化中心运行历史。"""
    metadata = agent_run.origin_metadata if isinstance(agent_run.origin_metadata, dict) else {}
    schedule_run_id = metadata.get("scheduled_run_id")
    if not schedule_run_id:
        return

    result = await db.execute(select(ScheduledAgentRun).where(ScheduledAgentRun.id == schedule_run_id).with_for_update())
    schedule_run = result.scalar_one_or_none()
    if not schedule_run:
        return
    schedule_result = await db.execute(
        select(ScheduledAgentTask).where(ScheduledAgentTask.id == schedule_run.schedule_id).with_for_update()
    )
    schedule = schedule_result.scalar_one_or_none()
    if not schedule:
        return

    status_map = {"completed": "completed", "failed": "failed", "cancelled": "cancelled", "interrupted": "failed"}
    schedule_run.status = status_map.get(agent_run.status, agent_run.status)
    schedule_run.started_at = agent_run.started_at or schedule_run.started_at
    schedule_run.finished_at = agent_run.finished_at or utc_now_naive()
    if schedule_run.started_at and schedule_run.finished_at:
        schedule_run.duration_ms = max(
            0,
            int((schedule_run.finished_at - schedule_run.started_at).total_seconds() * 1000),
        )
    schedule_run.error_message = agent_run.error_message
    if (
        agent_run.status == "failed"
        and schedule.status == "enabled"
        and schedule_run.attempt < schedule.max_retries
    ):
        retry_attempt = schedule_run.attempt + 1
        schedule_run.attempt = retry_attempt
        backoff_seconds = schedule.retry_backoff_seconds * (2 ** (retry_attempt - 1))
        schedule.next_run_at = _now_utc() + timedelta(seconds=backoff_seconds)
    if agent_run.output_message_id:
        message_result = await db.execute(select(Message).where(Message.id == agent_run.output_message_id))
        message = message_result.scalar_one_or_none()
        if message and isinstance(message.extra_metadata, dict):
            schedule_run.artifacts = message.extra_metadata.get("artifacts") or []
            token_usage = message.extra_metadata.get("token_usage")
            if isinstance(token_usage, dict):
                schedule_run.input_tokens = token_usage.get("input_tokens") or token_usage.get("llm_input_tokens")
                schedule_run.output_tokens = token_usage.get("output_tokens")


async def sweep_scheduled_tasks() -> int:
    """扫描到期任务并派发最近一次计划，返回本次派发数量。"""
    from yuxi.storage.postgres.manager import pg_manager

    dispatched = 0
    run_ids: list[str] = []
    async with pg_manager.get_async_session_context() as db:
        repo = EnterpriseRepository(db)
        due_schedules = await repo.claim_due_schedules(_now_utc())
        for schedule in due_schedules:
            owner_result = await db.execute(select(User).where(User.uid == schedule.owner_uid, User.is_deleted == 0))
            owner = owner_result.scalar_one_or_none()
            if not owner or schedule.status != "enabled":
                if not owner:
                    schedule.status = "disabled"
                    schedule.next_run_at = None
                continue
            try:
                schedule_run = await dispatch_schedule_run(
                    db,
                    schedule,
                    owner,
                    planned_at=schedule.next_run_at,
                    commit=False,
                    enqueue=False,
                )
                dispatched += 1
                if schedule_run.agent_run_id:
                    run_ids.append(schedule_run.agent_run_id)
            except IntegrityError:
                continue
            except (ValueError, HTTPException):
                schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone)
    for run_id in run_ids:
        await enqueue_agent_run(run_id)
    return dispatched
