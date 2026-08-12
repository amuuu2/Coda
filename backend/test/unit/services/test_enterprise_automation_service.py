"""定时 Agent 任务核心规则测试。

当前电脑未运行这些测试；由目标部署电脑在依赖安装后执行。
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from yuxi.services.enterprise_automation_service import (
    calculate_next_run,
    update_schedule,
    validate_schedule_payload,
)


def test_calculate_next_run_converts_local_cron_to_utc():
    result = calculate_next_run(
        "0 9 * * 1",
        "Asia/Shanghai",
        datetime(2026, 8, 9, 1, 0, tzinfo=UTC),
    )

    assert result == datetime(2026, 8, 10, 1, 0, tzinfo=UTC)


def test_validate_schedule_payload_rejects_unsupported_output_format():
    with pytest.raises(ValueError, match="输出格式"):
        validate_schedule_payload(
            {
                "name": "经营周报",
                "agent_slug": "report-agent",
                "prompt": "生成周报",
                "cron_expression": "0 9 * * 1",
                "output_config": {"format": "docx"},
            }
        )


def test_validate_schedule_payload_accepts_retry_bounds_and_timezone():
    validate_schedule_payload(
        {
            "name": "经营周报",
            "agent_slug": "report-agent",
            "prompt": "生成周报",
            "cron_expression": "0 9 * * 1",
            "timezone": "Asia/Shanghai",
            "max_retries": 3,
            "retry_backoff_seconds": 3600,
            "output_config": {"format": "markdown"},
        }
    )


def test_cancelled_schedule_cannot_be_updated_or_reenabled():
    with pytest.raises(ValueError, match="已取消"):
        update_schedule(SimpleNamespace(status="cancelled"), {})
