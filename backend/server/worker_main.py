"""ARQ worker entrypoint.

WorkerSettings also registers the enterprise reporting jobs: scheduled Agent
runs and structured document extraction continue through the existing ARQ
worker instead of introducing a second execution engine.
"""

import asyncio
import os
import sys

# 必须放在最顶层！
if sys.platform == "win32":
    # 把当前文件 (main.py) 的上一级的上一级（即项目根目录）加入到 sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from yuxi.services.run_worker import WorkerSettings

__all__ = ["WorkerSettings"]
