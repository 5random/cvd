import asyncio
import pytest

from src.utils.concurrency.process_pool import (
    get_process_pool_manager,
    ProcessPoolType,
)


@pytest.mark.asyncio
async def test_manager_refcounts():
    mgr = get_process_pool_manager()
    pool1 = mgr.get_pool(ProcessPoolType.CPU)
    pool2 = mgr.get_pool(ProcessPoolType.CPU)
    assert pool1 is pool2

    mgr.release_pool(ProcessPoolType.CPU)
    assert ProcessPoolType.CPU in mgr._pools

    mgr.release_pool(ProcessPoolType.CPU)
    assert ProcessPoolType.CPU not in mgr._pools
