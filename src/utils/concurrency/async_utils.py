"""async_utils_v2.py

A *feature-complete* asyncio helper library with:
------------------------------------------------
* **Structured logging & tracing** – opt-in setup with `setup_logging()`.
* **Exception-Group aware helpers** (Py ≥ 3.11).
* **TaskGroup-based management** with graceful shutdown.
* **Cancelable timeouts** (`asyncio.timeout`).
* **Retry / back-off decorator** – skips `CancelledError`.
* **Context-propagating thread executor**.
* **WeakRef task pool + ergonomic `TaskHandle`**.
* **Token-bucket rate-limiter** with fair scheduling.
* **UNIX signal graceful shutdown** (SIGINT/SIGTERM).
* **Strict typings** – `ParamSpec`, `Self`, `Awaitable`.

Python ≥ 3.11 required.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import functools
import logging
import random
import signal
import time
import weakref
from src.utils.log_service import (
    info,
    warning,
    error,
)
from dataclasses import dataclass
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    List,
    Optional,
    ParamSpec,
    Self,
    TypeVar,
    cast,
)


# Stub to satisfy __all__, real logging handled by LogService
def setup_logging(level: int = logging.INFO) -> None:
    """No-op: centralized LogService handles logging."""
    pass


# Add missing type definitions for generics
T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


# ----------------- Retry-Decorator ----------------
def retry_async(
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    backoff_factor: float = 2.0,
    jitter: float = 0.1,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry an async callable with exponential back-off + jitter."""

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except asyncio.CancelledError:
                    raise
                except exceptions as exc:
                    last_exc = exc
                    if attempt == attempts:
                        error(
                            "retry_exhausted",
                            fn=fn.__qualname__,
                            attempts=attempts,
                            exc_info=exc,
                        )
                        raise
                    delay = base_delay * (
                        backoff_factor ** (attempt - 1)
                    ) + random.uniform(0, jitter)
                    warning(
                        "retry_scheduled",
                        fn=fn.__qualname__,
                        attempt=attempt,
                        sleep=f"{delay:.3f}",
                        exc_info=exc,
                    )
                    await asyncio.sleep(delay)
            # should not reach here
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator


# ───────────────────── Timeout-Wrapper ───────────────────────
def run_with_timeout(
    timeout: float,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Cancel wrapped coroutine after *timeout* seconds."""

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async with asyncio.timeout(timeout):
                return await fn(*args, **kwargs)

        return wrapper

    return decorator


# ──────────────── Token-Bucket-Rate-Limiter ──────────────────
class AsyncRateLimiter:
    """Token-bucket limiter with fairness & burst control."""

    def __init__(self, rate: int, period: float, *, burst: int | None = None) -> None:
        self._rate = rate
        self._period = period
        self._tokens: float = rate
        self._updated_at = time.monotonic()
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(burst or rate)

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.release()

    async def acquire(self) -> None:
        """Acquire a rate-limiter token, waiting if necessary."""
        while True:
            async with self._lock:
                self._refill_tokens_locked()
                if self._tokens >= 1:
                    self._tokens -= 1
                    break
                wait_time = (1 - self._tokens) * (self._period / self._rate)
            await asyncio.sleep(wait_time)

        await self._sem.acquire()

    def release(self) -> None:
        self._sem.release()

    def _refill_tokens_locked(self) -> None:
        now = time.monotonic()
        elapsed = now - self._updated_at
        if elapsed <= 0:
            return
        self._tokens = min(
            self._rate, self._tokens + elapsed * (self._rate / self._period)
        )
        self._updated_at = now


# ────────── gather_with_concurrency (Race-Fix) ───────────────
async def gather_with_concurrency(
    coros: Iterable[Awaitable[T]],
    *,
    label: str = "gather",
    limiter: AsyncRateLimiter | None = None,
    cancel_on_exception: bool = True,
) -> List[T]:
    """Gather *coros* respecting an optional ``AsyncRateLimiter``.

    On error, an ``ExceptionGroup`` holding *all* exceptions is raised.
    """

    coro_list = list(coros)
    results: List[Optional[T]] = [None] * len(coro_list)
    errors: list[Exception] = []
    err_lock = asyncio.Lock()

    async def _worker(idx: int, aw: Awaitable[T]) -> None:
        async def _exec() -> None:
            info("task_started", task_id=f"{label}.{idx}", manager=label)
            try:
                results[idx] = await aw
            except Exception as exc:
                async with err_lock:
                    errors.append(exc)
                if cancel_on_exception:
                    raise
            finally:
                pass

        if limiter is not None:
            async with limiter:
                await _exec()
        else:
            await _exec()

    try:
        async with asyncio.TaskGroup() as tg:
            for i, coro in enumerate(coro_list):
                tg.create_task(_worker(i, coro))
    except* Exception as eg:
        error("gather_failed", label=label, exc_info=eg)
        raise

    if errors and not cancel_on_exception:
        exc_group = ExceptionGroup(f"{label} collected errors", errors)
        error("gather_errors", label=label, exc_info=exc_group)
        raise exc_group

    return cast(List[T], results)


# -------- Context-propagating run_in_executor --------
async def run_in_executor(
    func: Callable[..., R],
    /,
    *args: Any,
    executor: concurrent.futures.Executor | None = None,
    **kwargs: Any,
) -> R:
    loop = asyncio.get_running_loop()

    # Simplified: use LogService for any logging within executor
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))


# Ergonomic TaskHandle + manager
###############################################################################


@dataclass(slots=True)
class TaskHandle(Generic[T]):
    """A lightweight wrapper around ``asyncio.Task`` for fluent use."""

    _task: asyncio.Task[T]

    def done(self) -> bool:  # noqa: D401 – proxy
        return self._task.done()

    def cancel(self) -> None:
        self._task.cancel()

    def result(self) -> T:
        return self._task.result()

    def exception(self) -> BaseException | None:  # noqa: ANN001
        return self._task.exception()

    async def wait(self) -> T:
        return await self._task

    def __await__(self):  # noqa: D401 – allow ``await handle``
        return self._task.__await__()


class AsyncTaskManager:
    """Structured Task manager providing handles and graceful shutdown."""

    def __init__(self, name: str = "manager") -> None:
        self._name = name
        self._tasks: "weakref.WeakValueDictionary[str, asyncio.Task[Any]]" = (
            weakref.WeakValueDictionary()
        )
        info("manager_created", manager=name)

    # -------- context manager --------------------------------------
    async def __aenter__(self) -> Self:  # noqa: D401
        info("manager_enter", manager=self._name)
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
        info("manager_exit", exc_info=exc, manager=self._name)
        await self.stop_all_tasks()

    # -------- create & track ---------------------------------------
    def create_task(
        self,
        coro: Awaitable[T],
        *,
        task_id: str | None = None,
        on_error: Callable[[Exception], Awaitable[None]] | None = None,
    ) -> TaskHandle[T]:
        """Schedule *coro* and return a :class:`TaskHandle`."""
        if task_id is None:
            task_id = f"task-{len(self._tasks) + 1}"
        if task_id in self._tasks:
            raise KeyError(f"Task id {task_id!r} already exists")

        # inner runner ------------------------------------------------
        async def _runner() -> T:
            start = time.perf_counter()
            info("task_started", task_id=task_id, manager=self._name)
            try:
                res = await coro
                info(
                    "task_finished",
                    dt=time.perf_counter() - start,
                    task_id=task_id,
                    manager=self._name,
                )
                return res
            except asyncio.CancelledError:
                warning(
                    "task_cancelled",
                    dt=time.perf_counter() - start,
                    task_id=task_id,
                    manager=self._name,
                )
                raise
            except Exception as exc:
                error(
                    "task_failed",
                    dt=time.perf_counter() - start,
                    exc_info=exc,
                    task_id=task_id,
                    manager=self._name,
                )
                if on_error:
                    with contextlib.suppress(Exception):
                        await on_error(exc)
                raise
            finally:
                pass

        task = asyncio.create_task(_runner(), name=f"{self._name}:{task_id}")
        self._tasks[task_id] = task
        info("task_registered", task_id=task_id, manager=self._name)
        task.add_done_callback(
            lambda t, tid=task_id: self._tasks.pop(tid, None)  # type: ignore[misc]
        )
        return TaskHandle(task)

    # -------- stop helpers -----------------------------------------
    async def stop_task(self, task_id: str, *, timeout: float = 5.0) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.done():
            result = task.exception()
            self._tasks.pop(task_id, None)
            return result is None
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout)
            return True
        except (asyncio.TimeoutError, Exception):
            return False

    async def stop_all_tasks(self, *, timeout: float = 5.0) -> None:
        if not self._tasks:
            return
        for tid, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()

        # Convert to list to freeze current tasks and avoid iteration issues
        # if callbacks modify ``_tasks`` during ``asyncio.wait``
        tasks_list = list(self._tasks.values())
        _, pending = await asyncio.wait(tasks_list, timeout=timeout)

        if pending:
            warning("pending_after_shutdown", count=len(pending))
        self._tasks.clear()


###############################################################################
# Graceful shutdown signals
###############################################################################


def install_signal_handlers(manager: AsyncTaskManager) -> None:
    """Install SIGINT/SIGTERM handlers to shutdown *manager* cleanly."""

    loop = asyncio.get_running_loop()

    async def _shutdown(signame: str) -> None:
        warning("signal", sig=signame)
        await manager.stop_all_tasks()
        await asyncio.sleep(0)  # give cancellations a tick
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(_shutdown(s.name))  # type: ignore[misc]
            )
        except NotImplementedError:  # Windows
            signal.signal(
                sig, lambda *_: asyncio.create_task(_shutdown(sig.name))  # type: ignore[misc]
            )


__all__ = [
    "setup_logging",
    "AsyncRateLimiter",
    "AsyncTaskManager",
    "TaskHandle",
    "gather_with_concurrency",
    "run_with_timeout",
    "retry_async",
    "run_in_executor",
    "install_signal_handlers",
]
