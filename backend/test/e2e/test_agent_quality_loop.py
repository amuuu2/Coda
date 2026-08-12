"""Agent 质量闭环端到端验收骨架；依赖目标环境 Worker、Redis、PostgreSQL 和已配置模型，未运行。"""

import pytest


@pytest.mark.e2e
@pytest.mark.auth
async def test_agent_run_feedback_replay_experiment_publish_and_rollback(
    e2e_client, e2e_headers, e2e_agent_context
):
    """验证真实 AgentRun -> Replay -> 实验 -> 人工批准 -> 发布 -> 回滚链路。"""
    context = e2e_agent_context
    headers = e2e_headers
    thread_response = await e2e_client.post(
        "/api/chat/thread",
        headers=headers,
        json={"agent_id": context["agent_slug"], "title": "quality-loop-e2e"},
    )
    assert thread_response.status_code == 200, thread_response.text
    thread_id = str(thread_response.json().get("thread_id") or thread_response.json().get("id"))
    run_response = await e2e_client.post(
        "/api/agent/runs",
        headers=headers,
        json={"agent_slug": context["agent_slug"], "thread_id": thread_id, "query": "质量闭环验收问题"},
    )
    assert run_response.status_code in {200, 202}
    run_id = run_response.json()["run_id"]

    sample_response = await e2e_client.post(
        f"/api/agent-quality/runs/{run_id}/sample",
        headers=headers,
        json={"expected_output": "质量闭环验收"},
    )
    assert sample_response.status_code == 200

    candidate_response = await e2e_client.post(
        "/api/agent-quality/candidates",
        headers=headers,
        json={"agent_slug": context["agent_slug"], "config": {"system_prompt": "请明确给出证据和结论"}},
    )
    assert candidate_response.status_code == 200
    candidate_id = candidate_response.json()["candidate"]["id"]

    experiment_response = await e2e_client.post(
        "/api/agent-quality/experiments",
        headers=headers,
        json={"agent_slug": context["agent_slug"], "candidate_id": candidate_id},
    )
    assert experiment_response.status_code == 200
    experiment_id = experiment_response.json()["experiment"]["id"]

    run_experiment_response = await e2e_client.post(
        f"/api/agent-quality/experiments/{experiment_id}/run", headers=headers
    )
    assert run_experiment_response.status_code == 200
    assert run_experiment_response.json()["experiment"]["status"] == "completed"

    approve_response = await e2e_client.post(
        f"/api/agent-quality/candidates/{candidate_id}/approve", headers=headers
    )
    assert approve_response.status_code == 200
    publish_response = await e2e_client.post(
        f"/api/agent-quality/candidates/{candidate_id}/publish", headers=headers
    )
    assert publish_response.status_code == 200
    rollback_response = await e2e_client.post(
        f"/api/agent-quality/candidates/{candidate_id}/rollback", headers=headers
    )
    assert rollback_response.status_code == 200
