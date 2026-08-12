"""经营周报完整链路端到端场景。

当前电脑未运行此测试。目标部署电脑需准备 E2E_ANALYTICS_PASSWORD_ENV、
E2E_ANALYTICS_TABLE 和 E2E_EXTRACTION_FILE_ID 后显式设置 RUN_ENTERPRISE_REPORTING_E2E=1 执行。
"""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx
import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e, pytest.mark.slow]


@pytest.mark.skipif(
    os.getenv("RUN_ENTERPRISE_REPORTING_E2E") != "1",
    reason="设置 RUN_ENTERPRISE_REPORTING_E2E=1 后执行企业经营周报验收场景",
)
async def test_weekly_operating_report_flow(e2e_client: httpx.AsyncClient, e2e_headers, e2e_agent_context):
    password_env = os.getenv("E2E_ANALYTICS_PASSWORD_ENV")
    table_name = os.getenv("E2E_ANALYTICS_TABLE")
    file_id = os.getenv("E2E_EXTRACTION_FILE_ID")
    if not password_env or not table_name or not file_id:
        pytest.skip("未配置只读数据源密码环境变量、白名单表或已有知识文件 ID")

    qualified_table = table_name if "." in table_name else f"public.{table_name}"
    suffix = uuid.uuid4().hex[:8]
    source_id = None
    template_id = None
    schedule_id = None
    try:
        source_response = await e2e_client.post(
            "/api/analytics/data-sources",
            json={
                "name": f"weekly-report-{suffix}",
                "db_type": "postgresql",
                "host": os.getenv("E2E_ANALYTICS_HOST", "postgres"),
                "port": int(os.getenv("E2E_ANALYTICS_PORT", "5432")),
                "database_name": os.getenv("E2E_ANALYTICS_DATABASE", "coda"),
                "username": os.getenv("E2E_ANALYTICS_USERNAME", "readonly"),
                "password_env": password_env,
                "table_allowlist": [qualified_table],
            },
            headers=e2e_headers,
        )
        assert source_response.status_code == 200, source_response.text
        source_id = source_response.json()["data_source"]["id"]

        test_response = await e2e_client.post(
            f"/api/analytics/data-sources/{source_id}/test",
            headers=e2e_headers,
        )
        assert test_response.status_code == 200, test_response.text
        sync_response = await e2e_client.post(
            f"/api/analytics/data-sources/{source_id}/sync-schema",
            headers=e2e_headers,
        )
        assert sync_response.status_code == 200, sync_response.text

        template_response = await e2e_client.post(
            "/api/extraction/templates",
            json={
                "name": f"weekly-metrics-{suffix}",
                "schema_json": {
                    "type": "object",
                    "properties": {"revenue": {"type": "number"}, "orders": {"type": "number"}},
                    "required": ["revenue", "orders"],
                },
                "required_fields": ["revenue", "orders"],
                "prompt": "提取收入和订单数，并给出文件、页码或段落证据。",
            },
            headers=e2e_headers,
        )
        assert template_response.status_code == 200, template_response.text
        template_id = template_response.json()["template"]["id"]

        batch_response = await e2e_client.post(
            "/api/extraction/batches",
            json={"template_id": template_id, "file_ids": [file_id]},
            headers=e2e_headers,
        )
        assert batch_response.status_code == 200, batch_response.text
        batch_id = batch_response.json()["batch"]["id"]

        for _ in range(60):
            detail = await e2e_client.get(f"/api/extraction/batches/{batch_id}", headers=e2e_headers)
            assert detail.status_code == 200, detail.text
            status = detail.json()["batch"]["status"]
            if status in {"success", "completed_with_errors", "failed", "cancelled"}:
                break
            await asyncio.sleep(2)
        else:
            pytest.fail("文档抽取批次未在预期时间内结束")

        query_response = await e2e_client.post(
            "/api/analytics/queries",
            json={
                "data_source_id": source_id,
                "question": "分析最近一周的经营指标",
                "sql": f"SELECT * FROM {qualified_table} LIMIT 10",
            },
            headers=e2e_headers,
        )
        assert query_response.status_code == 200, query_response.text
        query_id = query_response.json()["query"]["id"]

        schedule_response = await e2e_client.post(
            "/api/automation/schedules",
            json={
                "name": f"经营周报-{suffix}",
                "cron_expression": "0 9 * * 1",
                "timezone": "Asia/Shanghai",
                "agent_slug": e2e_agent_context["agent_slug"],
                "prompt": (
                    f"读取抽取批次 {batch_id} 和查询记录 {query_id}，生成包含数据表、图表、结论和原文证据的经营周报。"
                ),
                "output_config": {"format": "markdown"},
            },
            headers=e2e_headers,
        )
        assert schedule_response.status_code == 200, schedule_response.text
        schedule_id = schedule_response.json()["schedule"]["id"]

        run_response = await e2e_client.post(
            f"/api/automation/schedules/{schedule_id}/run",
            headers=e2e_headers,
        )
        assert run_response.status_code == 200, run_response.text
        run_id = run_response.json()["run"]["id"]

        for _ in range(120):
            detail = await e2e_client.get(f"/api/automation/runs/{run_id}", headers=e2e_headers)
            assert detail.status_code == 200, detail.text
            run = detail.json()["run"]
            if run["status"] in {"completed", "failed", "cancelled"}:
                break
            await asyncio.sleep(2)
        else:
            pytest.fail("经营周报 AgentRun 未在预期时间内结束")

        assert run["status"] == "completed", run
        assert run.get("artifacts"), run
    finally:
        if schedule_id:
            await e2e_client.delete(f"/api/automation/schedules/{schedule_id}", headers=e2e_headers)
        if source_id:
            await e2e_client.delete(f"/api/analytics/data-sources/{source_id}", headers=e2e_headers)
