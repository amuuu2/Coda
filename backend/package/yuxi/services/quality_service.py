"""Agent 质量评测闭环服务。"""

from __future__ import annotations

import copy
import time
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.repositories.agent_repository import AgentRepository, user_can_manage_agent
from yuxi.repositories.quality_repository import QualityRepository
from yuxi.agents.skills.service import list_accessible_skills
from yuxi.models.providers.cache import model_cache
from yuxi.services.agent_run_service import await_agent_run_result
from yuxi.services.input_message_service import build_chat_input_message
from yuxi.services.run_submission_service import RunOrigin, RunSubmissionCommand, submit_run_command
from yuxi.storage.postgres.models_business import Agent, AgentRun, Message, User
from yuxi.storage.postgres.models_quality import (
    QualityCandidate,
    QualityEvaluationResult,
    QualityExperiment,
    QualityReplaySample,
)
from yuxi.utils.datetime_utils import utc_now_naive
from yuxi.utils.hash_utils import hash_id


def deterministic_score(output: str | None, expected: str | None) -> tuple[int, str]:
    """用可审计的字符串匹配计算 MVP 基线分数。"""
    actual = (output or "").strip()
    target = (expected or "").strip()
    if not actual:
        return 0, "没有生成有效输出"
    if not target:
        return 100, "样本未提供期望答案，按成功生成计分"
    if actual == target:
        return 100, "输出与期望答案完全一致"
    if target in actual:
        return 70, "输出包含期望答案"
    return 20, "输出未包含期望答案"


def _normalize_candidate_config(config: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """校验候选字段白名单、类型和相对当前配置的实际变化。"""
    allowed_fields = {"system_prompt", "model_spec", "skill_slugs"}
    unknown_fields = set(config) - allowed_fields
    if unknown_fields:
        raise HTTPException(status_code=422, detail=f"候选配置包含不支持字段: {sorted(unknown_fields)}")

    normalized: dict[str, Any] = {}
    if "system_prompt" in config:
        prompt = config["system_prompt"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise HTTPException(status_code=422, detail="system_prompt 必须是非空字符串")
        normalized["system_prompt"] = prompt.strip()

    if "model_spec" in config:
        model_spec = config["model_spec"]
        if not isinstance(model_spec, str) or not model_spec.strip():
            raise HTTPException(status_code=422, detail="model_spec 必须是非空字符串")
        model_spec = model_spec.strip()
        model_info = model_cache.get_model_info(model_spec)
        if not model_info or model_info.model_type != "chat":
            raise HTTPException(status_code=422, detail="model_spec 不是当前可用的对话模型")
        normalized["model_spec"] = model_spec

    if "skill_slugs" in config:
        skill_slugs = config["skill_slugs"]
        if not isinstance(skill_slugs, list) or any(not isinstance(item, str) for item in skill_slugs):
            raise HTTPException(status_code=422, detail="skill_slugs 必须是字符串列表")
        normalized["skill_slugs"] = list(dict.fromkeys(item.strip() for item in skill_slugs if item.strip()))

    if not normalized:
        raise HTTPException(status_code=422, detail="请至少配置一项 Prompt、模型或 Skill 变更")
    if _apply_candidate_config(current, normalized) == current:
        raise HTTPException(status_code=422, detail="候选配置与当前智能体配置相同")
    return normalized


async def _get_agent(db: AsyncSession, agent_slug: str, user: User) -> Agent:
    """校验当前用户可访问目标 Agent。"""
    agent = await AgentRepository(db).get_visible_by_slug(slug=agent_slug, user=user, kind="main")
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在或无权访问")
    return agent


async def _get_managed_agent(db: AsyncSession, agent_slug: str, user: User) -> Agent:
    """校验当前用户具备 Agent 管理权限。"""
    agent = await _get_agent(db, agent_slug, user)
    if not user_can_manage_agent(user, agent):
        raise HTTPException(status_code=403, detail="需要智能体管理权限")
    return agent


async def publish_candidate(db: AsyncSession, user: User, candidate_id: str) -> QualityCandidate:
    """发布已审批候选，并保存可回滚的 Agent 配置快照。"""
    repo = QualityRepository(db)
    candidate = await repo.get_candidate(candidate_id, str(user.uid))
    if not candidate:
        raise HTTPException(status_code=404, detail="候选版本不存在")
    if candidate.status != "approved":
        raise HTTPException(status_code=409, detail="只有已审批候选可以发布")
    agent = await _get_managed_agent(db, candidate.agent_slug, user)
    candidate.previous_config_json = copy.deepcopy(agent.config_json or {})
    agent.config_json = _apply_candidate_config(agent.config_json or {}, candidate.config_json or {})
    agent.updated_by = str(user.uid)
    agent.updated_at = utc_now_naive()
    candidate.status = "published"
    candidate.published_at = utc_now_naive()
    published = await db.scalars(
        select(QualityCandidate).where(
            QualityCandidate.agent_slug == candidate.agent_slug,
            QualityCandidate.status == "published",
            QualityCandidate.id != candidate.id,
        )
    )
    for previous in published.all():
        previous.status = "superseded"
    await db.commit()
    await db.refresh(candidate)
    return candidate


async def rollback_candidate(db: AsyncSession, user: User, candidate_id: str) -> QualityCandidate:
    """把已发布候选回滚到其发布前 Agent 配置。"""
    candidate = await QualityRepository(db).get_candidate(candidate_id, str(user.uid))
    if not candidate:
        raise HTTPException(status_code=404, detail="候选版本不存在")
    if candidate.status != "published" or candidate.previous_config_json is None:
        raise HTTPException(status_code=409, detail="该候选没有可回滚的发布记录")
    agent = await _get_managed_agent(db, candidate.agent_slug, user)
    agent.config_json = copy.deepcopy(candidate.previous_config_json)
    agent.updated_by = str(user.uid)
    agent.updated_at = utc_now_naive()
    candidate.status = "rolled_back"
    await db.commit()
    await db.refresh(candidate)
    return candidate


def _apply_candidate_config(current: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """将候选字段映射回 Coda Agent context，并保留未参与评测的配置。"""
    updated = copy.deepcopy(current)
    context = dict(updated.get("context") or {})
    field_map = {"system_prompt": "system_prompt", "model_spec": "model", "skill_slugs": "skills"}
    for source, target in field_map.items():
        if source in candidate:
            context[target] = copy.deepcopy(candidate[source])
    updated["context"] = context
    return updated


async def add_replay_sample(
    db: AsyncSession, user: User, agent_slug: str, input_text: str, expected_output: str | None, source_run_id: str | None
) -> QualityReplaySample:
    """创建 Replay 样本，并可选地从用户自己的 AgentRun 复制基线结果。"""
    await _get_agent(db, agent_slug, user)
    if not input_text.strip():
        raise HTTPException(status_code=422, detail="输入不能为空")
    baseline = None
    if source_run_id:
        run = await db.scalar(select(AgentRun).where(AgentRun.id == source_run_id, AgentRun.uid == str(user.uid)))
        if not run or run.agent_slug != agent_slug:
            raise HTTPException(status_code=404, detail="运行记录不存在或不属于当前智能体")
        if run.output_message_id:
            message = await db.scalar(select(Message).where(Message.id == run.output_message_id))
            baseline = message.content if message else None
    sample = QualityReplaySample(
        id=str(uuid.uuid4()), owner_uid=str(user.uid), agent_slug=agent_slug, source_run_id=source_run_id,
        input_text=input_text.strip(), expected_output=expected_output, baseline_output=baseline,
    )
    db.add(sample)
    await db.commit()
    await db.refresh(sample)
    return sample


async def add_run_to_replay(
    db: AsyncSession, user: User, run_id: str, expected_output: str | None = None
) -> QualityReplaySample:
    """从当前用户的一次真实 AgentRun 自动提取输入和基线输出。"""
    run = await db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.uid == str(user.uid)))
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    input_message = await db.scalar(select(Message).where(Message.id == run.input_message_id))
    if not input_message or not input_message.content.strip():
        raise HTTPException(status_code=409, detail="运行记录缺少可回放输入")
    return await add_replay_sample(
        db, user, run.agent_slug, input_message.content, expected_output, run.id
    )


async def approve_candidate(db: AsyncSession, user: User, candidate_id: str) -> QualityCandidate:
    """审批候选版本，并在服务层重新校验 Agent 管理权限。"""
    candidate = await QualityRepository(db).get_candidate(candidate_id, str(user.uid))
    if not candidate:
        raise HTTPException(status_code=404, detail="候选版本不存在")
    await _get_managed_agent(db, candidate.agent_slug, user)
    if candidate.status != "draft":
        raise HTTPException(status_code=409, detail="只有草稿候选可以批准")
    if not await QualityRepository(db).has_completed_experiment(str(user.uid), candidate.id):
        raise HTTPException(status_code=409, detail="候选至少需要完成一次回放实验后才能批准")
    candidate.status = "approved"
    candidate.approved_by = str(user.uid)
    candidate.approved_at = utc_now_naive()
    await db.commit()
    await db.refresh(candidate)
    return candidate


async def create_candidate(db: AsyncSession, user: User, agent_slug: str, config: dict[str, Any], summary: str | None) -> QualityCandidate:
    """从当前 Agent 配置创建一个不可变候选版本。"""
    agent = await _get_managed_agent(db, agent_slug, user)
    repo = QualityRepository(db)
    candidate_config = _normalize_candidate_config(copy.deepcopy(config or {}), agent.config_json or {})
    if "skill_slugs" in candidate_config:
        accessible_slugs = {
            skill.slug for skill in await list_accessible_skills(db, user) if isinstance(skill.slug, str)
        }
        unknown_skills = set(candidate_config["skill_slugs"]) - accessible_slugs
        if unknown_skills:
            raise HTTPException(status_code=422, detail=f"Skill 不存在或无权访问: {sorted(unknown_skills)}")
    candidate = QualityCandidate(
        id=str(uuid.uuid4()), owner_uid=str(user.uid), agent_slug=agent_slug,
        version=await repo.next_candidate_version(agent_slug),
        config_json=candidate_config, change_summary=summary,
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    return candidate


async def create_experiment(db: AsyncSession, user: User, agent_slug: str, candidate_id: str | None) -> QualityExperiment:
    """创建一次回放实验；执行由显式 run 接口触发。"""
    await _get_managed_agent(db, agent_slug, user)
    repo = QualityRepository(db)
    samples = await repo.list_samples(str(user.uid), agent_slug)
    if not samples:
        raise HTTPException(status_code=422, detail="请先添加至少一条 Replay 样本")
    candidate = None
    if candidate_id:
        candidate = await repo.get_candidate(candidate_id, str(user.uid))
        if not candidate or candidate.agent_slug != agent_slug:
            raise HTTPException(status_code=404, detail="候选版本不存在")
    experiment = QualityExperiment(
        id=str(uuid.uuid4()), owner_uid=str(user.uid), agent_slug=agent_slug,
        candidate_id=candidate.id if candidate else None, sample_count=len(samples),
        summary_json={"sample_ids": [sample.id for sample in samples]},
    )
    db.add(experiment)
    await db.commit()
    await db.refresh(experiment)
    return experiment


async def run_experiment(db: AsyncSession, user: User, experiment_id: str) -> QualityExperiment:
    """回放样本到现有 AgentRun 队列并持久化基线与候选结果。"""
    repo = QualityRepository(db)
    experiment = await repo.get_experiment(experiment_id, str(user.uid))
    if not experiment:
        raise HTTPException(status_code=404, detail="评测实验不存在")
    await _get_managed_agent(db, experiment.agent_slug, user)
    if experiment.status != "queued":
        raise HTTPException(status_code=409, detail="只有排队中的实验可以执行")
    candidate = await repo.get_candidate(experiment.candidate_id, str(user.uid)) if experiment.candidate_id else None
    if experiment.candidate_id and not candidate:
        raise HTTPException(status_code=404, detail="候选版本不存在")
    sample_ids = list((experiment.summary_json or {}).get("sample_ids") or [])
    samples = await repo.list_samples_by_ids(str(user.uid), experiment.agent_slug, sample_ids)
    if len(samples) != experiment.sample_count:
        raise HTTPException(status_code=409, detail="实验样本已被删除或不可访问")
    experiment.status = "running"
    experiment.started_at = utc_now_naive()
    await db.commit()
    scores: dict[str, list[int]] = {"baseline": [], "candidate": []}
    try:
        for sample in samples:
            variants = [("baseline", None)]
            if candidate:
                variants.append(("candidate", candidate.config_json))
            for variant, config in variants:
                started = time.perf_counter()
                result = await _run_sample(db, user, experiment, sample, config)
                output = result.get("output")
                score, reason = deterministic_score(output, sample.expected_output)
                scores[variant].append(score)
                db.add(QualityEvaluationResult(
                    id=str(uuid.uuid4()), experiment_id=experiment.id, sample_id=sample.id,
                    variant=variant, output_text=output, score=score, judge_reason=reason,
                    run_id=result.get("agent_run_id"), duration_ms=int((time.perf_counter() - started) * 1000),
                ))
        experiment.baseline_score = _average(scores["baseline"])
        experiment.candidate_score = _average(scores["candidate"]) if candidate else None
        experiment.summary_json = {"sample_ids": sample_ids, "scores": scores, "delta": _delta(scores)}
        experiment.status = "completed"
    except Exception as exc:
        experiment.status = "failed"
        experiment.error_message = str(exc)
    finally:
        experiment.finished_at = utc_now_naive()
        await db.commit()
        await db.refresh(experiment)
    return experiment


async def _run_sample(db: AsyncSession, user: User, experiment: QualityExperiment, sample: QualityReplaySample, config: dict[str, Any] | None) -> dict[str, Any]:
    """通过既有 AgentRun 提交一次单样本回放。"""
    meta = {"quality_experiment_id": experiment.id, "quality_sample_id": sample.id}
    if config:
        meta["quality_candidate_config"] = config
    request_id = hash_id("quality:", f"{experiment.id}:{sample.id}:{'candidate' if config else 'baseline'}", length=64)
    variant = "candidate" if config else "baseline"
    query = sample.input_text
    system_prompt = str((config or {}).get("system_prompt") or "").strip()
    if system_prompt:
        query = f"[候选版本评测指令]\n{system_prompt}\n\n[用户输入]\n{query}"
    response = await submit_run_command(
        command=RunSubmissionCommand(
            agent_slug=experiment.agent_slug,
            thread_id=hash_id("quality_thread_", f"{user.uid}:{experiment.id}:{sample.id}:{variant}", length=64),
            request_id=request_id, input_message=build_chat_input_message(query),
            origin=RunOrigin(source="quality_replay", channel="api", external_id=request_id, metadata=meta),
            request_metadata={
                **meta,
                "skill_slugs": list((config or {}).get("skill_slugs") or []),
            },
            model_spec=(config or {}).get("model_spec") if config else None,
            queue_policy="reject", create_conversation=True, conversation_title="Quality Replay",
        ), current_user=user, db=db,
    )
    return await await_agent_run_result(run_id=response["run_id"], current_uid=str(user.uid))


def _average(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def _delta(scores: dict[str, list[int]]) -> int | None:
    if not scores["baseline"] or not scores["candidate"]:
        return None
    return (_average(scores["candidate"]) or 0) - (_average(scores["baseline"]) or 0)
