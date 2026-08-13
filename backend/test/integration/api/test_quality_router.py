"""质量闭环 API 的认证、租户隔离和状态流测试；本文件已编写但未运行。"""

import pytest


@pytest.mark.integration
@pytest.mark.auth
async def test_quality_agent_list_only_returns_managed_main_agents(test_client, admin_headers):
    response = await test_client.get("/api/agent-quality/agents", headers=admin_headers)
    all_agents_response = await test_client.get(
        "/api/agent?include_subagents=true", headers=admin_headers
    )

    assert response.status_code == 200
    assert all_agents_response.status_code == 200
    agents = response.json()["agents"]
    expected_slugs = {
        agent["slug"]
        for agent in all_agents_response.json()["agents"]
        if agent["can_manage"] and not agent["is_subagent"]
    }
    assert {agent["slug"] for agent in agents} == expected_slugs
    assert all(set(agent) == {"id", "slug", "name"} for agent in agents)


@pytest.mark.integration
@pytest.mark.auth
async def test_quality_routes_require_authentication(test_client):
    response = await test_client.get("/api/agent-quality/samples?agent_slug=default-chatbot")

    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.auth
async def test_quality_sample_is_not_visible_across_users(test_client, admin_headers, standard_user):
    create_response = await test_client.post(
        "/api/agent-quality/samples",
        headers=admin_headers,
        json={"agent_slug": "default-chatbot", "input_text": "隔离样本"},
    )
    assert create_response.status_code == 200

    list_response = await test_client.get(
        "/api/agent-quality/samples?agent_slug=default-chatbot",
        headers=standard_user["headers"],
    )

    assert list_response.status_code == 200
    assert all(item["id"] != create_response.json()["sample"]["id"] for item in list_response.json()["samples"])


@pytest.mark.integration
@pytest.mark.auth
async def test_candidate_requires_replay_before_approval(test_client, admin_headers):
    create_response = await test_client.post(
        "/api/agent-quality/candidates",
        headers=admin_headers,
        json={"agent_slug": "default-chatbot", "config": {"system_prompt": "质量候选提示词"}},
    )
    assert create_response.status_code == 200
    candidate_id = create_response.json()["candidate"]["id"]

    approve_response = await test_client.post(
        f"/api/agent-quality/candidates/{candidate_id}/approve", headers=admin_headers
    )

    assert approve_response.status_code == 409


@pytest.mark.integration
@pytest.mark.auth
async def test_quality_experiment_delete_is_owner_scoped(test_client, admin_headers, standard_user):
    sample_response = await test_client.post(
        "/api/agent-quality/samples",
        headers=admin_headers,
        json={"agent_slug": "default-chatbot", "input_text": "待删除实验样本"},
    )
    assert sample_response.status_code == 200
    experiment_response = await test_client.post(
        "/api/agent-quality/experiments",
        headers=admin_headers,
        json={"agent_slug": "default-chatbot"},
    )
    assert experiment_response.status_code == 200
    experiment_id = experiment_response.json()["experiment"]["id"]

    forbidden_response = await test_client.delete(
        f"/api/agent-quality/experiments/{experiment_id}",
        headers=standard_user["headers"],
    )
    assert forbidden_response.status_code == 404

    delete_response = await test_client.delete(
        f"/api/agent-quality/experiments/{experiment_id}", headers=admin_headers
    )
    assert delete_response.status_code == 200
    detail_response = await test_client.get(
        f"/api/agent-quality/experiments/{experiment_id}", headers=admin_headers
    )
    assert detail_response.status_code == 404
