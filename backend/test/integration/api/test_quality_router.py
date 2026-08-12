"""质量闭环 API 的认证、租户隔离和状态流测试；本文件已编写但未运行。"""

import pytest


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

