"""
Improved thread-pool utilities – v2.5 (2025-06-03)

Changelog
---------
* **Slot-Leak behoben**: Semaphore wird bei Submit-Fehlern freigegeben.
* **Thread-sichere Executor-Initialisierung** mittels `self._lock`.
* **Circuit-Breaker Hysterese**: +1 s `hysteresis_seconds`.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import contextmanager
import inspect
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor, CancelledError
from dataclasses import dataclass
from enum import Enum
from threading import BoundedSemaphore, Lock
from types import TracebackType
from typing import Any, Callable, Dict, Optional, Set, TypeVar

from src.utils.log_service import debug, error, info, warning

# ───────────────────────────── optional dependencies ─────────────────────────
try:
    from opentelemetry import trace  # type: ignore

    _tracer = trace.get_tracer("cvd_tracker.thread_pool")
except Exception:  # pragma: no cover
    _tracer = None  # type: ignore

try:
    from prometheus_client import Counter, Gauge, CollectorRegistry  # type: ignore

    _metrics_registry = CollectorRegistry()
    _M_SUBMITTED = Counter(
        "cvd_pool_tasks_submitted_total",
        "Tasks submitted",
        ["pool"],
        registry=_metrics_registry,
    )
    _M_COMPLETED = Counter(
        "cvd_pool_tasks_completed_total",
        "Tasks completed",
        ["pool"],
        registry=_metrics_registry,
    )
    _M_FAILED = Counter(
        "cvd_pool_tasks_failed_total",
        "Tasks failed",
        ["pool"],
        registry=_metrics_registry,
    )
    _M_ACTIVE = Gauge(
        "cvd_pool_active_tasks",
        "Tasks currently executing",
        ["pool"],
        registry=_metrics_registry,
    )
except Exception:  # pragma: no cover
    Counter = Gauge = CollectorRegistry = None  # type: ignore
    _metrics_registry = None  # type: ignore
    _M_SUBMITTED = _M_COMPLETED = _M_FAILED = _M_ACTIVE = None  # type: ignore


# ────────────────────────────────── helpers ──────────────────────────────────
class SecurityError(RuntimeError):
    """Raised when a callable violates sandbox rules."""


T = TypeVar("T")


class ThreadPoolType(str, Enum):
    SENSOR_IO = "sensor_io"
    CAMERA_IO = "camera_io"
    FILE_IO = "file_io"
    NETWORK_IO = "network_io"
    GENERAL = "general"


@dataclass(slots=True)
class ThreadPoolConfig:
    # Performance
    max_workers: int | None = None
    cpu_factor: float = 4.0
    queue_maxsize: int | None = None
    queue_block: bool = True
    nice: int | None = None

    # Timeouts / Robustness
    timeout: float | None = None
    shutdown_timeout: float | None = 30.0
    retries: int = 0
    retry_backoff_base: float = 0.5
    retry_backoff_max: float = 5.0
    circuit_breaker_failures: int | None = None
    circuit_breaker_reset_timeout: float | None = 60.0
    hysteresis_seconds: float = 1.0  # NEU: Verzögerung für Circuit-Breaker Hysterese

    # Observability
    enable_tracing: bool = False
    enable_metrics: bool = False

    # Security
    allowed_modules: Optional[Set[str]] = None  # {"src.sensors", ...}
    allowed_callables: Optional[Set[str]] = None  # {"module.func", ...}
    deny_cpu_bound: bool = False  # simple heuristic

    # Misc
    thread_name_prefix: str = "CVDTracker"
    pool_type: ThreadPoolType = ThreadPoolType.GENERAL


@dataclass(slots=True)
class _PoolStats:
    tasks_submitted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    active_tasks: int = 0
    rejected_tasks: int = 0
    retries_performed: int = 0
    cb_open_events: int = 0
    sandbox_violations: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


# ─────────────────────────────── managed pool ────────────────────────────────
class ManagedThreadPool:
    """Thread-pool mit Back-Pressure, Robustness, Observability **und** Sandbox."""

    # ── construction ──
    def __init__(self, cfg: ThreadPoolConfig):
        self.config = cfg
        self.pool_type = cfg.pool_type

        self._workers = self._calc_workers(cfg)
        # lazy init der Semaphore für Back-Pressure
        self._sema: BoundedSemaphore | None = None
        self._executor: ThreadPoolExecutor | None = None
        # Lock für thread-sichere Executor-Init
        self._lock = Lock()
        self._shutdown = False

        # Stats and task tracking
        self._stats = _PoolStats()
        self._stats_lock = Lock()
        self._futures: Dict[str, Future[Any]] = {}

        # Circuit-Breaker
        self._cb_failures = 0
        self._cb_open_until: float | None = None
        self._cb_lock = Lock()

        # Observability handles
        self._tracer = _tracer if (cfg.enable_tracing and _tracer) else None
        # only enable metrics if the Gauge object _M_ACTIVE is present
        self._metrics_enabled = bool(cfg.enable_metrics and _M_ACTIVE)
        if self._metrics_enabled and _M_ACTIVE:
            _M_ACTIVE.labels(pool=self.pool_type.value).set(0)

    # ── helper static ──
    @staticmethod
    def _calc_workers(cfg: ThreadPoolConfig) -> int:
        if cfg.max_workers:
            return max(1, cfg.max_workers)
        cpu_cnt = os.cpu_count() or 4
        return max(1, int(cpu_cnt * cfg.cpu_factor))

    def _ensure_executor(self) -> ThreadPoolExecutor:
        # thread-sichere Initialisierung des Executors
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=self._workers,
                    thread_name_prefix=f"{self.config.thread_name_prefix}-{self.pool_type.value}",
                )
                debug(
                    "executor_created", pool=self.pool_type.value, workers=self._workers
                )
        return self._executor

    # ── sandbox checks ──
    def _check_callable_security(self, fn: Callable[..., Any]) -> None:
        full_name = f"{fn.__module__}.{fn.__qualname__}"
        if (
            self.config.allowed_callables
            and full_name not in self.config.allowed_callables
        ):
            raise SecurityError(f"Callable '{full_name}' not allowed")
        if (
            self.config.allowed_modules
            and fn.__module__ not in self.config.allowed_modules
        ):
            raise SecurityError(f"Module '{fn.__module__}' not allowed")
        if self.config.deny_cpu_bound:
            sig = inspect.signature(fn)
            for p in sig.parameters.values():
                ann = p.annotation
                if getattr(ann, "__module__", "").startswith(("numpy", "pandas")):
                    raise SecurityError("CPU-bound operation denied by pool policy")

    # ── slot helpers ──
    def _acquire_slot(self) -> None:
        # lazy init der Semaphore für Back-Pressure
        if self._sema is None:
            maxsize = (
                self.config.queue_maxsize
                if self.config.queue_maxsize is not None
                else self._workers
            )
            self._sema = BoundedSemaphore(maxsize)
        if not self._sema.acquire(blocking=self.config.queue_block):
            # bei voller Queue Fehler auslösen
            raise RuntimeError("Thread-pool queue full")

    def _release_slot(self) -> None:
        # sichere Freigabe der Semaphore
        if self._sema:
            with contextlib.suppress(ValueError):
                self._sema.release()

    # ── circuit-breaker helpers ──
    def _circuit_ok(self) -> bool:
        if self.config.circuit_breaker_failures is None:
            return True
        with self._cb_lock:
            return not (self._cb_open_until and time.time() < self._cb_open_until)

    def _record_failure(self) -> None:
        if self.config.circuit_breaker_failures is None:
            return
        with self._cb_lock:
            self._cb_failures += 1
            if self._cb_failures >= self.config.circuit_breaker_failures:
                # Verlängerte Öffnungszeit mit Hysterese
                self._cb_open_until = (
                    time.time()
                    + (self.config.circuit_breaker_reset_timeout or 0)
                    + self.config.hysteresis_seconds
                )
                self._cb_failures = 0
                with self._stats_lock:
                    self._stats.cb_open_events += 1
                warning("circuit_breaker_open", pool=self.pool_type.value)

    def _record_success(self) -> None:
        if self.config.circuit_breaker_failures is None:
            return
        with self._cb_lock:
            self._cb_failures = 0

    # ── retry wrapper ──
    def _wrap_retry(self, fn: Callable[..., T]) -> Callable[..., T]:
        if self.config.retries <= 0:
            return fn

        retries, base, backoff_max = (
            self.config.retries,
            self.config.retry_backoff_base,
            self.config.retry_backoff_max,
        )
        stats = self._stats

        def _inner(*a: Any, **kw: Any):
            attempt, delay = 0, base
            while True:
                try:
                    return fn(*a, **kw)
                except Exception as exc:  # noqa: BLE001
                    attempt += 1
                    if attempt > retries:
                        raise
                    with self._stats_lock:
                        stats.retries_performed += 1
                    sleep_for = min(delay, backoff_max)
                    warning(
                        "retry",
                        pool=self.pool_type.value,
                        attempt=attempt,
                        sleep=sleep_for,
                        exc=str(exc),
                    )
                    time.sleep(sleep_for)
                    delay *= 2

        return _inner

    # ── submission ──
    def submit_task(
        self,
        fn: Callable[..., T],
        *args: Any,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> Future[T]:
        if self._shutdown:
            raise RuntimeError("Pool closed")
        if not self._circuit_ok():
            raise RuntimeError("Circuit breaker open – task rejected")

        # Sandbox
        try:
            self._check_callable_security(fn)
        except SecurityError as se:
            with self._stats_lock:
                self._stats.sandbox_violations += 1
            error("sandbox_violation", pool=self.pool_type.value, msg=str(se))
            raise

        # Back-Pressure
        self._acquire_slot()

        # Metrics pre-increment
        if self._metrics_enabled and _M_SUBMITTED and _M_ACTIVE:
            _M_SUBMITTED.labels(pool=self.pool_type.value).inc()
            _M_ACTIVE.labels(pool=self.pool_type.value).inc()

        # Compose wrapper (retry, nice)
        target: Callable[..., T] = self._wrap_retry(fn)

        if self.config.nice is not None:

            def _with_nice(*a: Any, **kw: Any):
                try:
                    if hasattr(os, "nice"):
                        assert self.config.nice is not None
                        os.nice(self.config.nice)  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover
                    pass
                return target(*a, **kw)

            target = _with_nice

        # Actual submission
        with (
            self._tracer.start_as_current_span(
                "threadpool.submit",
                attributes={"pool": self.pool_type.value, "task_id": task_id or ""},
            )
            if self._tracer
            else contextlib.nullcontext()
        ):
            # --- FIX: Slot-Leak absichern -------------------------
            try:
                fut: Future[T] = self._ensure_executor().submit(target, *args, **kwargs)
            except Exception:  # noqa: BLE001
                self._release_slot()
                raise

        self._register_future(fut, task_id)
        debug("task_submitted", pool=self.pool_type.value, task_id=task_id)
        return fut

    async def submit_async(
        self,
        fn: Callable[..., T],
        *args: Any,
        task_id: str | None = None,
        deadline: float | None = None,
        **kwargs: Any,
    ) -> T:
        loop = asyncio.get_running_loop()
        fut = self.submit_task(fn, *args, task_id=task_id, **kwargs)
        wrapped = asyncio.wrap_future(fut, loop=loop)
        timeout = self.config.timeout
        if deadline is not None:
            remaining = deadline - time.time()
            timeout = remaining if timeout is None else max(0, min(timeout, remaining))
        try:
            return await asyncio.wait_for(wrapped, timeout=timeout)
        except asyncio.TimeoutError:
            fut.cancel()
            error("task_timeout", pool=self.pool_type.value, task_id=task_id)
            raise

    # ── bookkeeping ──
    def _register_future(self, fut: Future[Any], task_id: str | None) -> None:
        with self._stats_lock:
            self._stats.tasks_submitted += 1
            self._stats.active_tasks += 1
        if task_id:
            self._futures[task_id] = fut

        # callbacks
        def _done(res: Future[Any]):
            try:
                exc = res.exception()
            except CancelledError:
                # Future was cancelled, treat as no exception
                exc = None
            with self._stats_lock:
                self._stats.active_tasks -= 1
                if exc:
                    self._stats.tasks_failed += 1
                else:
                    self._stats.tasks_completed += 1
            if exc:
                self._record_failure()
                if self._metrics_enabled and _M_FAILED:
                    _M_FAILED.labels(pool=self.pool_type.value).inc()
            else:
                self._record_success()
                if self._metrics_enabled and _M_COMPLETED:
                    _M_COMPLETED.labels(pool=self.pool_type.value).inc()
            if self._metrics_enabled and _M_ACTIVE:
                _M_ACTIVE.labels(pool=self.pool_type.value).dec()
            self._release_slot()

        fut.add_done_callback(_done)

    # ── public helpers ──
    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            fut = self._futures.get(task_id)
        if not fut:
            return False
        cancelled = fut.cancel()
        if cancelled:
            debug("task_cancelled", pool=self.pool_type.value, task_id=task_id)
        return cancelled

    def get_stats(self) -> Dict[str, Any]:
        d = self._stats.as_dict()
        d["pool_type"] = self.pool_type.value
        d["max_workers"] = self._workers
        return d

    def shutdown(self, *, wait: bool = True) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        if self._metrics_enabled and _M_ACTIVE:
            _M_ACTIVE.labels(pool=self.pool_type.value).set(0)
        if self._executor:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        info("pool_shutdown", pool=self.pool_type.value)

    # context-manager sugar
    def __enter__(self):
        self._ensure_executor()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ):
        self.shutdown()


# ───────────────────────────── manager + helpers ─────────────────────────────
class ThreadPoolManager:
    """Singleton-Orchestrator für mehrere ManagedThreadPools."""

    _defaults: Dict[ThreadPoolType, ThreadPoolConfig] = {
        ThreadPoolType.SENSOR_IO: ThreadPoolConfig(
            pool_type=ThreadPoolType.SENSOR_IO, cpu_factor=2.0
        ),
        ThreadPoolType.CAMERA_IO: ThreadPoolConfig(
            pool_type=ThreadPoolType.CAMERA_IO,
            max_workers=1,
            cpu_factor=2.0,
        ),
        ThreadPoolType.FILE_IO: ThreadPoolConfig(
            pool_type=ThreadPoolType.FILE_IO, cpu_factor=3.0
        ),
        ThreadPoolType.NETWORK_IO: ThreadPoolConfig(
            pool_type=ThreadPoolType.NETWORK_IO, cpu_factor=4.0
        ),
        ThreadPoolType.GENERAL: ThreadPoolConfig(
            pool_type=ThreadPoolType.GENERAL, cpu_factor=4.0
        ),
    }

    def __init__(self) -> None:
        self._pools: Dict[ThreadPoolType, ManagedThreadPool] = {}
        self._lock = Lock()

    def set_default_max_workers(self, workers: int) -> None:
        """Set ``max_workers`` for all default configs without one."""
        workers = max(1, workers)
        for cfg in self._defaults.values():
            if cfg.max_workers is None:
                cfg.max_workers = workers

    def get_pool(
        self, pool_type: ThreadPoolType, *, config: ThreadPoolConfig | None = None
    ) -> ManagedThreadPool:
        with self._lock:
            if pool_type not in self._pools:
                cfg = config or self._defaults[pool_type]
                self._pools[pool_type] = ManagedThreadPool(cfg)
            return self._pools[pool_type]

    async def submit_to_pool(
        self,
        pool_type: ThreadPoolType,
        fn: Callable[..., T],
        *args: Any,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> T:
        pool = self.get_pool(pool_type)
        return await pool.submit_async(fn, *args, task_id=task_id, **kwargs)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        return {pt.value: pool.get_stats() for pt, pool in self._pools.items()}

    async def shutdown_all(self) -> None:
        await asyncio.gather(
            *(asyncio.to_thread(pool.shutdown) for pool in self._pools.values())
        )
        self._pools.clear()


# ───────────────────── global singleton & convenience helpers ────────────────

_global_mgr: ThreadPoolManager | None = None
_mgr_lock = Lock()


def get_thread_pool_manager(default_max_workers: int | None = None) -> ThreadPoolManager:
    """Return global :class:`ThreadPoolManager` and apply defaults."""
    global _global_mgr
    if _global_mgr is None:
        with _mgr_lock:
            if _global_mgr is None:
                _global_mgr = ThreadPoolManager()
    if default_max_workers is not None:
        _global_mgr.set_default_max_workers(default_max_workers)
    return _global_mgr


async def run_sensor_io(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    return await get_thread_pool_manager().submit_to_pool(
        ThreadPoolType.SENSOR_IO, fn, *args, **kwargs
    )


async def run_camera_io(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    return await get_thread_pool_manager().submit_to_pool(
        ThreadPoolType.CAMERA_IO, fn, *args, **kwargs
    )


async def run_file_io(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    return await get_thread_pool_manager().submit_to_pool(
        ThreadPoolType.FILE_IO, fn, *args, **kwargs
    )


async def run_network_io(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    return await get_thread_pool_manager().submit_to_pool(
        ThreadPoolType.NETWORK_IO, fn, *args, **kwargs
    )


# context-manager shortcut


@contextmanager
def thread_pool_context(
    pool_type: ThreadPoolType, *, config: ThreadPoolConfig | None = None
):
    pool = get_thread_pool_manager().get_pool(pool_type, config=config)
    yield pool  # ownership remains with manager


__all__ = [
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
]
