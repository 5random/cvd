import asyncio
import signal
import sys
import time

import pytest

from cvd.utils.concurrency.process_pool import (
    ManagedProcessPool,
    ProcessPoolConfig,
)


def add(x: int, y: int) -> int:
    return x + y


def slow() -> int:
    time.sleep(1)
    return 1


def hold(duration: float) -> None:
    time.sleep(duration)


def noop() -> None:
    pass


_NEEDS_PRESTART = sys.platform == "win32" and sys.version_info >= (3, 13)


@pytest.mark.asyncio
async def test_pool_executes_tasks():
    pool = ManagedProcessPool(ProcessPoolConfig(max_workers=1, timeout=2))

    if _NEEDS_PRESTART:
        pool.submit(noop).result(timeout=10)

    res = await pool.submit_async(add, 1, 2)
    assert res == 3
    expected_finished = 1 + int(_NEEDS_PRESTART)
    assert pool._telemetry.finished == expected_finished
    pool.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sig", [signal.SIGTERM, getattr(signal, "SIGKILL", signal.SIGTERM)]
)
async def test_timeout_kills_pool(monkeypatch, sig):
    killed: list[int] = []

    def fake_kill(pid: int, s: int) -> None:
        killed.append(s)

    monkeypatch.setattr("cvd.utils.concurrency.process_pool.os.kill", fake_kill)

    cfg = ProcessPoolConfig(
        max_workers=1, timeout=0.1, kill_on_timeout=True, kill_signal=sig
    )
    pool = ManagedProcessPool(cfg)

    if _NEEDS_PRESTART:
        pool.submit(noop).result(timeout=10)

    with pytest.raises(asyncio.TimeoutError):
        await pool.submit_async(slow)

    assert killed
    assert all(k == sig for k in killed)
    assert pool._executor is None
    pool.config.timeout = 1

    res = await pool.submit_async(add, 40, 2)
    assert res == 42
    pool.shutdown()


def test_scale_workers_behavior():
    pool = ManagedProcessPool(ProcessPoolConfig(max_workers=2))

    if _NEEDS_PRESTART:
        pool.submit(noop).result(timeout=10)

    fut = pool.submit(hold, 0.2)
    original_exec = pool._executor

    pool.scale_workers(1)
    assert pool._max_workers == 2
    assert pool._executor is original_exec

    fut.result(timeout=2)

    pool.scale_workers(1)
    assert pool._max_workers == 1
    assert pool._executor is not original_exec
    pool.shutdown()
