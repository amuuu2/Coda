"""执行企业报告平台的显式数据库 Migration。"""

from __future__ import annotations

import asyncio
import importlib
import sys

from yuxi.storage.postgres.manager import pg_manager

MIGRATION_MODULE = "migrations.versions.20260811_enterprise_reporting"


async def run(direction: str) -> None:
    """在现有 PostgreSQL 连接上执行升级或回滚。"""
    if direction not in {"upgrade", "downgrade"}:
        raise ValueError("方向必须是 upgrade 或 downgrade")

    migration = importlib.import_module(MIGRATION_MODULE)
    pg_manager.initialize()
    try:
        async with pg_manager.async_engine.begin() as connection:
            await getattr(migration, direction)(connection)
    finally:
        await pg_manager.close()


def main() -> int:
    """解析命令行参数并执行 Migration。"""
    if len(sys.argv) != 2:
        print("用法: python scripts/run_enterprise_migrations.py upgrade|downgrade", file=sys.stderr)
        return 2
    asyncio.run(run(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
