"""Agent 质量闭环服务的纯逻辑测试；本文件已编写但未运行。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from yuxi.services.quality_service import (
    _apply_candidate_config,
    _normalize_candidate_config,
    _run_sample,
    delete_experiment,
    deterministic_score,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("output", "expected", "score"),
    [(None, "答案", 0), ("回答", None, 100), ("答案", "答案", 100), ("前缀答案后缀", "答案", 70), ("其他", "答案", 20)],
)
def test_deterministic_score_is_auditable(output, expected, score):
    actual_score, reason = deterministic_score(output, expected)

    assert actual_score == score
    assert reason


def test_apply_candidate_config_preserves_unmanaged_context():
    current = {"context": {"system_prompt": "old", "temperature": 0.2}, "runtime": {"mode": "safe"}}

    updated = _apply_candidate_config(current, {"system_prompt": "new"})

    assert updated["context"] == {"system_prompt": "new", "temperature": 0.2}
    assert updated["runtime"] == {"mode": "safe"}
    assert current["context"]["system_prompt"] == "old"


def test_candidate_config_rejects_unknown_fields():
    with pytest.raises(HTTPException) as error:
        _normalize_candidate_config({"arbitrary": True}, {"context": {}})

    assert error.value.status_code == 422


def test_candidate_config_rejects_empty_changes():
    with pytest.raises(HTTPException) as error:
        _normalize_candidate_config({}, {"context": {}})

    assert error.value.status_code == 422


def test_candidate_config_requires_chat_model(monkeypatch):
    monkeypatch.setattr(
        "yuxi.services.quality_service.model_cache.get_model_info",
        lambda _spec: SimpleNamespace(model_type="embedding"),
    )

    with pytest.raises(HTTPException) as error:
        _normalize_candidate_config({"model_spec": "provider:embedding"}, {"context": {}})

    assert error.value.status_code == 422


def test_candidate_config_normalizes_skill_list():
    result = _normalize_candidate_config(
        {"skill_slugs": ["  knowledge-base ", "knowledge-base", ""]},
        {"context": {"skills": []}},
    )

    assert result == {"skill_slugs": ["knowledge-base"]}


@pytest.mark.asyncio
async def test_running_experiment_cannot_be_deleted(monkeypatch):
    """运行中的实验必须保留，避免 Worker 完成后回写到已删除记录。"""
    experiment = SimpleNamespace(id="experiment-1", agent_slug="default-chatbot", status="running")
    repo = SimpleNamespace(
        get_experiment=AsyncMock(return_value=experiment),
        delete_experiment=AsyncMock(),
    )
    monkeypatch.setattr("yuxi.services.quality_service.QualityRepository", lambda _db: repo)
    monkeypatch.setattr("yuxi.services.quality_service._get_managed_agent", AsyncMock())

    with pytest.raises(HTTPException) as error:
        await delete_experiment(object(), SimpleNamespace(uid="user-1"), experiment.id)

    assert error.value.status_code == 409
    repo.delete_experiment.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_sample_uses_path_safe_thread_id(monkeypatch):
    """质量回放线程 ID 只能包含现有运行链路允许的安全字符。"""
    captured = {}

    async def fake_submit_run_command(*, command, current_user, db):
        captured["thread_id"] = command.thread_id
        return {"run_id": "run-1"}

    async def fake_await_agent_run_result(*, run_id, current_uid):
        return {"agent_run_id": run_id, "output": "ok"}

    monkeypatch.setattr("yuxi.services.quality_service.submit_run_command", fake_submit_run_command)
    monkeypatch.setattr("yuxi.services.quality_service.await_agent_run_result", fake_await_agent_run_result)

    await _run_sample(
        db=object(),
        user=SimpleNamespace(uid="user-1"),
        experiment=SimpleNamespace(id="experiment-1", agent_slug="default-chatbot"),
        sample=SimpleNamespace(id="sample-1", input_text="test"),
        config=None,
    )

    assert captured["thread_id"].startswith("quality_thread_")
    assert captured["thread_id"].replace("_", "").isalnum()
