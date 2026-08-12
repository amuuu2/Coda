"""SQL AST 安全门禁测试。

当前电脑未运行这些测试；由目标部署电脑在依赖安装后执行。
"""

from __future__ import annotations

import pytest

from yuxi.services.sql_guard import validate_read_only_sql


def test_validate_read_only_sql_accepts_select_and_cte():
    result = validate_read_only_sql(
        "WITH weekly AS (SELECT region, SUM(amount) AS total FROM public.orders GROUP BY region) "
        "SELECT * FROM weekly",
        dialect="postgres",
        allowed_tables={"public.orders"},
    )

    assert result.tables == ("public.orders",)
    assert "public.orders" in result.sql.lower()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM public.orders; SELECT 1",
        "DELETE FROM public.orders",
        "SELECT pg_sleep(1) FROM public.orders",
        "SELECT * FROM other_db.public.orders",
        "SELECT * FROM private.orders",
    ],
)
def test_validate_read_only_sql_rejects_unsafe_or_unlisted_sql(sql: str):
    with pytest.raises(ValueError):
        validate_read_only_sql(sql, dialect="postgres", allowed_tables={"public.orders"})


def test_validate_read_only_sql_rejects_select_into():
    with pytest.raises(ValueError, match="SELECT INTO"):
        validate_read_only_sql(
            "SELECT * INTO public.copy_orders FROM public.orders",
            dialect="postgres",
            allowed_tables={"public.orders"},
        )


def test_validate_read_only_sql_accepts_unique_short_table_name():
    result = validate_read_only_sql(
        "SELECT * FROM orders",
        dialect="postgres",
        allowed_tables={"orders"},
    )

    assert result.tables == ("orders",)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM public.orders FOR UPDATE",
        "SELECT GET_LOCK('report', 1) FROM public.orders",
        "SELECT pg_advisory_lock(1) FROM public.orders",
    ],
)
def test_validate_read_only_sql_rejects_locks_and_dangerous_functions(sql: str):
    with pytest.raises(ValueError):
        validate_read_only_sql(sql, dialect="postgres", allowed_tables={"public.orders"})
