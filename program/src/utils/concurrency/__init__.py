from . import async_utils, process_pool, thread_pool

"""
Concurrency utilities package

This package bundles:
 - async_utils    : Structured asyncio helpers (logging, retries, rate-limiting, TaskHandle/TaskManager, …)
 - thread_pool    : ManagedThreadPool + ThreadPoolManager + convenience runners
 - process_pool   : ManagedProcessPool for CPU-bound workloads
"""

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
