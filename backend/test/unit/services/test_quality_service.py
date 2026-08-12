"""Agent 质量闭环服务的纯逻辑测试；本文件已编写但未运行。"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from yuxi.services.quality_service import (
    _apply_candidate_config,
    _normalize_candidate_config,
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
