"""
Concurrency utilities package

This package bundles:
 - async_utils    : Structured asyncio helpers (logging, retries, rate-limiting, TaskHandle/TaskManager, …)
 - thread_pool    : ManagedThreadPool + ThreadPoolManager + convenience runners
 - process_pool   : ManagedProcessPool for CPU-bound workloads
"""

from . import async_utils, process_pool, thread_pool

import sys
module = sys.modules[__name__]
sys.modules.setdefault("src.utils.concurrency", module)
sys.modules.setdefault("src.utils.concurrency.async_utils", async_utils)
sys.modules.setdefault("src.utils.concurrency.process_pool", process_pool)
sys.modules.setdefault("src.utils.concurrency.thread_pool", thread_pool)

# expose the three submodules

# re-export most-used names at package level
from .async_utils import (
    setup_logging,
    AsyncRateLimiter,
    AsyncTaskManager,
    TaskHandle,
    gather_with_concurrency,
    run_with_timeout,
    retry_async,
    run_in_executor,
    install_signal_handlers,
)

from .process_pool import (
    ProcessPoolType,
    ProcessPoolConfig,
    ManagedProcessPool,
    ProcessPoolManager,
    get_process_pool_manager,
)

from .thread_pool import (
    ThreadPoolType,
    ThreadPoolConfig,
    ManagedThreadPool,
    ThreadPoolManager,
    get_thread_pool_manager,
    run_sensor_io,
    run_camera_io,
    run_file_io,
    run_network_io,
    thread_pool_context,
)

__all__ = [
    # async_utils
    "setup_logging",
    "AsyncRateLimiter",
    "AsyncTaskManager",
    "TaskHandle",
    "gather_with_concurrency",
    "run_with_timeout",
    "retry_async",
    "run_in_executor",
    "install_signal_handlers",
    # process_pool
    "ProcessPoolType",
    "ProcessPoolConfig",
    "ManagedProcessPool",
    "ProcessPoolManager",
    "get_process_pool_manager",
    # thread_pool
    "ThreadPoolType",
    "ThreadPoolConfig",
    "ManagedThreadPool",
    "ThreadPoolManager",
    "get_thread_pool_manager",
    "run_sensor_io",
    "run_camera_io",
    "run_file_io",
    "run_network_io",
    "thread_pool_context",
    # submodules
    "async_utils",
    "process_pool",
    "thread_pool",
]
