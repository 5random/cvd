"""
Process-pool utilities – v3.1 (2025-06-03)

Changelog
---------
* Einzelner Timeout zerstört den Pool nur noch, wenn
  `kill_on_timeout=True`.
* `scale_workers` verhindert Umskalieren bei laufenden Tasks,
  außer `force_shutdown=True`.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import os
import signal
import threading
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from src.utils.log_service import info, warning


class ProcessPoolType(Enum):
    DEFAULT = "default"
    CPU = "cpu"
    ML = "ml"


@dataclass
class ProcessPoolConfig:
    max_workers: int | None = None
    timeout: float | None = None
    kill_on_timeout: bool = False
    kill_signal: int = signal.SIGTERM


@dataclass
class _Telemetry:
    submitted: int = 0
    finished: int = 0
    failed: int = 0
    cancelled: int = 0
    timed_out: int = 0
    active: int = 0
    total_wall_time: float = 0.0

    def inc(self, field: str) -> None:
        setattr(self, field, getattr(self, field) + 1)


class ManagedProcessPool:
    def __init__(
        self,
        config: ProcessPoolConfig,
        pool_type: ProcessPoolType = ProcessPoolType.DEFAULT,
    ) -> None:
        self.config = config
        self.pool_type = pool_type
        self._max_workers = config.max_workers or (mp.cpu_count() or 1)
        self._executor: ProcessPoolExecutor | None = None
        self._lock = threading.Lock()
        self._closed = False
        self._telemetry = _Telemetry()
        self._telemetry_lock = threading.Lock()

    # ───────── Submission ─────────
    def submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        if self._closed:
            raise RuntimeError("Pool closed")
        if self._executor is None:
            self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        with self._telemetry_lock:
            self._telemetry.inc("submitted")
            self._telemetry.active += 1
        fut = self._executor.submit(func, *args, **kwargs)
        fut.add_done_callback(self._on_done)
        return fut

    async def submit_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        fut = self.submit(func, *args, **kwargs)
        wrapped: asyncio.Future[Any] = asyncio.wrap_future(fut)
        try:
            if self.config.timeout is not None:
                return await asyncio.wait_for(wrapped, timeout=self.config.timeout)
            return await wrapped
        except asyncio.TimeoutError:
            with self._telemetry_lock:
                self._telemetry.inc("timed_out")
            warning(f"Task {func.__name__!s} timed out after {self.config.timeout}s")
            fut.cancel()
            if self.config.kill_on_timeout:
                self._kill_children(sig=self.config.kill_signal)
                self._terminate_executor()
            raise
        except asyncio.CancelledError:
            with self._telemetry_lock:
                self._telemetry.inc("cancelled")
            fut.cancel()
            # Pool bleibt bestehen
            raise

    # ───────── Scaling ─────────
    def scale_workers(self, max_workers: int, *, force_shutdown: bool = False) -> None:
        new_max = max(1, min(max_workers, mp.cpu_count()))
        with self._lock:
            if self._telemetry.active and not force_shutdown:
                warning(
                    "scale_skipped_active_jobs",
                    active=self._telemetry.active,
                    requested=new_max,
                )
                return
            self._max_workers = new_max
            old_exec, self._executor = self._executor, None
        if old_exec:
            old_exec.shutdown(wait=not force_shutdown, cancel_futures=force_shutdown)
            info("pool_scaled", new_max=new_max, force=force_shutdown)

    # ───────── Helpers / Shutdown ─────────
    def _on_done(self, fut: Future) -> None:
        with self._telemetry_lock:
            self._telemetry.active -= 1
            if fut.cancelled():
                self._telemetry.inc("cancelled")
            elif fut.exception():
                self._telemetry.inc("failed")
            else:
                self._telemetry.inc("finished")

    def _terminate_executor(self) -> None:
        with self._lock:
            exec_, self._executor = self._executor, None
        if exec_:
            exec_.shutdown(cancel_futures=True)

    def _kill_children(self, *, sig: int = signal.SIGTERM) -> None:
        if self._executor is None:
            return
        for p in self._executor._processes.values():
            pid = getattr(p, "pid", None)
            if pid is None:
                continue
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                continue

    def shutdown(self, wait: bool = True) -> None:
        self._closed = True
        self._terminate_executor()


class ProcessPoolManager:
    """Singleton-style manager for :class:`ManagedProcessPool` instances."""

    _defaults: dict[ProcessPoolType, ProcessPoolConfig] = {
        ProcessPoolType.DEFAULT: ProcessPoolConfig(),
        ProcessPoolType.CPU: ProcessPoolConfig(),
        ProcessPoolType.ML: ProcessPoolConfig(),
    }

    def __init__(self) -> None:
        self._pools: dict[ProcessPoolType, ManagedProcessPool] = {}
        self._refcounts: dict[ProcessPoolType, int] = {}
        self._lock = threading.Lock()

    def get_pool(
        self, pool_type: ProcessPoolType, *, config: ProcessPoolConfig | None = None
    ) -> ManagedProcessPool:
        with self._lock:
            if pool_type not in self._pools:
                cfg = config or self._defaults.get(pool_type, ProcessPoolConfig())
                self._pools[pool_type] = ManagedProcessPool(cfg, pool_type=pool_type)
                self._refcounts[pool_type] = 1
            else:
                self._refcounts[pool_type] += 1
            return self._pools[pool_type]

    def release_pool(self, pool_type: ProcessPoolType, *, wait: bool = True) -> None:
        with self._lock:
            if pool_type not in self._pools:
                return
            self._refcounts[pool_type] -= 1
            if self._refcounts[pool_type] > 0:
                return
            pool = self._pools.pop(pool_type)
            self._refcounts.pop(pool_type, None)
        pool.shutdown(wait=wait)

    async def submit_to_pool(
        self,
        pool_type: ProcessPoolType,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        pool = self.get_pool(pool_type)
        return await pool.submit_async(fn, *args, **kwargs)

    async def shutdown_all(self) -> None:
        with self._lock:
            pools = list(self._pools.items())
            self._pools.clear()
            self._refcounts.clear()
        await asyncio.gather(
            *(asyncio.to_thread(pool.shutdown) for _, pool in pools)
        )


_global_mgr: ProcessPoolManager | None = None
_mgr_lock = threading.Lock()


def get_process_pool_manager() -> ProcessPoolManager:
    """Return global :class:`ProcessPoolManager` instance."""
    global _global_mgr
    if _global_mgr is None:
        with _mgr_lock:
            if _global_mgr is None:
                _global_mgr = ProcessPoolManager()
    return _global_mgr


__all__ = [
    "ProcessPoolType",
    "ProcessPoolConfig",
    "ManagedProcessPool",
    "ProcessPoolManager",
    "get_process_pool_manager",
]
