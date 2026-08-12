"""受控数据分析核心规则测试。

当前电脑未运行这些测试；由目标部署电脑在依赖安装后执行。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from yuxi.services.enterprise_analytics_service import (
    _configured_table_names,
    _json_safe_rows,
    build_chart,
    update_data_source,
)


def test_json_safe_rows_converts_driver_values_for_jsonb():
    rows = _json_safe_rows(
        [
            {
                "amount": Decimal("12.50"),
                "count": Decimal("3"),
                "day": date(2026, 8, 11),
                "created_at": datetime(2026, 8, 11, 8, 30),
                "payload": b"ok",
            }
        ]
    )

    assert rows == [
        {
            "amount": 12.5,
            "count": 3,
            "day": "2026-08-11",
            "created_at": "2026-08-11T08:30:00",
            "payload": "ok",
        }
    ]


def test_build_chart_uses_dimension_and_numeric_metrics():
    chart = build_chart(
        ["week", "orders", "revenue"],
        [{"week": "2026-W32", "orders": 10, "revenue": 200.5}],
    )

    assert chart == {"type": "line", "dimension": "week", "metrics": ["orders", "revenue"]}


def test_update_data_source_preserves_existing_port_when_omitted():
    source = SimpleNamespace(
        name="warehouse",
        db_type="postgresql",
        host="db.internal",
        port=5432,
        database_name="metrics",
        username="reader",
        options={"sslmode": "require"},
        table_allowlist=["public.orders"],
        is_enabled=True,
        password_env="REPORT_DB_PASSWORD",
        password_ciphertext=None,
        updated_at=None,
    )

    update_data_source(source, {"name": "warehouse-prod"})

    assert source.name == "warehouse-prod"
    assert source.port == 5432
    assert source.password_env == "REPORT_DB_PASSWORD"


def test_update_data_source_updates_database_type():
    source = SimpleNamespace(
        name="warehouse",
        db_type="postgresql",
        host="db.internal",
        port=5432,
        database_name="metrics",
        username="reader",
        options={},
        table_allowlist=[],
        is_enabled=True,
        password_env="REPORT_DB_PASSWORD",
        password_ciphertext=None,
        updated_at=None,
    )

    update_data_source(source, {"db_type": "mysql"})

    assert source.db_type == "mysql"


def test_empty_table_allowlist_rejects_all_discovered_tables():
    discovered = [{"schema_name": "public", "table_name": "orders"}]

    assert _configured_table_names(discovered, set()) == set()


def test_short_table_name_only_allows_a_unique_schema_table():
    discovered = [
        {"schema_name": "public", "table_name": "orders"},
        {"schema_name": "archive", "table_name": "orders"},
        {"schema_name": "public", "table_name": "customers"},
    ]

    assert _configured_table_names(discovered, {"orders"}) == set()
    assert _configured_table_names(discovered, {"public.customers"}) == {"public.customers"}
