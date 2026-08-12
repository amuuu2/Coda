"""在目标部署环境显式执行 Agent 质量闭环 Migration。"""

import argparse
import asyncio
import importlib

from yuxi.storage.postgres.manager import pg_manager

MIGRATION_MODULE = "migrations.versions.20260812_agent_quality_loop"


async def run(direction: str) -> None:
    """在一个事务内执行升级或回滚，失败时由事务自动回滚。"""
    pg_manager.initialize()
    pg_manager._check_initialized()
    try:
        migration = importlib.import_module(MIGRATION_MODULE)
        operation = migration.upgrade if direction == "upgrade" else migration.downgrade
        async with pg_manager.async_engine.begin() as connection:
            await operation(connection)
    finally:
        await pg_manager.close()


def main() -> int:
    """解析命令行参数并执行 Migration。"""
    parser = argparse.ArgumentParser(description="Agent quality loop migration")
    parser.add_argument("direction", choices=("upgrade", "downgrade"))
    args = parser.parse_args()
    asyncio.run(run(args.direction))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
