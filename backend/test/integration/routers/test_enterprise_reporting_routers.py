"""企业报告平台路由集成测试。

当前电脑未运行这些测试；目标部署电脑必须先完成 Migration 并启动 API/Worker。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_enterprise_routes_require_authentication(test_client):
    for path in ("/api/automation/schedules", "/api/extraction/templates", "/api/analytics/data-sources"):
        response = await test_client.get(path)
        assert response.status_code == 401, (path, response.text)


async def test_authenticated_user_can_read_enterprise_centers(test_client, admin_headers):
    checks = [
        ("/api/automation/schedules", "schedules"),
        ("/api/extraction/templates", "templates"),
        ("/api/extraction/batches", "batches"),
        ("/api/analytics/data-sources", "data_sources"),
        ("/api/analytics/queries", "queries"),
    ]
    for path, key in checks:
        response = await test_client.get(path, headers=admin_headers)
        assert response.status_code == 200, (path, response.text)
        assert isinstance(response.json().get(key), list)
