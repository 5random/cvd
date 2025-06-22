import asyncio
import pytest

from program.src.utils.concurrency.async_utils import (
    AsyncTaskManager,
    gather_with_concurrency,
    run_with_timeout,
)
from src.utils import log_service
from program.src.utils.concurrency import async_utils


@pytest.mark.asyncio
async def test_run_with_timeout_expires():
    @run_with_timeout(0.05)
    async def slow():
        await asyncio.sleep(0.2)
        return 1

    with pytest.raises(asyncio.TimeoutError):
        await slow()


@pytest.mark.asyncio
async def test_async_task_manager_stop_releases_tasks():
    mgr = AsyncTaskManager("tst")
    started = asyncio.Event()

    async def worker():
        started.set()
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise

    async with mgr:
        handle = mgr.create_task(worker(), task_id="w")
        await started.wait()
        with pytest.raises(asyncio.CancelledError):
            await mgr.stop_task("w", timeout=0.1)
        assert handle.done()
        await mgr.stop_all_tasks()
    assert len(mgr._tasks) == 0


@pytest.mark.asyncio
async def test_async_task_manager_stop_task_timeout_removed():
    mgr = AsyncTaskManager("tst")
    started = asyncio.Event()
    cancel_count = 0

    async def stubborn_worker():
        nonlocal cancel_count
        started.set()
        while True:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                cancel_count += 1
                if cancel_count >= 2:
                    raise

    async with mgr:
        mgr.create_task(stubborn_worker(), task_id="w")
        await started.wait()
        result = await mgr.stop_task("w", timeout=0.05)
        assert result is False
        assert "w" not in mgr._tasks
        await mgr.stop_all_tasks(timeout=0.1)
    assert len(mgr._tasks) == 0


@pytest.mark.asyncio
async def test_async_task_manager_stop_task_exception_removed():
    mgr = AsyncTaskManager("tst")

    async def failing_worker():
        await asyncio.sleep(0.05)
        raise RuntimeError("boom")

    async with mgr:
        mgr.create_task(failing_worker(), task_id="w")
        await asyncio.sleep(0.06)
        result = await mgr.stop_task("w", timeout=0.1)
        assert result is False
        assert "w" not in mgr._tasks
        await mgr.stop_all_tasks()
    assert len(mgr._tasks) == 0


@pytest.mark.asyncio
async def test_gather_with_concurrency_cancels_remaining():
    cancelled = asyncio.Event()

    async def good():
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def bad():
        await asyncio.sleep(0.05)
        raise RuntimeError("boom")

    with pytest.raises(ExceptionGroup):
        await gather_with_concurrency([good(), bad()])

    assert cancelled.is_set()
